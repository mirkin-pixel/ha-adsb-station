"""Rebuild the three reference tables the integration ships.

None of these can come off your own network. An aircraft broadcasts a
callsign, an ICAO type code and a 24 bit address and nothing else, so turning
`DLH6CH` into Lufthansa, `A20N` into an Airbus A320neo and `484123` into the
Netherlands means having a table on hand. Asking a service on the internet
for something that never changes would be a request per aircraft for data
that fits in a file, so the file ships with the integration and this script
regenerates it.

The source is the standing data of Virtual Radar Server, which is published
into the public domain under CC0-1.0:

    https://github.com/vradarserver/standing-data

Run it from the repository root, and commit what it writes:

    python scripts/build_reference.py
"""

from __future__ import annotations

import csv
from itertools import takewhile
import json
from pathlib import Path
import re
from string import ascii_uppercase
from typing import Any
import urllib.request

BASE_URL = "https://raw.githubusercontent.com/vradarserver/standing-data/main"
AIRLINES_URL = f"{BASE_URL}/airlines/schema-01/airlines.csv"
CODE_BLOCKS_URL = f"{BASE_URL}/code-blocks/schema-01/code-blocks.csv"
# The model types are split over one file per initial letter, plus a file for
# the codes that start with something else.
MODEL_URLS = tuple(
    f"{BASE_URL}/model-type/schema-01/{letter}.csv"
    for letter in (*ascii_uppercase, "-")
)

SOURCE = "https://github.com/vradarserver/standing-data (CC0-1.0)"

# A military designation, as in the "P-72" of an ATR P-72. Only ever a hint,
# and only used where it follows the model name rather than opening it.
MILITARY_DESIGNATION = re.compile(r"^[A-Z]{1,2}-\d")

# The code an aircraft carries when it has no type designator at all. Its row
# says so in words, which reads as a description and is not one.
UNASSIGNED_TYPE = "ZZZZ"

# Codes in the country column that are not countries. ZZ is the whole address
# space, sitting under everything else as the row that says nothing is known;
# XA, XB and XC are carve-outs for addresses that belong to no single state,
# from ICAO's own F00000-F07FFF down to single hex codes inside a national
# block. Dropping all four leaves those aircraft to the block around them, or
# to no country at all, which is the truth in both cases.
UNASSIGNED_COUNTRIES = frozenset({"ZZ", "XA", "XB", "XC"})

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "adsb_station"
AIRLINES_FILE = PACKAGE / "airlines.json"
MODELS_FILE = PACKAGE / "aircraft_models.json"
CODE_BLOCKS_FILE = PACKAGE / "code_blocks.json"


def _fetch(url: str) -> list[dict[str, str]]:
    """Read one CSV off the source repository."""
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        # The files carry a byte order mark, which utf-8-sig eats for us.
        text = response.read().decode("utf-8-sig")
    return list(csv.DictReader(text.splitlines()))


def build_airlines() -> dict[str, str]:
    """Return the ICAO airline designators, mapped to the airline's name.

    The file is keyed on a code that may be either an IATA or an ICAO one, so
    the rows without an ICAO code are travel agencies and ticketing systems
    that no aircraft will ever broadcast. The first row for a code wins.
    """
    airlines: dict[str, str] = {}
    for row in _fetch(AIRLINES_URL):
        icao = (row.get("ICAO") or "").strip().upper()
        name = (row.get("Name") or "").strip()
        if len(icao) != 3 or not icao.isalpha() or not name:
            continue
        airlines.setdefault(icao, name)
    return airlines


def _score(code: str, manufacturer: str, model: str, active: bool) -> int:
    """Rate how likely one row is to be the aircraft the code stands for.

    A type code covers a family rather than a single aircraft, so most of them
    have several rows: a C172 is a Cessna 172 but also a licence-built one from
    Colombia, and a BE20 is any of a dozen King Airs and their military
    cousins. Nothing in the data says which one you are most likely to see
    overhead, but the code itself is a strong hint, because it is built out of
    the manufacturer and the model: C172 is Cessna 172, BE20 is a Beech 200,
    B06 is a Bell 206. So the row whose manufacturer and model the code spells
    out wins, and a type still in service always beats one that is not.
    """
    letters = "".join(takewhile(str.isalpha, code))
    digits = "".join(takewhile(str.isdigit, code[len(letters) :]))

    score = 4 if active else 0
    upper = manufacturer.upper()
    if letters and upper.startswith(letters):
        score += 3
    elif letters and upper.startswith(letters[0]):
        score += 1
    # Compared without the hyphen, so a "200 Super King Air" is recognised as
    # the 200 in BE20 and an "A-320neo" is not mistaken for one.
    if digits and model.replace("-", "").upper().startswith(digits):
        score += 2

    # Two variants that share their code with an airliner and are far rarer
    # than it: the corporate conversions, and the military ones that carry
    # their designation behind the model name, as the maritime patrol version
    # of an ATR 72 does. A single point, so this only settles a tie.
    words = model.upper().split()
    if any(word in ("BBJ", "ACJ") or word.startswith(("BBJ", "ACJ")) for word in words):
        score -= 1
    if any(MILITARY_DESIGNATION.match(word) for word in words[1:]):
        score -= 1
    # An ATR 72-600 and an "ATR-72-212A (600)" are the same aircraft under the
    # certification number of the airframe. Prefer the name people use.
    if "(" in model:
        score -= 1
    return score


