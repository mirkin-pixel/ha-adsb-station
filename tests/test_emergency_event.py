"""Tests for the event fired when an aircraft in range is in distress."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    EVENT_AIRCRAFT_EMERGENCY,
    MAX_SCAN_INTERVAL,
    PASSAGE_GAP,
)

from .conftest import set_responses, setup_integration
from .test_passages import next_poll, poll

# Home is 52.0, 5.0: a tenth of a degree north is 11.1 km, and at cruising
# height, far outside any passage radius or ceiling.
DISTRESS = {
    "hex": "4ca123",
    "flight": "RYR1YY",
    "lat": 52.1,
    "lon": 5.0,
    "alt_baro": 37000,
    "t": "B738",
    "squawk": "7700",
}
QUIET = {**DISTRESS, "squawk": "1000"}


@pytest.fixture
def emergencies(hass: HomeAssistant) -> list[Event]:
    """Collect every emergency event fired during a test."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_AIRCRAFT_EMERGENCY, events.append)
    return events


async def _then(
    hass: HomeAssistant,
    freezer: Any,
    aioclient_mock: AiohttpClientMocker,
    *aircraft: dict[str, Any],
    after: timedelta | None = None,
) -> None:
    set_responses(aioclient_mock, aircraft=poll(*aircraft))
    await next_poll(hass, freezer, after)


async def test_an_emergency_is_announced(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test the event, at any distance and height, with what it is and where."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)

    [event] = emergencies
    assert event.data["entry_id"] == mock_config_entry.entry_id
    assert event.data["station"] == mock_config_entry.title
    assert event.data["reason"] == "emergency"
    assert event.data["squawk"] == "7700"
    assert event.data["hex"] == "4ca123"
    assert event.data["flight"] == "RYR1YY"
    assert event.data["distance"] == 11.1
    assert event.data["altitude"] == 37000
    assert event.data["aircraft_type"] == "B738"


async def test_the_status_counts_under_the_same_reason(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test readsb's own word for it, said the way the squawk says it."""
    hijacked = {**QUIET, "emergency": "unlawful"}
    set_responses(aioclient_mock, aircraft=poll(hijacked))
    assert await setup_integration(hass, mock_config_entry)

    [event] = emergencies
    assert event.data["reason"] == "hijack"
    assert event.data["squawk"] == "1000"


async def test_an_ambulance_flight_is_no_emergency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test that asking for priority, or low on fuel, is not announced."""
    set_responses(
        aioclient_mock,
        aircraft=poll(
            {**QUIET, "emergency": "lifeguard"},
            {**QUIET, "hex": "4ca124", "emergency": "minfuel"},
        ),
    )
    assert await setup_integration(hass, mock_config_entry)

    assert emergencies == []


async def test_one_flight_is_one_event(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test an aircraft in distress for an hour, then gone and back."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)

    for _ in range(60):
        await _then(hass, freezer, aioclient_mock, DISTRESS, after=timedelta(minutes=1))
    assert len(emergencies) == 1

    # Gone for longer than the gap, then back still in distress
    await _then(hass, freezer, aioclient_mock, after=PASSAGE_GAP)
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=1))
    await _then(hass, freezer, aioclient_mock, DISTRESS)
    assert len(emergencies) == 2


async def test_a_new_emergency_on_the_same_flight_is_not_repeated(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test a squawk that drops for a poll: still the same emergency."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)

    await _then(hass, freezer, aioclient_mock, QUIET)
    await _then(hass, freezer, aioclient_mock, DISTRESS)
    assert len(emergencies) == 1


async def test_two_aircraft_are_two_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test that one emergency does not hide another."""
    second = {**DISTRESS, "hex": "4ca124", "flight": "BOX116", "squawk": "7600"}
    set_responses(aioclient_mock, aircraft=poll(DISTRESS, second))
    assert await setup_integration(hass, mock_config_entry)

    assert [event.data["reason"] for event in emergencies] == [
        "emergency",
        "radio_failure",
    ]


async def test_the_slowest_interval_is_still_one_event(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    emergencies: list[Event],
) -> None:
    """Test polls a little further apart than the gap, as they are in practice."""
    set_responses(aioclient_mock, aircraft=poll(DISTRESS))
    assert await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.update_interval = timedelta(seconds=MAX_SCAN_INTERVAL)

    for _ in range(5):
        await _then(
            hass,
            freezer,
            aioclient_mock,
            DISTRESS,
            after=timedelta(seconds=MAX_SCAN_INTERVAL + 5),
        )
    assert len(emergencies) == 1
