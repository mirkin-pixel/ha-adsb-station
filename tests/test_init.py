"""Tests for the ADS-B Station integration setup."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_LOOK_UP_ROUTES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROUTESET_URL,
)

from .conftest import (
    AIRCRAFT_URL,
    ANTENNA_LATITUDE,
    ANTENNA_LONGITUDE,
    MOCK_ALIAS,
    MOCK_HOST,
    MOCK_RECEIVER_READSB,
    MOCK_RECEIVER_VERSION,
    RECEIVER_UNIQUE_ID,
    STATS_URL,
    set_responses,
    setup_integration,
)

REFRESH = timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)


async def _refresh(hass: HomeAssistant) -> None:
    """Advance time past one update interval."""
    async_fire_time_changed(hass, dt_util.utcnow() + REFRESH)
    await hass.async_block_till_done()


def _state(
    hass: HomeAssistant, platform: str, key: str, device_id: str = MOCK_ALIAS
) -> str | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{device_id}_{key}"
    )
    if entity_id is None:
        return None
    return hass.states.get(entity_id).state


def _receiver_state(hass: HomeAssistant, platform: str, key: str) -> str | None:
    """Return the state of an entity on a station without a feeder."""
    return _state(hass, platform, key, device_id=RECEIVER_UNIQUE_ID)


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test a successful setup and unload."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "monitor_kwargs",
    [
        {"exc": aiohttp.ClientError("boom")},
        {"exc": TimeoutError},
        {"status": 500},
        {"json": ["not", "a", "dict"]},
        {"json": {"something": "else"}},
    ],
)
async def test_setup_retries_on_a_broken_feeder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    monitor_kwargs: dict,
) -> None:
    """Test that an unreachable or unrecognised feeder leads to a retry."""
    set_responses(aioclient_mock, monitor_kwargs=monitor_kwargs)

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_without_aircraft_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the aircraft entities are skipped when no URL is configured."""
    set_responses(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_AIRCRAFT_URL: None},
    )

    assert await setup_integration(hass, entry)

    assert _state(hass, "sensor", "aircraft_tracked") == "25"
    assert _state(hass, "sensor", "aircraft_received") is None
    assert _state(hass, "sensor", "max_range") is None


async def test_receiver_outage_is_reported_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failing receiver degrades instead of taking the feeder down."""
    caplog.set_level(logging.INFO)
    assert await setup_integration(hass, mock_config_entry)
    assert _state(hass, "sensor", "aircraft_received") == "3"

    set_responses(mock_api, aircraft_kwargs={"exc": aiohttp.ClientError("boom")})
    await _refresh(hass)

    # The feeder keeps working, only the receiver entities drop out
    assert _state(hass, "sensor", "aircraft_tracked") == "25"
    assert _state(hass, "sensor", "aircraft_received") == STATE_UNAVAILABLE
    assert caplog.text.count(f"Could not read {AIRCRAFT_URL}") == 1

    # A second failure does not warn again
    await _refresh(hass)
    assert caplog.text.count(f"Could not read {AIRCRAFT_URL}") == 1

    # Recovery is logged, and a later relapse warns again
    set_responses(mock_api)
    await _refresh(hass)
    assert _state(hass, "sensor", "aircraft_received") == "3"
    assert f"{AIRCRAFT_URL} can be read again" in caplog.text

    set_responses(mock_api, aircraft_kwargs={"exc": aiohttp.ClientError("boom")})
    await _refresh(hass)
    assert caplog.text.count(f"Could not read {AIRCRAFT_URL}") == 2


async def test_feeder_outage_marks_everything_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that entities become unavailable when the feeder cannot be read."""
    assert await setup_integration(hass, mock_config_entry)
    assert _state(hass, "sensor", "aircraft_tracked") == "25"

    set_responses(mock_api, monitor_kwargs={"exc": aiohttp.ClientError("boom")})
    await _refresh(hass)

    assert _state(hass, "sensor", "aircraft_tracked") == STATE_UNAVAILABLE
    assert _state(hass, "binary_sensor", "receiver") == STATE_UNAVAILABLE
    assert _state(hass, "sensor", "aircraft_received") == STATE_UNAVAILABLE


async def test_changing_the_scan_interval_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that new options are picked up by the coordinator."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.update_interval == timedelta(
        seconds=DEFAULT_SCAN_INTERVAL
    )

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.update_interval == timedelta(seconds=60)


