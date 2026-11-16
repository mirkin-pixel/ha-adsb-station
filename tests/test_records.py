"""Tests for the furthest, highest and fastest aircraft a station has heard."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_RECORD_BROKEN,
    SECTORS,
)

from .conftest import MOCK_ALIAS, metres, set_responses, setup_integration


def _sky(*aircraft: dict[str, Any]) -> dict[str, Any]:
    return {"now": 1636387404.0, "messages": 10, "aircraft": list(aircraft)}


def _plane(
    altitude: float = 30_000, speed: float = 400, hex_code: str = "aa0001", **more: Any
) -> dict[str, Any]:
    # Due north of home at 52.0, 5.0, about 11 km away.
    return {
        "hex": hex_code,
        "flight": f"F{hex_code}",
        "lat": 52.1,
        "lon": 5.0,
        "alt_baro": altitude,
        "gs": speed,
        **more,
    }


def _entity_id(hass: HomeAssistant, domain: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None, key
    return entity_id


def _state(hass: HomeAssistant, key: str) -> State:
    state = hass.states.get(_entity_id(hass, "sensor", key))
    assert state is not None
    return state


class Poller:
    """Feeds the station one sky after another, each on its own poll.

    With the freezer the clock moves as well, as the records read it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        aioclient_mock: AiohttpClientMocker,
        freezer: Any = None,
    ) -> None:
        self._hass = hass
        self._mock = aioclient_mock
        self._freezer = freezer
        self._at = dt_util.utcnow()

    async def __call__(
        self,
        sky: dict[str, Any],
        after: timedelta = timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5),
    ) -> None:
        set_responses(self._mock, aircraft=sky)
        if self._freezer is None:
            self._at += after
            async_fire_time_changed(self._hass, self._at)
        else:
            self._freezer.tick(after)
            async_fire_time_changed(self._hass)
        await self._hass.async_block_till_done()


def _restore(hass: HomeAssistant, key: str, value: float, since: datetime) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(f"sensor.t_ehxx23_{key}", str(value)),
                {
                    "value": value,
                    "recorded_at": since.isoformat(),
                    "details": {"hex": "old001", "flight": "OLD1", "altitude": value},
                    "since": since.isoformat(),
                },
            )
        ],
    )


async def test_a_figure_counts_once_heard_twice_in_a_row(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that one garbled message cannot become a record that stands."""
    set_responses(aioclient_mock, aircraft=_sky(_plane(30_000)))
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)
    # Heard once is not yet a record
    assert _state(hass, "altitude_record").state == STATE_UNKNOWN

    await poll(_sky(_plane(30_000)))
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(30_000), abs=1
    )

    # A height reported once, between two ordinary ones, never counts
    await poll(_sky(_plane(90_000)))
    await poll(_sky(_plane(30_000)))
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(30_000), abs=1
    )

    attributes = _state(hass, "altitude_record").attributes
    assert attributes["flight"] == "Faa0001"
    assert attributes["altitude"] == metres(30_000)
    assert attributes["altitude_unit"] == "m"
    assert attributes["recorded_at"] is not None


async def test_records_for_range_altitude_and_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that each count has its own aircraft, and only ever grows."""
    far = {"lat": 53.0, "lon": 5.0, "flight": "FAR1"}
    sky = _sky(
        _plane(41_000, 380, "aa0001"),
        _plane(20_000, 520, "aa0002"),
        _plane(10_000, 250, "aa0003", **far),
    )
    set_responses(aioclient_mock, aircraft=sky)
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)
    await poll(sky)

    assert float(_state(hass, "range_record").state) == pytest.approx(111.2, rel=0.01)
    assert _state(hass, "range_record").attributes["flight"] == "FAR1"
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(41_000), abs=1
    )
    # 520 kt in km/h
    assert float(_state(hass, "speed_record").state) == pytest.approx(963, abs=1)
    assert _state(hass, "speed_record").attributes["hex"] == "aa0002"

    # Lower figures later leave the records standing
    await poll(_sky(_plane(5_000, 120, "aa0004")))
    await poll(_sky(_plane(5_000, 120, "aa0004")))
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(41_000), abs=1
    )
    assert _state(hass, "speed_record").attributes["hex"] == "aa0002"


