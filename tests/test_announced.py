"""Tests that what was announced is not announced again after a restart."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Event, HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_WATCHLIST,
    EVENT_AIRCRAFT_EMERGENCY,
    EVENT_WATCHLIST_LOST,
    EVENT_WATCHLIST_MATCH,
    PASSAGE_GAP,
)

from .conftest import set_responses, setup_integration
from .test_emergency_event import DISTRESS, QUIET
from .test_passages import next_poll, poll


@pytest.fixture
def events(hass: HomeAssistant) -> list[Event]:
    """Collect the events that announce something."""
    collected: list[Event] = []
    for kind in (EVENT_AIRCRAFT_EMERGENCY, EVENT_WATCHLIST_MATCH, EVENT_WATCHLIST_LOST):
        hass.bus.async_listen(kind, collected.append)
    return collected


def _kinds(events: list[Event]) -> list[str]:
    # Sorted: Home Assistant 2025.7 hands events to listeners in its own order.
    return sorted(event.event_type for event in events)


async def _reload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_reload_says_nothing_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    events: list[Event],
) -> None:
    """Test that an emergency and a watched aircraft still up are not repeated."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_WATCHLIST: "4CA123"}
    )
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)
    assert _kinds(events) == [EVENT_AIRCRAFT_EMERGENCY, EVENT_WATCHLIST_MATCH]

    await _reload(hass, mock_config_entry)

    assert len(events) == 2


async def test_one_gone_while_away_is_still_said_to_be_lost(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    events: list[Event],
) -> None:
    """Test that the lost event comes after a reload, with what was seen before."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_WATCHLIST: "4CA123"}
    )
    set_responses(aioclient_mock, aircraft=poll(QUIET))
    assert await setup_integration(hass, mock_config_entry)

    set_responses(aioclient_mock, aircraft=poll())
    await _reload(hass, mock_config_entry)
    await next_poll(hass, freezer, PASSAGE_GAP * 2)

    match, lost = events
    assert lost.event_type == EVENT_WATCHLIST_LOST
    assert lost.data["hex"] == match.data["hex"] == "4ca123"


async def test_after_a_long_break_it_is_news_again(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    events: list[Event],
) -> None:
    """Test that what was kept is forgotten once it would have been anyway."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    freezer.tick(PASSAGE_GAP * 2)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _kinds(events) == [EVENT_AIRCRAFT_EMERGENCY, EVENT_AIRCRAFT_EMERGENCY]
