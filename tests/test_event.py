"""Tests for the event entities that repeat the rare bus events."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_WATCHLIST,
    DOMAIN,
    EVENT_AIRCRAFT_EMERGENCY,
)

from .conftest import set_responses, setup_integration
from .test_emergency_event import DISTRESS
from .test_passages import next_poll, poll
from .test_watchlist import FAR_AWAY, watching


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str | None:
    unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
    return er.async_get(hass).async_get_entity_id("event", DOMAIN, unique_id)


async def test_an_aircraft_in_distress(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the reason as the event type, with the aircraft and not the station."""
    set_responses(aioclient_mock, aircraft=poll())
    assert await setup_integration(hass, mock_config_entry)
    # The first poll runs before the entities exist.
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    await next_poll(hass, freezer)

    state = hass.states.get(_entity_id(hass, mock_config_entry, "distress"))
    assert state.attributes["event_type"] == "emergency"
    assert state.attributes["flight"] == "RYR1YY"
    assert state.attributes["squawk"] == "7700"
    assert "entry_id" not in state.attributes
    assert "device_id" not in state.attributes

    # Another station's, and one with no reason, leave it as it was.
    before = state.state
    hass.bus.async_fire(
        EVENT_AIRCRAFT_EMERGENCY, {"entry_id": "other", "reason": "hijack"}
    )
    hass.bus.async_fire(
        EVENT_AIRCRAFT_EMERGENCY, {"entry_id": mock_config_entry.entry_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(_entity_id(hass, mock_config_entry, "distress"))
    assert (state.state, state.attributes["event_type"]) == (before, "emergency")


async def test_a_watched_aircraft(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the watchlist entity, there only while there is a list."""
    await watching(hass, mock_config_entry, aioclient_mock, "484123", poll())
    set_responses(aioclient_mock, aircraft=poll(FAR_AWAY))
    await next_poll(hass, freezer)

    state = hass.states.get(_entity_id(hass, mock_config_entry, "watchlist_event"))
    assert state.attributes["event_type"] == "in_range"
    assert state.attributes["watching"] == "484123"

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_WATCHLIST: ""}
    )
    await hass.async_block_till_done()
    assert _entity_id(hass, mock_config_entry, "watchlist_event") is None

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_WATCHLIST: "PH-BXA"}
    )
    await hass.async_block_till_done()
    assert _entity_id(hass, mock_config_entry, "watchlist_event") is not None


async def test_none_without_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a station without a list: distress, but no watchlist entity."""
    set_responses(aioclient_mock)
    assert await setup_integration(hass, mock_config_entry)

    assert _entity_id(hass, mock_config_entry, "distress") is not None
    assert _entity_id(hass, mock_config_entry, "watchlist_event") is None
