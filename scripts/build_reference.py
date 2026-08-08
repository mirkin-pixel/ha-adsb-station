"""Rebuild the two reference tables the integration ships.

Neither of these can come off your own network. An aircraft broadcasts a
callsign and an ICAO type code and nothing else, so turning `DLH6CH` into
Lufthansa and `A20N` into an Airbus A320neo means having a table on hand.
Asking a service on the internet for something that never changes would be
a request per aircraft for data that fits in a file, so the file ships with
the integration and this script regenerates it.

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

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "adsb_station"
AIRLINES_FILE = PACKAGE / "airlines.json"
MODELS_FILE = PACKAGE / "aircraft_models.json"


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


def _write(path: Path, key: str, table: dict[str, str]) -> None:
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
