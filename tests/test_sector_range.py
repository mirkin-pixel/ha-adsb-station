"""Tests for the range records the ADS-B Station keeps per compass sector."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DEFAULT_SCAN_INTERVAL, DOMAIN, SECTORS
from custom_components.adsb_station.coordinator import sector_of

from .conftest import MOCK_ALIAS, set_responses, setup_integration

# Home sits at 52.0, 5.0. These three are due north, due east and due south of
# it, at distances that make the assertions readable.
AIRCRAFT_AROUND_US = {
    "now": 1636387404.0,
    "messages": 10,
    "aircraft": [
        {"hex": "aa0001", "flight": "NORTH1", "lat": 53.0, "lon": 5.0},
        {"hex": "aa0002", "flight": "EAST1", "lat": 52.0, "lon": 6.0},
        {"hex": "aa0003", "flight": "SOUTH1", "lat": 51.5, "lon": 5.0},
    ],
}


def _state(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None, key
    return hass.states.get(entity_id).state


def _attributes(hass: HomeAssistant, key: str) -> dict:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None, key
    return dict(hass.states.get(entity_id).attributes)


def test_every_bearing_lands_in_a_sector() -> None:
    """Test that the whole compass is covered exactly once."""
    seen = {sector_of(float(degrees)) for degrees in range(360)}
    assert seen == set(SECTORS)
    # Each sector is centred on its direction rather than starting at it
    assert sector_of(0.0) == "n"
    assert sector_of(22.4) == "n"
    assert sector_of(22.6) == "ne"
    assert sector_of(337.6) == "n"
    assert sector_of(359.9) == "n"


async def test_records_are_kept_per_sector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that each direction gets its own record."""
    set_responses(aioclient_mock, aircraft=AIRCRAFT_AROUND_US)

    assert await setup_integration(hass, mock_config_entry)

    # Metres natively, but the sensors suggest kilometres, so states are km.
    # One degree of latitude is about 111 km, half a degree about 55.6.
    assert float(_state(hass, "max_range_n")) == pytest.approx(111.2, rel=0.01)
    assert float(_state(hass, "max_range_e")) == pytest.approx(68.5, rel=0.02)
    assert float(_state(hass, "max_range_s")) == pytest.approx(55.6, rel=0.01)
    assert _attributes(hass, "max_range_n")["flight"] == "NORTH1"
    assert _attributes(hass, "max_range_n")["recorded_at"] is not None

    # Nothing was heard in the other five, and they are still readable
    for sector in ("ne", "se", "sw", "w", "nw"):
        assert _state(hass, f"max_range_{sector}") == STATE_UNKNOWN


async def test_a_record_only_ever_grows(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a closer aircraft later does not lower the record."""
    set_responses(aioclient_mock, aircraft=AIRCRAFT_AROUND_US)
    assert await setup_integration(hass, mock_config_entry)
    record = float(_state(hass, "max_range_n"))

    # The same direction, but half as far away
    set_responses(
        aioclient_mock,
        aircraft={
            **AIRCRAFT_AROUND_US,
            "aircraft": [
                {"hex": "aa0009", "flight": "NEARER", "lat": 52.5, "lon": 5.0}
            ],
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert float(_state(hass, "max_range_n")) == pytest.approx(record)
    assert _attributes(hass, "max_range_n")["flight"] == "NORTH1"


async def test_a_record_survives_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a record set before a restart is still there after it."""
    entity_id = "sensor.t_ehxx23_maximum_range_north"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "250000"),
                {
                    "distance": 250_000.0,
                    "recorded_at": "2026-01-01T12:00:00+00:00",
                    "flight": "OLDREC",
                    "hex": "aa9999",
                },
            )
        ],
    )
    # Nothing in range now, so only the restored record can supply a value
    set_responses(aioclient_mock, aircraft={"now": 1.0, "messages": 1, "aircraft": []})

    assert await setup_integration(hass, mock_config_entry)

    assert float(_state(hass, "max_range_n")) == pytest.approx(250.0)
    assert _attributes(hass, "max_range_n")["flight"] == "OLDREC"


async def test_reset_button_clears_every_sector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the button wipes the records, for when the antenna moved."""
    set_responses(aioclient_mock, aircraft=AIRCRAFT_AROUND_US)
    assert await setup_integration(hass, mock_config_entry)
    assert _state(hass, "max_range_n") != STATE_UNKNOWN

    # Empty the sky first. Resetting with the same aircraft still in view sets
    # a fresh record from them straight away, which is right but invisible.
    set_responses(aioclient_mock, aircraft={"now": 2.0, "messages": 2, "aircraft": []})
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)
    )
    await hass.async_block_till_done()
    # The record outlives the aircraft that set it
    assert _state(hass, "max_range_n") != STATE_UNKNOWN

    button_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{MOCK_ALIAS}_reset_range"
    )
    assert button_id is not None
    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )
    await hass.async_block_till_done()

    for sector in SECTORS:
        assert _state(hass, f"max_range_{sector}") == STATE_UNKNOWN
