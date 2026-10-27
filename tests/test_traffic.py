"""Tests for the counters that split the sky into four kinds of traffic."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DB_FLAG_MILITARY, DOMAIN

from .conftest import MOCK_ALIAS, set_responses, setup_integration

# Six aircraft, each picked to land in one of the four on purpose.
SKY: dict[str, Any] = {
    "now": 1636387404.0,
    "messages": 1000,
    "aircraft": [
        # Military by the aircraft database, and a helicopter as well: it
        # counts as military, because that is tried first.
        {
            "hex": "43c6e1",
            "flight": "ASCOT1",
            "category": "A7",
            "dbFlags": DB_FLAG_MILITARY,
            "lat": 52.2,
            "lon": 5.0,
        },
        # Military by the Dutch military address block, under a callsign that
        # looks like an airline's.
        {"hex": "480123", "flight": "NAF11", "lat": 53.0, "lon": 5.0},
        # A civil helicopter, the air ambulance.
        {"hex": "4851a7", "flight": "LIFE01", "category": "A7"},
        # An airline flight: the callsign opens with a designator we know.
        {"hex": "484123", "flight": "KLM123", "lat": 52.01, "lon": 5.0},
        # A private aircraft under its registration.
        {"hex": "486882", "flight": "PHTBM", "category": "A1"},
        # Nothing to go on at all, as a Mode S only aircraft sends.
        {"hex": "4840d6"},
    ],
}


def _count(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


async def test_every_aircraft_counts_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the four counters, and that they add up to what was received."""
    set_responses(aioclient_mock, aircraft=SKY)
    assert await setup_integration(hass, mock_config_entry)

    counts = {
        kind: int(_count(hass, f"aircraft_{kind}"))
        for kind in ("military", "helicopter", "airline", "other")
    }
    assert counts == {"military": 2, "helicopter": 1, "airline": 1, "other": 2}
    # Every aircraft lands in one of the four, wherever it is and whether or
    # not it has a position, so nothing is lost and nothing counted twice.
    assert sum(counts.values()) == int(_count(hass, "aircraft_received")) == 6


async def test_an_empty_sky_is_nought_everywhere(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that nothing heard is a count of nought rather than unknown."""
    set_responses(
        aioclient_mock, aircraft={"now": 1636387404.0, "messages": 0, "aircraft": []}
    )
    assert await setup_integration(hass, mock_config_entry)

    for kind in ("military", "helicopter", "airline", "other"):
        assert _count(hass, f"aircraft_{kind}") == "0"
