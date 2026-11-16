"""Tests for a bad tuner and readsb's connections to the networks it feeds."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.api import parse_connectors
from custom_components.adsb_station.const import DOMAIN

from .conftest import (
    MOCK_STATS,
    PROMETHEUS_URL,
    RECEIVER_UNIQUE_ID,
    set_responses,
    setup_integration,
)

# As readsb writes it, around two of its lines.
PROMETHEUS = """readsb_messages_valid 52549019
readsb_net_connector_status{host="feed.adsb.fi",port="30004"} 3600
readsb_net_connector_status{host="feed.airplanes.live",port="30004"} 0
readsb_sdr_gain 49.6
"""


def _connection(hass: HomeAssistant, key: str) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{RECEIVER_UNIQUE_ID}_connector_{key}"
    )
    assert entity_id is not None, key
    return hass.states.get(entity_id)


async def _minute(hass: HomeAssistant, freezer: Any) -> None:
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def test_reading_the_connections() -> None:
    """Test each connection, up while it has been up for some seconds."""
    assert parse_connectors(PROMETHEUS) == {
        "feed.adsb.fi:30004": True,
        "feed.airplanes.live:30004": False,
    }
    assert parse_connectors("readsb_messages_valid 1\n") == {}


async def test_a_sensor_per_connection(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test one per network, one added later, and one no longer listed."""
    set_responses(aioclient_mock, prometheus=PROMETHEUS)
    assert await setup_integration(hass, mock_receiver_entry)

    adsbfi = _connection(hass, "feed_adsb_fi_30004")
    assert adsbfi.state == STATE_ON
    assert adsbfi.name.endswith("Connection feed.adsb.fi:30004")
    assert _connection(hass, "feed_airplanes_live_30004").state == STATE_OFF

    set_responses(
        aioclient_mock,
        prometheus='readsb_net_connector_status{host="in.adsb.lol",port="30004"} 12\n'
        'readsb_net_connector_status{host="feed.adsb.fi",port="30004"} 3660\n',
    )
    await _minute(hass, freezer)

    assert _connection(hass, "in_adsb_lol_30004").state == STATE_ON
    assert _connection(hass, "feed_adsb_fi_30004").state == STATE_ON
    assert _connection(hass, "feed_airplanes_live_30004").state == STATE_UNAVAILABLE


async def test_a_missed_read_keeps_the_connections(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a page that cannot be read for a moment changes nothing."""
    set_responses(aioclient_mock, prometheus=PROMETHEUS)
    assert await setup_integration(hass, mock_receiver_entry)
    set_responses(aioclient_mock, prometheus_kwargs={"status": 500})
    await _minute(hass, freezer)
    assert _connection(hass, "feed_adsb_fi_30004").state == STATE_ON
    set_responses(aioclient_mock, prometheus_kwargs={"exc": TimeoutError()})
    await _minute(hass, freezer)
    assert _connection(hass, "feed_adsb_fi_30004").state == STATE_ON


async def test_a_decoder_without_stats_prom_is_not_asked_again(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that dump1090-fa, which serves none, is asked once."""
    set_responses(aioclient_mock)
    assert await setup_integration(hass, mock_receiver_entry)
    await _minute(hass, freezer)
    await _minute(hass, freezer)

    asked = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == PROMETHEUS_URL
    ]
    assert len(asked) == 1
    registry = er.async_get(hass)
    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            registry, mock_receiver_entry.entry_id
        )
        if "_connector_" in entry.unique_id
    ]


async def test_a_bad_tuner(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test the repair while readsb reports one, gone once it no longer does."""
    issue_id = f"bad_tuner_{mock_receiver_entry.entry_id}"
    set_responses(aioclient_mock, stats={**MOCK_STATS, "bad_tuner": True})
    assert await setup_integration(hass, mock_receiver_entry)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "bad_tuner"
    assert issue.translation_placeholders == {"station": mock_receiver_entry.title}

    # Another dongle
    set_responses(aioclient_mock)
    await _minute(hass, freezer)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

    # And with the station when it unloads
    set_responses(aioclient_mock, stats={**MOCK_STATS, "bad_tuner": True})
    await _minute(hass, freezer)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_unload(mock_receiver_entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
