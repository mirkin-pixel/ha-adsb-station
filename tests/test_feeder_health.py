"""Tests for a feeder's last disconnect, a frozen status page and the decoder."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN
from custom_components.adsb_station.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import (
    MOCK_ALIAS,
    MOCK_MONITOR,
    MOCK_PIAWARE,
    MOCK_RECEIVER_READSB,
    PIAWARE_UNIQUE_ID,
    PIAWARE_URL,
    set_responses,
    setup_integration,
)

# As fr24feed 1.0.51 writes them.
MONITOR = {
    **MOCK_MONITOR,
    "time_update_utc": 1794838758,
    "feed_last_disconnected_time": 1794733538,
    "feed_status_message": "",
}


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def _state(hass: HomeAssistant, domain: str, unique_id: str) -> Any:
    entity_id = _entity_id(hass, domain, unique_id)
    assert entity_id is not None, unique_id
    return hass.states.get(entity_id)


async def _minute(hass: HomeAssistant, freezer: Any) -> None:
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_last_disconnected_and_why(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when the feed last dropped, and the reason fr24feed gives."""
    set_responses(
        aioclient_mock,
        monitor={
            **MONITOR,
            "feed_status": "disconnected",
            "feed_status_message": "Unable to resolve host",
        },
    )
    assert await setup_integration(hass, mock_config_entry)

    state = _state(hass, "sensor", f"{MOCK_ALIAS}_last_disconnected")
    assert state.state == "2026-11-15T09:05:38+00:00"
    feed = _state(hass, "sensor", f"{MOCK_ALIAS}_feed_status")
    assert feed.attributes["message"] == "Unable to resolve host"


async def test_no_message_while_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the empty message fr24feed writes while fine is left out."""
    set_responses(aioclient_mock, monitor=MONITOR)
    assert await setup_integration(hass, mock_config_entry)
    feed = _state(hass, "sensor", f"{MOCK_ALIAS}_feed_status")
    assert "message" not in feed.attributes


async def test_a_frozen_status_page(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a feeder that answers with a page whose time no longer moves."""
    set_responses(aioclient_mock, monitor=MONITOR)
    assert await setup_integration(hass, mock_config_entry)
    stale = f"{MOCK_ALIAS}_status_stale"
    assert _state(hass, "binary_sensor", stale).state == STATE_OFF

    # Five minutes is not yet frozen
    for _ in range(4):
        await _minute(hass, freezer)
    assert _state(hass, "binary_sensor", stale).state == STATE_OFF
    for _ in range(2):
        await _minute(hass, freezer)
    assert _state(hass, "binary_sensor", stale).state == STATE_ON

    # Moving again, whatever its clock says compared to ours
    set_responses(aioclient_mock, monitor={**MONITOR, "time_update_utc": 1000})
    await _minute(hass, freezer)
    assert _state(hass, "binary_sensor", stale).state == STATE_OFF


async def test_piaware_writes_its_time_in_milliseconds(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test the same for PiAware, whose status page carries its own time."""
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)
    stale = f"{PIAWARE_UNIQUE_ID}_status_stale"
    assert _state(hass, "binary_sensor", stale).state == STATE_OFF
    for _ in range(6):
        await _minute(hass, freezer)
    assert _state(hass, "binary_sensor", stale).state == STATE_ON


async def test_no_sensor_without_a_time_on_the_page(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a build without the field gets no sensor stuck off."""
    assert await setup_integration(hass, mock_config_entry)
    assert _entity_id(hass, "binary_sensor", f"{MOCK_ALIAS}_status_stale") is None
    assert _entity_id(hass, "sensor", f"{MOCK_ALIAS}_last_disconnected") is None


async def test_the_decoder_in_diagnostics(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test what the decoder is and can do, without where the antenna is."""
    set_responses(
        aioclient_mock,
        receiver={
            **MOCK_RECEIVER_READSB,
            "alt_m_amsl": 12,
            "readsb": True,
            "binCraft": True,
            "jaeroTimeout": 33.0,
        },
    )
    assert await setup_integration(hass, mock_receiver_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_receiver_entry)

    receiver = diagnostics["receiver"]
    assert receiver["readsb"] is True
    assert receiver["binCraft"] is True
    assert receiver["refresh"] == 1000
    assert not {"lat", "lon", "alt_m_amsl"} & receiver.keys()
