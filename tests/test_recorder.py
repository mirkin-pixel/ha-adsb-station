"""Tests against a running recorder and its database.

In a module of their own: the recorder has to be set up before Home
Assistant, which every test in a module then pays for.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.components import recorder
from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.adsb_station.const import CONF_MAP_AIRCRAFT

from .conftest import set_responses, setup_integration
from .test_emergency_event import DISTRESS
from .test_geo_location import NEARBY_LATITUDE, NEARBY_LONGITUDE, _poll
from .test_passages import poll
from .test_websocket import _station_device


@pytest.fixture
def mock_recorder_before_hass(async_setup_recorder_instance: Any) -> None:
    """Set the recorder up before Home Assistant, as it needs to be."""


async def test_an_aircraft_on_the_map_leaves_no_position_behind(
    recorder_mock: Any,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test what is written to the database for an aircraft on the map.

    Only what Home Assistant keeps for every entity, not a position per poll.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True}
    )
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {
                "hex": "484123",
                "flight": "KLM123",
                "lat": NEARBY_LATITUDE,
                "lon": NEARBY_LONGITUDE,
                "alt_baro": 2000,
            }
        ),
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert "latitude" in hass.states.get("geo_location.klm123").attributes
    await async_wait_recording_done(hass)

    history = await recorder.get_instance(hass).async_add_executor_job(
        state_changes_during_period,
        hass,
        dt_util.utcnow() - timedelta(hours=1),
        None,
        "geo_location.klm123",
    )
    recorded = history["geo_location.klm123"]
    assert recorded
    assert set(recorded[0].attributes) <= {"friendly_name", "unit_of_measurement"}


async def test_an_emergency_on_the_device_page(
    recorder_mock: Any,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the line in the activity log, heard on the very first poll."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)
    # Its panel needs the built frontend, which the tests do not install.
    with patch("homeassistant.components.frontend.async_register_built_in_panel"):
        hass.config.components.add("frontend")
        assert await async_setup_component(hass, "logbook", {})
    await async_wait_recording_done(hass)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "logbook/get_events",
            "start_time": (dt_util.utcnow() - timedelta(hours=1)).isoformat(),
            "device_ids": [_station_device(hass, mock_config_entry)],
        }
    )
    response = await client.receive_json()
    assert [(row["name"], row["message"]) for row in response["result"]] == [
        (
            mock_config_entry.title,
            "heard RYR1YY report an emergency, squawk 7700, 11.1 km away",
        )
    ]
