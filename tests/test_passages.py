"""Tests for the aircraft crossing the sky above you."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DEFAULT_SCAN_INTERVAL,
    EVENT_AIRCRAFT_PASSAGE,
    PASSAGE_GAP,
)
from custom_components.adsb_station.coordinator import AircraftSummary, slant_distance

from .conftest import set_responses, setup_integration

# Home is 52.0, 5.0. This one sits a shade over a kilometre north of it.
OVERHEAD = {
    "hex": "484123",
    "flight": "KLM123",
    "lat": 52.01,
    "lon": 5.0,
    "alt_baro": 2000,
    "gs": 250,
    "t": "B738",
}
# Same place on the ground, but at cruising altitude, which puts it out of
# reach of a ten kilometre radius once the height is counted.
HIGH_ABOVE = {**OVERHEAD, "hex": "484199", "flight": "TRA45", "alt_baro": 37000}


async def next_poll(
    hass: HomeAssistant, freezer: Any, after: timedelta | None = None
) -> None:
    """Move time on and let the coordinator read the receiver again."""
    freezer.tick(after or timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def poll(*aircraft: dict[str, Any]) -> dict[str, Any]:
    """Return an aircraft.json holding exactly these aircraft."""
    return {"now": 1636387404.0, "messages": 1000, "aircraft": list(aircraft)}


@pytest.fixture
def passages(hass: HomeAssistant) -> list[Event]:
    """Collect every passage event fired during a test."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_AIRCRAFT_PASSAGE, events.append)
    return events


def summary(distance: float | None, altitude: float | None) -> AircraftSummary:
    """Return a summary with only the fields a distance needs."""
    return AircraftSummary(
        hex="484123",
        flight=None,
        distance=distance,
        altitude=altitude,
        speed=None,
        track=None,
        vertical_rate=None,
        rssi=None,
        seen=None,
        registration=None,
        aircraft_type=None,
        description=None,
        military=False,
    )


@pytest.mark.parametrize(
    ("distance", "altitude", "expected"),
    [
        # A 3-4-5 triangle: 3 km across the ground and 4 km up
        (3000.0, 4000 / 0.3048, 5000.0),
        # Right overhead, so the whole distance is the height
        (0.0, 1000 / 0.3048, 1000.0),
        # Nothing to add, so the ground distance stands
        (5000.0, None, 5000.0),
        # An aircraft with no position has no distance of either kind
        (None, 10000.0, None),
    ],
)
def test_slant_distance(
    distance: float | None, altitude: float | None, expected: float | None
) -> None:
    """Test the distance that counts the height as well as the ground."""
    result = slant_distance(summary(distance, altitude))
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, abs=1.0)


async def test_a_passing_aircraft_fires_once(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    passages: list[Event],
) -> None:
    """Test that an aircraft in view over several polls is one passage."""
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))

    assert await setup_integration(hass, mock_config_entry)
    assert len(passages) == 1

    event = passages[0]
    assert event.data["hex"] == "484123"
    assert event.data["flight"] == "KLM123"
    assert event.data["altitude"] == 2000
    assert event.data["aircraft_type"] == "B738"
    assert event.data["description"] == "Boeing 737-800"
    assert event.data["airline"] == "KLM"
    assert event.data["entry_id"] == mock_config_entry.entry_id

    # Still there on the next poll, and still the same passage
    await next_poll(hass, freezer)
    assert len(passages) == 1


async def test_the_height_is_counted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    passages: list[Event],
) -> None:
    """Test that traffic crossing high overhead is not a passage.

    Both aircraft are a kilometre away across the ground and inside the ten
    kilometre radius, so both are nearby. Only the low one is overhead.
    """
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD, HIGH_ABOVE))

    assert await setup_integration(hass, mock_config_entry)

    nearby = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert [aircraft["flight"] for aircraft in nearby.attributes["aircraft"]] == [
        "KLM123",
        "TRA45",
    ]
    assert [event.data["flight"] for event in passages] == ["KLM123"]


async def test_a_second_aircraft_is_a_second_passage(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    passages: list[Event],
) -> None:
    """Test the case the binary sensor cannot report.

    One aircraft arriving while another is still in view turns nothing on,
    because something was already overhead. The event is per aircraft.
    """
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    assert await setup_integration(hass, mock_config_entry)
    assert len(passages) == 1

    second = {**OVERHEAD, "hex": "484124", "flight": "EZY22"}
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD, second))
    await next_poll(hass, freezer)

    assert [event.data["flight"] for event in passages] == ["KLM123", "EZY22"]


async def test_a_gap_in_reception_is_not_a_new_passage(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    passages: list[Event],
) -> None:
    """Test that an aircraft flickering out and back is still one passage."""
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    assert await setup_integration(hass, mock_config_entry)

    set_responses(aioclient_mock, aircraft=poll())
    await next_poll(hass, freezer)

    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    await next_poll(hass, freezer)

    assert len(passages) == 1


async def test_the_same_aircraft_hours_later_is_a_new_passage(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    passages: list[Event],
) -> None:
    """Test that a gap long enough to be a different flight counts again."""
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    assert await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert len(passages) == 1

    set_responses(aioclient_mock, aircraft=poll())
    await next_poll(hass, freezer, PASSAGE_GAP + timedelta(minutes=1))
    # Gone long enough to be forgotten rather than remembered forever
    assert not coordinator.passages

    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    await next_poll(hass, freezer)

    assert len(passages) == 2


async def test_a_passage_keeps_its_closest_approach(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a passage holds the moment the aircraft was nearest."""
    set_responses(aioclient_mock, aircraft=poll({**OVERHEAD, "alt_baro": 9000}))
    assert await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    set_responses(aioclient_mock, aircraft=poll({**OVERHEAD, "alt_baro": 3000}))
    await next_poll(hass, freezer)

    # And climbing away again does not replace it
    set_responses(aioclient_mock, aircraft=poll({**OVERHEAD, "alt_baro": 8000}))
    await next_poll(hass, freezer)

    passage = coordinator.passages["484123"]
    assert passage.closest.altitude == 3000


