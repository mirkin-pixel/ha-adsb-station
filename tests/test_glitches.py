"""Tests for riding out a missed read or two without anyone noticing."""

from __future__ import annotations

from datetime import timedelta

import aiohttp
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DEFAULT_SCAN_INTERVAL,
    EVENT_AIRCRAFT_PASSAGE,
    MISSED_READS_TOLERATED,
)

from .conftest import set_responses, setup_integration

OVERHEAD = "binary_sensor.t_ehxx23_aircraft_overhead"


async def _poll(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)
    )
    await hass.async_block_till_done()


async def test_a_hiccup_changes_nothing_an_automation_can_see(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer,
) -> None:
    """Test the harm this is about: no flicker, so no second notification.

    An aircraft is overhead. Before, one missed read turned the sensor
    unavailable and the next one turned it on again, which an automation
    waiting for "on" took for a second aircraft.
    """
    passages: list[Event] = []
    changes: list[Event] = []
    hass.bus.async_listen(EVENT_AIRCRAFT_PASSAGE, passages.append)
    assert await setup_integration(hass, mock_config_entry)
    state = hass.states.get(OVERHEAD)
    assert state is not None
    assert state.state == "on"
    assert len(passages) == 1

    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        lambda event: (
            changes.append(event) if event.data["entity_id"] == OVERHEAD else None
        ),
    )
    set_responses(mock_api, aircraft_kwargs={"exc": aiohttp.ClientError("boom")})
    for _ in range(MISSED_READS_TOLERATED):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5))
        await _poll(hass)

    set_responses(mock_api)
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5))
    await _poll(hass)

    assert changes == []
    assert len(passages) == 1
    state = hass.states.get(OVERHEAD)
    assert state is not None
    assert state.state == "on"
