"""Tests for the passages a station keeps after the board starts over."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station import passage_log
from custom_components.adsb_station.const import CONF_KEEP_PASSAGES, DOMAIN
from custom_components.adsb_station.passage_log import PassageLog, storage_key

from .conftest import set_responses, setup_integration

# About 5.5 km north of home at 52.0, 5.0: inside the default radius.
OVERHEAD = {
    "hex": "484506",
    "flight": "KLM1234",
    "r": "PH-BXA",
    "t": "B738",
    "lat": 52.05,
    "lon": 5.0,
    "alt_baro": 3000,
}


def _sky(*aircraft: dict[str, Any]) -> dict[str, Any]:
    return {"now": 1636387404.0, "messages": 10, "aircraft": list(aircraft)}


def _keep(hass_storage: dict[str, Any], entry_id: str, *passages: Any) -> None:
    hass_storage[storage_key(entry_id)] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key(entry_id),
        "data": {"passages": list(passages)},
    }


def _passage(days_ago: float, hex_code: str) -> dict[str, Any]:
    at = dt_util.utcnow() - timedelta(days=days_ago)
    return {"at": at.isoformat(), "hex": hex_code, "altitude": 2000, "distance": 4.0}


async def _list(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN, "list_passages", data, blocking=True, return_response=True
    )
    assert response is not None
    return dict(response)


async def test_passages_are_kept_and_looked_up(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a passage lands in the file and the action finds it."""
    set_responses(aioclient_mock, aircraft=_sky(OVERHEAD))
    assert await setup_integration(hass, mock_config_entry)

    answer = await _list(hass)
    assert [passage["hex"] for passage in answer["passages"]] == ["484506"]
    passage = answer["passages"][0]
    assert passage["registration"] == "PH-BXA"
    # In the station's units, and named
    assert passage["altitude"] == round(3000 * 0.3048)
    assert answer["altitude_unit"] == "m"
    assert answer["distance_unit"] == "km"

    # By registration, written either way, callsign or hex
    for wanted in ("PH-BXA", "phbxa", "KLM1234", "484506"):
        assert len((await _list(hass, aircraft=wanted))["passages"]) == 1, wanted
    assert (await _list(hass, aircraft="PH-ABC"))["passages"] == []

    # By when it began
    later = dt_util.now() + timedelta(hours=1)
    assert (await _list(hass, start=later.isoformat()))["passages"] == []
    assert len((await _list(hass, end=later.isoformat()))["passages"]) == 1

    # Written on unload, so a reload reads it back
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    kept = hass_storage[storage_key(mock_config_entry.entry_id)]["data"]["passages"]
    assert [entry["hex"] for entry in kept] == ["484506"]


async def test_older_passages_go_and_newest_come_first(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the days kept, counted back from now."""
    _keep(
        hass_storage,
        mock_config_entry.entry_id,
        _passage(40, "aa0001"),
        _passage(20, "aa0002"),
        _passage(2, "aa0003"),
        {"hex": "broken"},
    )
    set_responses(aioclient_mock, aircraft=_sky())
    assert await setup_integration(hass, mock_config_entry)

    answer = await _list(hass)
    assert [passage["hex"] for passage in answer["passages"]] == ["aa0003", "aa0002"]


async def test_none_kept(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that 0 days keeps nothing, removes the file and says so."""
    _keep(hass_storage, mock_config_entry.entry_id, _passage(1, "aa0001"))
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_KEEP_PASSAGES: 0}
    )
    set_responses(aioclient_mock, aircraft=_sky(OVERHEAD))
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(mock_config_entry.entry_id) not in hass_storage

    with pytest.raises(ServiceValidationError) as raised:
        await _list(hass)
    assert raised.value.translation_key == "passages_not_kept"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert storage_key(mock_config_entry.entry_id) not in hass_storage


async def test_a_limit_however_long_they_are_kept(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a busy station drops its oldest beyond the limit."""
    monkeypatch.setattr(passage_log, "MAX_KEPT", 2)
    log = PassageLog(hass, "entry", 365)
    log.note([_passage(3, "aa0001"), _passage(2, "aa0002"), _passage(1, "aa0003")])
    assert [passage["hex"] for passage in log.find()] == ["aa0003", "aa0002"]


async def test_removing_the_station_removes_the_file(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the passages go with the station."""
    set_responses(aioclient_mock, aircraft=_sky(OVERHEAD))
    assert await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert storage_key(mock_config_entry.entry_id) in hass_storage

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(mock_config_entry.entry_id) not in hass_storage
