"""Tests for the ADS-B Station diagnostics."""

from __future__ import annotations

import json

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import CONF_AIRCRAFT_URL, CONF_WATCHLIST
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
    assert diagnostics["feeder"]["feed_alias"] == REDACTED
    assert diagnostics["feeder"]["feed_legacy_id"] == REDACTED
    assert diagnostics["feeder"]["feed_num_ac_tracked"] == 25
    assert diagnostics["aircraft"]["total"] == 3
    assert diagnostics["aircraft"]["with_position"] == 2
    assert diagnostics["aircraft"]["closest"]["hex"] == "484123"
    assert diagnostics["aircraft"]["emergencies"] == []
    assert diagnostics["reception"]["strong_signals"] == 6
    assert diagnostics["reception"]["period"] == "last1min"
    assert diagnostics["range_measured_from"] == [HOME_LATITUDE, HOME_LONGITUDE]
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
    assert diagnostics["feeder"] is None
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


async def test_diagnostics_do_not_give_the_house_away(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that no position in the download is finer than the region.

    Diagnostics are pasted into public issues. The antenna's own position is
    the house, and so, nearly, is an aircraft passing over it.
    """
    set_responses(
        aioclient_mock,
        receiver={**MOCK_RECEIVER_READSB, "lat": 51.98765, "lon": 5.12345},
        aircraft={
            "now": 1636387404.0,
            "messages": 1000,
            "aircraft": [
                # In distress as well, which puts it in the download once more
                {
                    "hex": "484123",
                    "flight": "KLM123",
                    "lat": 51.98812,
                    "lon": 5.12401,
                    "squawk": "7700",
                }
            ],
        },
    )
    assert await setup_integration(hass, mock_receiver_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_receiver_entry)

    assert diagnostics["range_measured_from_source"] == "receiver"
    assert diagnostics["range_measured_from"] == [52.0, 5.1]
    # Not even rounded: beside the exact distance and bearing, a few
    # aircraft would narrow the region down to the house.
    assert diagnostics["aircraft"]["closest"]["position"] is True
    assert diagnostics["aircraft"]["nearby"][0]["position"] is True
    [emergency] = diagnostics["aircraft"]["emergencies"]
    assert emergency["summary"]["position"] is True
    written = json.dumps(diagnostics, default=str)
    for exact in ("51.98", "5.12"):
        assert exact not in written


async def test_diagnostics_count_the_watchlist_rather_than_show_it(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the watchlist says how many lines of which kind, not which."""
    mock_receiver_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_receiver_entry, options={CONF_WATCHLIST: "PH-BXA\n4CA123\n7700"}
    )
    set_responses(aioclient_mock, receiver=MOCK_RECEIVER_READSB)
    assert await hass.config_entries.async_setup(mock_receiver_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_receiver_entry)

    assert diagnostics["entry_options"][CONF_WATCHLIST] == {
        "name": 1,
        "hex": 1,
        "squawk": 1,
    }
    written = json.dumps(diagnostics["entry_options"])
    assert "PH-BXA" not in written
    assert "4CA123" not in written
