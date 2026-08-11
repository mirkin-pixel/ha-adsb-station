"""Tests for the airline, aircraft type and address block tables."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
import pytest

from custom_components.adsb_station import reference
from custom_components.adsb_station.reference import (
    ReferenceTables,
    _read,
    _read_blocks,
    async_load_reference,
    designator_of,
)

# Three blocks as the generator leaves them: flattened, so the Dutch military
# range sits beside the civil one instead of inside it, and with the gaps the
# source has where nothing was ever handed out.
BLOCK_STARTS = (0x3C0000, 0x480000, 0x481000)
BLOCK_VALUES = (
    (0x3FFFFF, "DE", False),
    (0x480FFF, "NL", True),
    (0x483FFF, "NL", False),
)

TABLES = ReferenceTables(
    airlines={"KLM": "KLM", "DLH": "Lufthansa"},
    models={"B738": "Boeing 737-800"},
    starts=BLOCK_STARTS,
    blocks=BLOCK_VALUES,
)


@pytest.mark.parametrize(
    ("callsign", "expected"),
    [
        ("KLM123", "KLM"),
        # A flight number reaches us padded and in either case
        ("klm123  ", "KLM"),
        ("DLH6CH", "Lufthansa"),
        # An airline we have no row for
        ("TRA45", None),
        # A business jet or a light aircraft flies under its registration, and
        # reading three letters off one would name an airline that is not there
        ("PHABC", None),
        ("N123AB", None),
        # Nothing to read a designator out of
        ("KLM", None),
        ("", None),
        (None, None),
    ],
)
def test_airline_of(callsign: str | None, expected: str | None) -> None:
    """Test that only a callsign shaped like a flight number names an airline."""
    assert TABLES.airline_of(callsign) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("B738", "Boeing 737-800"),
        ("b738", "Boeing 737-800"),
        ("A20N", None),
        (None, None),
    ],
)
def test_model_of(code: str | None, expected: str | None) -> None:
    """Test looking a type code up."""
    assert TABLES.model_of(code) == expected


@pytest.mark.parametrize(
    ("hex_code", "country", "military"),
    [
        ("3C6444", "DE", False),
        # Inside the range the Netherlands keeps for its own, and inside the
        # civil range that starts right where it ends
        ("480123", "NL", True),
        ("480FFF", "NL", True),
        ("481000", "NL", False),
        ("483FFF", "NL", False),
        # Read whatever case and padding it arrives in
        (" 480123 ", "NL", True),
        ("480123".lower(), "NL", True),
        # Past the end of the last block, and in the gap between two of them
        ("484000", None, False),
        ("400000", None, False),
        ("000001", None, False),
        # readsb marks an address it worked out rather than heard with a
        # tilde, and that is not an ICAO address to look up at all
        ("~484123", None, False),
        ("", None, False),
        (None, None, False),
    ],
)
def test_address_blocks(
    hex_code: str | None, country: str | None, military: bool
) -> None:
    """Test looking a hex code up in the address blocks."""
    assert TABLES.country_of(hex_code) == country
    assert TABLES.is_military(hex_code) is military


def test_no_blocks_at_all() -> None:
    """Test that a table without blocks answers rather than reaching into one."""
    empty = ReferenceTables()
    assert empty.country_of("480123") is None
    assert empty.is_military("480123") is False


def test_missing_table_is_not_fatal() -> None:
    """Test that a table that cannot be read costs a name and nothing more."""
    assert _read("not-a-file.json", "airlines") == {}
    assert _read_blocks("not-a-file.json") == ((), ())


def test_unreadable_blocks_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that one bad row costs that row rather than the whole table."""
    monkeypatch.setattr(reference, "_DIRECTORY", tmp_path)
    (tmp_path / "blocks.json").write_text(
        json.dumps(
            {
                "blocks": {
                    "480000": ["480FFF", "NL", 1],
                    # Not three things, so there is nothing to read out of it
                    "3C0000": "not a block",
                }
            }
        ),
        "utf-8",
    )
    (tmp_path / "not-a-table.json").write_text(json.dumps({"blocks": []}), "utf-8")

    assert _read_blocks("blocks.json") == ((0x480000,), ((0x480FFF, "NL", True),))
    assert _read_blocks("not-a-table.json") == ((), ())


async def test_shipped_tables(hass: HomeAssistant) -> None:
    """Test that the generated files are there and hold what they should."""
    tables = await async_load_reference(hass)

    assert tables.airline_of("KLM123") == "KLM"
    assert tables.airline_of("TRA45") == "Transavia"
    assert tables.model_of("A20N") == "Airbus A-320neo"
    # A code no aircraft carries stays unknown rather than guessing, and ZZZZ,
    # which is the code for having no type designator, is left out on purpose
    assert tables.model_of("QQQQ") is None
    assert tables.model_of("ZZZZ") is None

    # The address blocks, against four aircraft picked out of the source by
    # hand. A Dutch registration is civil; the range above it is not.
    assert tables.country_of("484123") == "AW"
    assert tables.is_military("484123") is False
    assert (tables.country_of("AE1CE9"), tables.is_military("AE1CE9")) == ("US", True)
    assert (tables.country_of("43C7A2"), tables.is_military("43C7A2")) == ("GB", True)
    assert (tables.country_of("480123"), tables.is_military("480123")) == ("NL", True)
    # ICAO's own range belongs to no country, and neither does the space
    # nobody was ever given
    assert tables.country_of("F00123") is None
    assert tables.country_of("000001") is None


@pytest.mark.parametrize(
    ("callsign", "expected"),
    [
        ("KLM123", "KLM"),
        ("dlh6ch ", "DLH"),
        # An airline this table has never heard of still broadcast a code, and
        # that is what a dashboard looks a logo up by
        ("XYZ99", "XYZ"),
        ("PHABC", None),
        ("N123AB", None),
        ("KLM", None),
        (None, None),
    ],
)
def test_designator_of(callsign: str | None, expected: str | None) -> None:
    """Test reading the airline designator off a callsign."""
    assert designator_of(callsign) == expected
