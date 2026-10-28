"""Tests for the sky the dashboard card subscribes to."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.adsb_station.const import (
    CONF_LOOK_UP_ROUTES,
    DEFAULT_SCAN_INTERVAL,
    ROUTESET_URL,
)
from custom_components.adsb_station.websocket import LOOK_UP_ROUTE, SUBSCRIBE_AIRCRAFT

from .conftest import (
    HOME_LATITUDE,
    HOME_LONGITUDE,
    MOCK_AIRCRAFT,
    set_responses,
    setup_integration,
)
from .test_route import ROUTESET_ANSWER


@pytest.fixture
def route_entry(mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """Return the usual entry, with routes looked up."""
    return MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        unique_id=mock_config_entry.unique_id,
        data=mock_config_entry.data,
        options={CONF_LOOK_UP_ROUTES: True},
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


async def test_the_route_of_a_nearby_aircraft_comes_with_the_sky(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    route_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a route already looked up is sent with where its ends are."""
    set_responses(aioclient_mock)
    aioclient_mock.post(ROUTESET_URL, json=ROUTESET_ANSWER)
    assert await setup_integration(hass, route_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": SUBSCRIBE_AIRCRAFT, "device_id": _station_device(hass, route_entry)}
    )
    assert (await client.receive_json())["success"]
    planes = {
        plane["flight"]: plane
        for plane in (await client.receive_json())["event"]["aircraft"]
    }

    points = planes["KLM123"]["route_points"]
    assert points["origin"]["code"] == "GOT"
    assert points["destination"]["latitude"] == 52.308601
    # TRA45 is outside the radius, so nothing was asked about it yet.
    assert "route_points" not in planes["TRA45"]


async def test_a_tapped_aircraft_further_out_is_looked_up(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    route_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that the card can ask for the route of any aircraft it shows."""
    set_responses(aioclient_mock)
    aioclient_mock.post(
        ROUTESET_URL, json=[{**ROUTESET_ANSWER[0], "callsign": "TRA45"}]
    )
    assert await setup_integration(hass, route_entry)
    freezer.tick(timedelta(seconds=31))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": LOOK_UP_ROUTE,
            "device_id": _station_device(hass, route_entry),
            "hex": "484124",
        }
    )
    answer = await client.receive_json()

    assert answer["success"]
    assert answer["result"]["route_points"]["origin"]["location"] == "Gothenburg"


async def test_no_route_when_routes_are_off(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that nothing is asked for a station that keeps routes off."""
    set_responses(aioclient_mock)
    assert await setup_integration(hass, mock_config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": LOOK_UP_ROUTE,
            "device_id": _station_device(hass, mock_config_entry),
            "hex": "484124",
        }
    )
    answer = await client.receive_json()

    assert answer["result"] == {"route_points": None}
    assert not [
        call for call in aioclient_mock.mock_calls if "routeset" in str(call[1])
    ]
