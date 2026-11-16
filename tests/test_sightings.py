"""Tests for the aircraft a station has ever heard, and the new ones."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_AIRCRAFT,
)
from custom_components.adsb_station.sightings import storage_key

from .conftest import MOCK_ALIAS, set_responses, setup_integration


def _sky(*aircraft: dict[str, Any]) -> dict[str, Any]:
    return {"now": 1636387404.0, "messages": 10, "aircraft": list(aircraft)}


KLM = {"hex": "484506", "flight": "KLM1234", "t": "B738", "r": "PH-BXA"}
SUPERJUMBO = {"hex": "896180", "flight": "UAE147", "t": "A388", "r": "A6-EOA"}
NOT_ICAO = {"hex": "~2a4f01", "flight": "TISB1"}


def _today() -> int:
    return dt_util.now().date().toordinal()


def _keep(hass_storage: dict[str, Any], entry_id: str, **data: Any) -> None:
    hass_storage[storage_key(entry_id)] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key(entry_id),
        "data": data,
    }


def _kept(hass_storage: dict[str, Any], entry_id: str) -> dict[str, Any]:
    return hass_storage[storage_key(entry_id)]["data"]


def _count(hass: HomeAssistant) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_aircraft_ever_heard"
    )
    assert entity_id is not None
    return hass.states.get(entity_id)


async def _poll(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: Any, sky: Any
) -> None:
    set_responses(aioclient_mock, aircraft=sky)
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_the_first_week_only_collects(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a new station keeps what it hears, quietly, and writes it."""
    events = async_capture_events(hass, EVENT_NEW_AIRCRAFT)
    set_responses(aioclient_mock, aircraft=_sky(KLM, SUPERJUMBO, NOT_ICAO))
    assert await setup_integration(hass, mock_config_entry)

    state = _count(hass)
    # Only aircraft with an ICAO address are airframes to keep
    assert state.state == "2"
    assert state.attributes["since"] == date.fromordinal(_today()).isoformat()
    assert state.attributes["types"] == 2
    assert state.attributes["airlines"] == 2
    assert events == []

    # Kept on unload, so a reload does not read a file a quarter behind
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    kept = _kept(hass_storage, mock_config_entry.entry_id)
    assert set(kept["aircraft"]) == {"484506", "896180"}
    assert kept["aircraft"]["484506"] == [_today(), _today(), 1]
    assert kept["types"] == ["A388", "B738"]
    assert kept["airlines"] == ["KLM", "UAE"]


async def test_a_new_aircraft_is_announced_once(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test the event, with whether it is the first of its type or airline."""
    today = _today()
    _keep(
        hass_storage,
        mock_config_entry.entry_id,
        since=today - 30,
        aircraft={"484506": [today - 30, today - 2, 9]},
        types=["B738"],
        airlines=["KLM", "UAE"],
    )
    events = async_capture_events(hass, EVENT_NEW_AIRCRAFT)
    set_responses(aioclient_mock, aircraft=_sky(KLM))
    assert await setup_integration(hass, mock_config_entry)
    assert events == []

    await _poll(hass, aioclient_mock, freezer, _sky(KLM, SUPERJUMBO))
    await _poll(hass, aioclient_mock, freezer, _sky(KLM, SUPERJUMBO))

    assert len(events) == 1
    data = events[0].data
    assert data["hex"] == "896180"
    assert data["registration"] == "A6-EOA"
    assert data["first_of_type"] is True
    assert data["first_of_airline"] is False
    assert data["entry_id"] == mock_config_entry.entry_id
    assert _count(hass).state == "2"


async def test_days_heard_and_forgetting_after_a_year(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a day counted once, and one not heard for a year let go."""
    today = _today()
    _keep(
        hass_storage,
        mock_config_entry.entry_id,
        since=today - 500,
        aircraft={
            "484506": [today - 400, today - 1, 30],
            "4ca123": [today - 450, today - 366, 2],
        },
        types=[],
        airlines=[],
    )
    set_responses(aioclient_mock, aircraft=_sky(KLM))
    assert await setup_integration(hass, mock_config_entry)
    await _poll(hass, aioclient_mock, freezer, _sky(KLM))
    assert _count(hass).state == "1"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert _kept(hass_storage, mock_config_entry.entry_id)["aircraft"] == {
        "484506": [today - 400, today, 31]
    }


async def test_a_damaged_file_starts_over(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that entries that make no sense are left out, not a failure."""
    _keep(
        hass_storage,
        mock_config_entry.entry_id,
        since="yesterday",
        aircraft={"484506": "often", "4ca123": [1, 2]},
    )
    set_responses(aioclient_mock, aircraft=_sky())
    assert await setup_integration(hass, mock_config_entry)
    assert _count(hass).state == "0"


async def test_removing_the_station_removes_the_file(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that nothing of a removed station stays behind."""
    set_responses(aioclient_mock, aircraft=_sky(KLM))
    assert await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert storage_key(mock_config_entry.entry_id) in hass_storage

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(mock_config_entry.entry_id) not in hass_storage