async def test_setup_without_a_feeder(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test a station that runs a decoder but no fr24feed.

    This is the FlightAware and Plane Finder case: everything derived from the
    receiver works, and none of the feed entities are created at all.
    """
    assert await setup_integration(hass, mock_receiver_entry)
    assert mock_receiver_entry.state is ConfigEntryState.LOADED

    assert _receiver_state(hass, "sensor", "aircraft_received") == "3"
    assert _receiver_state(hass, "sensor", "aircraft_with_position") == "2"
    assert _receiver_state(hass, "sensor", "strong_signals") == "6"
    assert _receiver_state(hass, "binary_sensor", "emergency") == "off"

    # Nothing that comes from monitor.json exists here
    assert _receiver_state(hass, "sensor", "aircraft_tracked") is None
    assert _receiver_state(hass, "sensor", "feed_alias") is None
    assert _receiver_state(hass, "sensor", "cpu_temperature") is None
    assert _receiver_state(hass, "binary_sensor", "receiver") is None
    assert _receiver_state(hass, "binary_sensor", "feed") is None
    assert _receiver_state(hass, "binary_sensor", "mlat") is None

    # And the feeder is never polled
    assert not [call for call in mock_api.mock_calls if "monitor.json" in str(call[1])]


async def test_receiver_only_device_has_no_manufacturer(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a bare decoder is not presented as a Flightradar24 device."""
    set_responses(aioclient_mock, receiver=MOCK_RECEIVER_READSB)

    assert await setup_integration(hass, mock_receiver_entry)

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, RECEIVER_UNIQUE_ID)}
    )
    assert device is not None
    assert device.manufacturer is None
    assert device.model == "ADS-B receiver"
    assert device.name == "ADS-B station"
    # readsb reports its version in receiver.json, unlike the fr24feed fork
    assert device.sw_version == MOCK_RECEIVER_VERSION
    assert device.configuration_url == f"http://{MOCK_HOST}:8080/dump1090/"

    # And a decoder that publishes its position is measured from the antenna
    assert mock_receiver_entry.runtime_data.origin == (
        ANTENNA_LATITUDE,
        ANTENNA_LONGITUDE,
    )


async def test_receiver_outage_without_a_feeder_retries(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an unreachable decoder is fatal when it is the only source."""
    set_responses(aioclient_mock, aircraft_kwargs={"exc": aiohttp.ClientError("boom")})

    assert not await setup_integration(hass, mock_receiver_entry)
    assert mock_receiver_entry.state is ConfigEntryState.SETUP_RETRY


async def test_receiver_outage_without_a_feeder_marks_unavailable(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a decoder dropping out later takes its entities down."""
    assert await setup_integration(hass, mock_receiver_entry)
    assert _receiver_state(hass, "sensor", "aircraft_received") == "3"

    set_responses(mock_api, aircraft_kwargs={"exc": aiohttp.ClientError("boom")})
    await _refresh(hass)

    assert _receiver_state(hass, "sensor", "aircraft_received") == STATE_UNAVAILABLE
    assert _receiver_state(hass, "sensor", "strong_signals") == STATE_UNAVAILABLE

    set_responses(mock_api)
    await _refresh(hass)
    assert _receiver_state(hass, "sensor", "aircraft_received") == "3"


async def test_statistics_outage_is_reported_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failing stats.json only takes the statistics down."""
    caplog.set_level(logging.INFO)
    assert await setup_integration(hass, mock_config_entry)
    assert _state(hass, "sensor", "strong_signals") == "6"

    set_responses(mock_api, stats_kwargs={"status": 500})
    await _refresh(hass)

    assert _state(hass, "sensor", "aircraft_received") == "3"
    assert _state(hass, "sensor", "strong_signals") == STATE_UNAVAILABLE
    assert caplog.text.count(f"Could not read {STATS_URL}") == 1

    await _refresh(hass)
    assert caplog.text.count(f"Could not read {STATS_URL}") == 1

    set_responses(mock_api)
    await _refresh(hass)
    assert _state(hass, "sensor", "strong_signals") == "6"
    assert f"{STATS_URL} can be read again" in caplog.text


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        # Either source meant "yes, look them up", and one of the two is gone
        ("routeset", True),
        ("adsbdb", True),
        ("none", False),
        (None, False),
    ],
)
async def test_migration_keeps_the_answer_to_the_route_question(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    stored: str | None,
    expected: bool,
) -> None:
    """Test that an entry naming a route source becomes a yes or a no.

    The setting used to be a choice between two databases and is now a switch,
    so anyone who picked either source has to come out of the upgrade still
    getting routes, without being asked again.
    """
    mock_api.post(ROUTESET_URL, json=[])
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=mock_config_entry.unique_id,
        data=dict(mock_config_entry.data),
        options={CONF_SCAN_INTERVAL: 15, "route_source": stored},
    )

    assert await setup_integration(hass, entry)

    assert entry.version == 3
    assert entry.options[CONF_LOOK_UP_ROUTES] is expected
    assert "route_source" not in entry.options
    assert (entry.runtime_data.route_lookup is not None) is expected
