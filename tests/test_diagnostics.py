"""Tests for the ADS-B Station diagnostics."""

from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import CONF_AIRCRAFT_URL
from custom_components.adsb_station.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import (
    HOME_LATITUDE,
    HOME_LONGITUDE,
    MOCK_RECEIVER_READSB,
    MOCK_RECEIVER_VERSION,
    set_responses,
    setup_integration,
)


async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the address and the feed alias are redacted."""
    assert await setup_integration(hass, mock_config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry_data"][CONF_HOST] == REDACTED
    assert diagnostics["entry_data"][CONF_AIRCRAFT_URL] == REDACTED
    assert diagnostics["monitor"]["feed_alias"] == REDACTED
    assert diagnostics["monitor"]["feed_num_ac_tracked"] == 25
    assert diagnostics["aircraft"]["total"] == 3
    assert diagnostics["aircraft"]["with_position"] == 2
    assert diagnostics["aircraft"]["closest"]["hex"] == "484123"
    assert diagnostics["aircraft"]["emergencies"] == ()
    assert diagnostics["reception"]["strong_signals"] == 6
    assert diagnostics["reception"]["period"] == "last1min"
    assert diagnostics["range_measured_from"] == (HOME_LATITUDE, HOME_LONGITUDE)
    # This receiver.json carries no position, so the fallback is in use
    assert diagnostics["range_measured_from_source"] == "home_location"
    assert diagnostics["has_feeder"] is True
    # The fr24feed fork never expands the placeholder in its receiver.json
    assert diagnostics["receiver_version"] is None


async def test_diagnostics_without_a_feeder(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the diagnostics of a station that runs no fr24feed."""
    set_responses(aioclient_mock, receiver=MOCK_RECEIVER_READSB)

    assert await setup_integration(hass, mock_receiver_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_receiver_entry)
    assert diagnostics["has_feeder"] is False
    assert diagnostics["monitor"] is None
    assert diagnostics["receiver_version"] == MOCK_RECEIVER_VERSION
    assert diagnostics["aircraft"]["total"] == 3
    # readsb publishes its antenna position, so ranges come off that
    assert diagnostics["range_measured_from_source"] == "receiver"


async def test_diagnostics_without_receiver_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the diagnostics while the receiver is unreachable."""
    set_responses(
        aioclient_mock,
        aircraft_kwargs={"status": 404},
        stats_kwargs={"status": 404},
    )

    assert await setup_integration(hass, mock_config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics["aircraft"] is None
    assert diagnostics["reception"] is None
