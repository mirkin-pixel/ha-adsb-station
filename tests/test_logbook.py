"""Tests for the lines the rare events leave in the activity log."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant
import pytest

from custom_components.adsb_station.const import (
    EVENT_AIRCRAFT_APPROACHING,
    EVENT_AIRCRAFT_EMERGENCY,
    EVENT_AIRCRAFT_PASSAGE,
    EVENT_WATCHLIST_MATCH,
)
from custom_components.adsb_station.logbook import async_describe_events

AIRCRAFT = {"station": "Garage", "hex": "4ca123", "flight": "RYR1YY", "distance": 11.1}


def _described(hass: HomeAssistant) -> dict[str, Callable[[Event], dict[str, str]]]:
    described: dict[str, Callable[[Event], dict[str, str]]] = {}
    async_describe_events(
        hass, lambda _, event_type, describe: described.update({event_type: describe})
    )
    return described


@pytest.mark.parametrize(
    ("language", "event_type", "data", "message"),
    [
        (
            "en",
            EVENT_WATCHLIST_MATCH,
            {**AIRCRAFT, "squawk": "1000"},
            "heard RYR1YY from the watchlist, 11.1 km away",
        ),
        (
            "nl",
            EVENT_WATCHLIST_MATCH,
            {**AIRCRAFT, "flight": None, "registration": "EI-DCL"},
            "hoorde EI-DCL van de watchlist, op 11,1 km",
        ),
        (
            "en",
            EVENT_AIRCRAFT_EMERGENCY,
            {**AIRCRAFT, "reason": "radio_failure", "squawk": "7600"},
            "heard RYR1YY report a radio failure, squawk 7600, 11.1 km away",
        ),
        (
            "nl-BE",
            EVENT_AIRCRAFT_EMERGENCY,
            {
                **AIRCRAFT,
                "flight": None,
                "reason": "emergency",
                "squawk": None,
                "distance": None,
            },
            "hoorde 4CA123 een noodgeval melden",
        ),
    ],
)
async def test_lines(
    hass: HomeAssistant,
    language: str,
    event_type: str,
    data: dict[str, Any],
    message: str,
) -> None:
    """Test what each line says, by the name of the station, in its language."""
    hass.config.language = language
    line = _described(hass)[event_type](Event(event_type, data))
    assert line == {LOGBOOK_ENTRY_NAME: "Garage", LOGBOOK_ENTRY_MESSAGE: message}


async def test_passages_stay_out(hass: HomeAssistant) -> None:
    """Test that the events of dozens a day are not described."""
    described = _described(hass)
    assert EVENT_AIRCRAFT_PASSAGE not in described
    assert EVENT_AIRCRAFT_APPROACHING not in described
