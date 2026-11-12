"""Tests for readsb's coverage shape, sent along to the card."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.adsb_station.const import OUTLINE_INTERVAL
from custom_components.adsb_station.websocket import SUBSCRIBE_AIRCRAFT

from .conftest import (
    MOCK_RECEIVER_READSB,
    RECEIVER_URL,
    set_responses,
    setup_integration,
)
from .test_passages import next_poll
from .test_websocket import _station_device

OUTLINE_URL = RECEIVER_URL.replace("receiver.json", "outline.json")
WRITES_ONE = {**MOCK_RECEIVER_READSB, "outlineJson": True}


def _outline(*points: Any) -> dict[str, Any]:
    return {"actualRange": {"last24h": {"points": list(points)}}}


def _read(aioclient_mock: AiohttpClientMocker) -> int:
    return sum(
        1 for _, url, _, _ in aioclient_mock.mock_calls if str(url) == OUTLINE_URL
    )


def _serve(aioclient_mock: AiohttpClientMocker, **kwargs: Any) -> None:
    set_responses(aioclient_mock, receiver=WRITES_ONE)
    aioclient_mock.get(OUTLINE_URL, **kwargs)


async def test_read_now_and_then_and_sent_to_the_card(
    hass: HomeAssistant,
    freezer: Any,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the shape, the points that are no position left out."""
    _serve(
        aioclient_mock,
        json=_outline(
            [52.4, 5.0, 38000], [52.0, 5.6, 36000], ["x", 5.0], [51.6], [51.7, 4.6, 0]
        ),
    )
    assert await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.outline == [(52.4, 5.0), (52.0, 5.6), (51.7, 4.6)]
    assert _read(aioclient_mock) == 1

    # Not on every poll: it changes over a day, not over seconds
    await next_poll(hass, freezer)
    assert _read(aioclient_mock) == 1
    await next_poll(hass, freezer, OUTLINE_INTERVAL)
    assert _read(aioclient_mock) == 2

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": SUBSCRIBE_AIRCRAFT,
            "device_id": _station_device(hass, mock_config_entry),
        }
    )
    assert (await client.receive_json())["success"]
    sky = (await client.receive_json())["event"]
    assert sky["outline"] == [[52.4, 5.0], [52.0, 5.6], [51.7, 4.6]]


async def test_a_failed_read_keeps_the_last(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a decoder busy writing the file does not wipe the shape."""
    _serve(aioclient_mock, json=_outline([52.4, 5.0], [52.0, 5.6], [51.7, 4.6]))
    assert await setup_integration(hass, mock_config_entry)

    _serve(aioclient_mock, exc=ClientError())
    await next_poll(hass, freezer, OUTLINE_INTERVAL + timedelta(seconds=1))
    assert _read(aioclient_mock) == 1
    assert len(mock_config_entry.runtime_data.outline) == 3


async def test_not_asked_for_unless_the_decoder_writes_one(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test dump1090-fa and fr24feed, whose receiver.json says nothing of it."""
    set_responses(aioclient_mock, receiver=MOCK_RECEIVER_READSB)
    assert await setup_integration(hass, mock_config_entry)

    assert _read(aioclient_mock) == 0
    assert mock_config_entry.runtime_data.outline is None