def build_models() -> dict[str, str]:
    """Return the ICAO type codes, mapped to a name you can read."""
    models: dict[str, str] = {}
    best: dict[str, int] = {}
    for url in MODEL_URLS:
        for row in _fetch(url):
            code = (row.get("ICAO") or "").strip().upper()
            manufacturer = (row.get("Manufacturer") or "").strip()
            model = (row.get("Model") or "").strip()
            if not code or not model or code == UNASSIGNED_TYPE:
                continue
            score = _score(
                code, manufacturer, model, (row.get("IsActive") or "").strip() == "1"
            )
            # Strictly greater, so the first row of the best kind wins and the
            # output does not depend on how the rows below it are ordered. A
            # code is only ever missing when the source has no row for it, so
            # an unseen code has to lose to any score, including a negative one.
            if code not in best or score > best[code]:
                best[code] = score
                models[code] = f"{manufacturer} {model}".strip()
    return models


Block = tuple[int, int, str, bool]


def _flatten(blocks: list[Block]) -> list[Block]:
    """Return the same blocks with nothing sitting inside anything else.

    The source nests: `000000-7FFFFF` covers half the address space, the
    Netherlands hold `480000-487FFF` inside it, and the Dutch military
    `480000-480FFF` inside that again. A lookup would have to find every block
    that contains an address and pick between them, so the nesting is undone
    here instead, once, offline. At runtime a hex code then lands in exactly
    one block and the search is a single bisect.

    The narrowest block wins, because that is the one that says the most: an
    address inside the Dutch military range is Dutch and military, not merely
    Dutch. Blocks that end up saying the same thing and touch are joined back
    together, so the table is no longer than the answers it holds.
    """
    edges = sorted(
        {edge for start, finish, _, _ in blocks for edge in (start, finish + 1)}
    )
    flattened: list[Block] = []
    for start, next_edge in zip(edges, edges[1:], strict=False):
        finish = next_edge - 1
        covering = [
            block for block in blocks if block[0] <= start and finish <= block[1]
        ]
        if not covering:
            # A gap between two blocks. Nothing is registered there, so
            # nothing is claimed about it either.
            continue
        _, _, country, military = min(covering, key=lambda block: block[1] - block[0])
        if flattened:
            before = flattened[-1]
            if before[1] + 1 == start and before[2:] == (country, military):
                flattened[-1] = (before[0], finish, country, military)
                continue
        flattened.append((start, finish, country, military))
    return flattened


def build_code_blocks() -> dict[str, list[Any]]:
    """Return the ICAO address ranges, mapped to a country and a military flag.

    Every aircraft transmits a 24 bit address, and the range it falls in was
    handed to a country by ICAO. That makes two things knowable from the hex
    code alone, without an aircraft database and without asking anyone: where
    an aircraft is registered, and whether it sits in a range a state keeps
    for its own military.

    The second is the reason this table exists. A decoder without an aircraft
    database sends no dbFlags at all, so on those stations the military marker
    was permanently empty. It is a coarser answer than dbFlags, which knows
    the individual tail, and the integration treats it as one.
    """
    blocks: list[Block] = []
    for row in _fetch(CODE_BLOCKS_URL):
        start = (row.get("Start") or "").strip()
        finish = (row.get("Finish") or "").strip()
        country = (row.get("CountryISO2") or "").strip().upper()
        if len(country) != 2 or country in UNASSIGNED_COUNTRIES:
            continue
        try:
            first, last = int(start, 16), int(finish, 16)
        except ValueError:
            continue
        if first > last:
            continue
        blocks.append((first, last, country, (row.get("IsMilitary") or "") == "1"))

    flattened = _flatten(blocks)
    for (_, finish, _, _), (start, *_rest) in zip(
        flattened, flattened[1:], strict=False
    ):
        if start <= finish:
            raise ValueError(f"blocks still overlap at {start:06X}")

    return {
        f"{first:06X}": [f"{last:06X}", country, int(military)]
        for first, last, country, military in flattened
    }


def _write(path: Path, key: str, table: dict[str, Any]) -> None:
    """Write one table, sorted, so a regeneration makes a readable diff."""
    payload: dict[str, Any] = {
        "source": SOURCE,
        key: dict(sorted(table.items())),
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"{path.name}: {len(table)} entries, {path.stat().st_size // 1024} kB")


if __name__ == "__main__":
    _write(AIRLINES_FILE, "airlines", build_airlines())
    _write(MODELS_FILE, "models", build_models())
    _write(CODE_BLOCKS_FILE, "blocks", build_code_blocks())
