"""Tests for the airline and aircraft type tables."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
import pytest

from custom_components.adsb_station.reference import (
    ReferenceTables,
    _read,
    async_load_reference,
    designator_of,
)

TABLES = ReferenceTables(
    airlines={"KLM": "KLM", "DLH": "Lufthansa"},
    models={"B738": "Boeing 737-800"},
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


def test_missing_table_is_not_fatal() -> None:
    """Test that a table that cannot be read costs a name and nothing more."""
    assert _read("not-a-file.json", "airlines") == {}


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