async def test_on_the_ground_sets_no_record(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a fast take-off run or a ground speed glitch is not a record."""
    taxiing = _plane("ground", 600)
    set_responses(aioclient_mock, aircraft=_sky(taxiing))
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)
    await poll(_sky(taxiing))
    assert _state(hass, "speed_record").state == STATE_UNKNOWN


async def test_the_first_day_breaks_records_quietly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a fresh station does not announce every aircraft it hears."""
    events = async_capture_events(hass, EVENT_RECORD_BROKEN)
    set_responses(aioclient_mock, aircraft=_sky(_plane(30_000)))
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)
    for feet in (30_000, 31_000, 32_000, 32_000, 33_000, 33_000, 33_000):
        await poll(_sky(_plane(feet)))
    await poll(_sky())

    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(33_000), abs=1
    )
    assert events == []


async def test_an_aircraft_setting_a_record_is_announced_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test one event per flight, once it has settled, with its best."""
    _restore(hass, "altitude_record", 40_000, dt_util.utcnow() - timedelta(days=3))
    events = async_capture_events(hass, EVENT_RECORD_BROKEN)
    set_responses(aioclient_mock, aircraft=_sky(_plane(41_000)))
    assert await setup_integration(hass, mock_config_entry)
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(40_000), abs=1
    )
    poll = Poller(hass, aioclient_mock, freezer)

    # Climbing past the record, poll after poll, then level: no news yet
    for feet in (42_000, 43_000, 43_000, 43_000):
        await poll(_sky(_plane(feet)))
    assert events == []
    # Five minutes without bettering it settles the record
    await poll(_sky(_plane(43_000)), after=timedelta(minutes=5))

    assert len(events) == 1
    data = events[0].data
    assert data["record"] == "altitude"
    assert data["hex"] == "aa0001"
    assert data["altitude"] == metres(43_000)
    assert data["altitude_unit"] == "m"
    assert data["entry_id"] == mock_config_entry.entry_id
    assert data["previous"]["altitude"] == metres(40_000)
    assert data["previous"]["flight"] == "OLD1"

    # A ground speed or height that wavers up a little later is the same
    # flight: the record follows it, without another message
    await poll(_sky(_plane(43_100)))
    await poll(_sky(_plane(43_100)))
    await poll(_sky())
    assert len(events) == 1
    assert float(_state(hass, "altitude_record").state) == pytest.approx(
        metres(43_100), abs=1
    )

    event_state = hass.states.get(_entity_id(hass, "event", "records"))
    assert event_state is not None
    assert event_state.attributes["event_type"] == "altitude"


async def test_a_second_aircraft_is_a_second_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a record beaten again by another aircraft is news again.

    The first is announced as soon as the second beats it, the second once
    it is gone.
    """
    _restore(hass, "altitude_record", 40_000, dt_util.utcnow() - timedelta(days=3))
    events = async_capture_events(hass, EVENT_RECORD_BROKEN)
    set_responses(aioclient_mock, aircraft=_sky(_plane(41_000)))
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)

    await poll(_sky(_plane(41_000)))
    await poll(_sky(_plane(41_000), _plane(45_000, hex_code="bb0002")))
    assert events == []
    await poll(_sky(_plane(41_000), _plane(45_000, hex_code="bb0002")))
    assert [event.data["hex"] for event in events] == ["aa0001"]
    await poll(_sky(_plane(41_000)))

    assert [event.data["hex"] for event in events] == ["aa0001", "bb0002"]
    assert events[1].data["previous"]["hex"] == "aa0001"


async def test_a_record_survives_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a record set before a restart is still there after it."""
    _restore(hass, "altitude_record", 44_000, dt_util.utcnow() - timedelta(days=9))
    set_responses(aioclient_mock, aircraft=_sky())
    assert await setup_integration(hass, mock_config_entry)

    state = _state(hass, "altitude_record")
    assert float(state.state) == pytest.approx(metres(44_000), abs=1)
    assert state.attributes["flight"] == "OLD1"


async def test_the_reset_button_clears_every_record(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test one button for all of them, for after a new antenna."""
    set_responses(aioclient_mock, aircraft=_sky(_plane()))
    assert await setup_integration(hass, mock_config_entry)
    poll = Poller(hass, aioclient_mock)
    await poll(_sky(_plane()))
    await poll(_sky())
    for key in ("range_record", "altitude_record", "speed_record", "max_range_n"):
        assert _state(hass, key).state != STATE_UNKNOWN, key

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": _entity_id(hass, "button", "reset_range")},
        blocking=True,
    )

    for key in (
        "range_record",
        "altitude_record",
        "speed_record",
        *(f"max_range_{sector}" for sector in SECTORS),
    ):
        assert _state(hass, key).state == STATE_UNKNOWN, key
