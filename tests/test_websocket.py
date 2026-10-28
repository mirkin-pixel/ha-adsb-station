"""Tests for the sky the dashboard card subscribes to."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.adsb_station.const import DEFAULT_SCAN_INTERVAL
from custom_components.adsb_station.websocket import SUBSCRIBE_AIRCRAFT

from .conftest import (
    HOME_LATITUDE,
    HOME_LONGITUDE,
    MOCK_AIRCRAFT,
    set_responses,
    setup_integration,
)


def _station_device(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the device the card would find, by the overhead sensor's key."""
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if entity.translation_key == "overhead_flight":
            assert entity.device_id is not None
            return entity.device_id
    raise AssertionError("no overhead sensor")


async def test_the_sky_is_sent_and_follows_every_poll(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that every aircraft with a position is sent, now and after a poll."""
    set_responses(aioclient_mock)
    assert await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": SUBSCRIBE_AIRCRAFT,
            "device_id": _station_device(hass, mock_config_entry),
        }
    )
    assert (await client.receive_json())["success"]
    sky = (await client.receive_json())["event"]

    assert sky["latitude"] == HOME_LATITUDE
    assert sky["longitude"] == HOME_LONGITUDE
    assert sky["radius"] == 10
    # Not only the nearby one: TRA45 is a hundred kilometres out. EZY22 has no
    # position, so there is nowhere to draw it.
    planes = {plane["flight"]: plane for plane in sky["aircraft"]}
    assert sorted(planes) == ["KLM123", "TRA45"]
    assert planes["KLM123"]["latitude"] == 52.01
    assert planes["KLM123"]["longitude"] == 5.0
    assert planes["KLM123"]["track"] == 90
    assert planes["TRA45"]["altitude"] == 35000
    assert planes["TRA45"]["distance"] == 111.3

    moved = {
        **MOCK_AIRCRAFT,
        "aircraft": [{**MOCK_AIRCRAFT["aircraft"][0], "lat": 52.02}],
    }
    set_responses(aioclient_mock, aircraft=moved)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)
    )
    await hass.async_block_till_done()

    sky = (await client.receive_json())["event"]
    assert [plane["latitude"] for plane in sky["aircraft"]] == [52.02]
    # The trails go out with the first sky only.
    assert "trails" not in sky

    # A card opened now gets where KLM123 has been, not just where it is.
    await client.send_json_auto_id(
        {
            "type": SUBSCRIBE_AIRCRAFT,
            "device_id": _station_device(hass, mock_config_entry),
        }
    )
    assert (await client.receive_json())["success"]
    trails = (await client.receive_json())["event"]["trails"]
    assert [point[:3] for point in trails["484123"]] == [
        [52.01, 5.0, 2000],
        [52.02, 5.0, 2000],
    ]
    assert [point[:3] for point in trails["484124"]] == [[53.0, 5.0, 35000]]


async def test_an_unknown_device_is_an_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a device that is not a station is answered, not ignored."""
    set_responses(aioclient_mock)
    assert await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": SUBSCRIBE_AIRCRAFT, "device_id": "no-such-device"}
    )
    answer = await client.receive_json()

    assert not answer["success"]
    assert answer["error"]["code"] == "not_found"
