"""Tests for the words the station speaks."""

from __future__ import annotations

import pytest

from custom_components.adsb_station.coordinator import AircraftSummary
from custom_components.adsb_station.speech import language_of, name_of


def _aircraft(**values: object) -> AircraftSummary:
    """Return a summary with only what a test cares about filled in."""
    empty: dict[str, object] = {
        "hex": "484123",
        "flight": None,
        "distance": None,
        "altitude": None,
        "speed": None,
        "track": None,
        "vertical_rate": None,
        "rssi": None,
        "seen": None,
        "registration": None,
        "aircraft_type": None,
        "description": None,
        "military": False,
    }
    return AircraftSummary(**{**empty, **values})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("asked", "answered"),
    [
        ("nl", "nl"),
        ("nl-NL", "nl"),
        ("en-GB", "en"),
        ("EN", "en"),
        # A language we have no words for is answered in English rather than
        # not at all
        ("de", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_language_of(asked: str | None, answered: str) -> None:
    """Test which language an answer comes back in."""
    assert language_of(asked) == answered


@pytest.mark.parametrize(
    ("aircraft", "spoken"),
    [
        # An airliner is announced the way everyone else announces it
        (_aircraft(flight="KLM123", airline="KLM"), "KLM 123"),
        # Leading noughts are part of the flight number on paper only
        (_aircraft(flight="KLM007", airline="KLM"), "KLM 7"),
        # An airline the table has no name for is spelled out rather than
        # read as a word
        (_aircraft(flight="XYZ99"), "X Y Z 9 9"),
        # A business jet or a glider flies under its registration
        (_aircraft(registration="PH-ABC"), "P H A B C"),
        # And with nothing else at all, its hex code is the only name it has
        (_aircraft(), "4 8 4 1 2 3"),
    ],
)
def test_name_of(aircraft: AircraftSummary, spoken: str) -> None:
    """Test what an aircraft is called out loud."""
    assert name_of(aircraft, "en") == spoken
