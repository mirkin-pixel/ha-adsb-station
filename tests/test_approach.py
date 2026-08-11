"""Tests for seeing an aircraft coming before it is here."""

from __future__ import annotations

from dataclasses import replace
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
    CONF_PROXIMITY_MAX_ALTITUDE,
    DEFAULT_SCAN_INTERVAL,
    EVENT_AIRCRAFT_APPROACHING,
)
from custom_components.adsb_station.coordinator import AircraftSummary, approach_of

from .conftest import set_responses, setup_integration
from .test_passages import summary

# Home is 52.0, 5.0. Twenty kilometres north of it, which is well outside the
# ten kilometre radius, so nothing here is a passage yet.
NORTH = 52.18
HEADING_SOUTH = 180
HEADING_NORTH = 0


def flying(**values: Any) -> dict[str, Any]:
    """Return one aircraft, twenty kilometres north unless told otherwise."""
    return {
        "hex": "484123",
        "flight": "KLM123",
        "lat": NORTH,
        "lon": 5.0,
        "alt_baro": 4000,
        "gs": 300,
        "track": HEADING_SOUTH,
        **values,
    }


def poll(*aircraft: dict[str, Any]) -> dict[str, Any]:
    """Return an aircraft.json holding exactly these aircraft."""
    return {"now": 1636387404.0, "messages": 1000, "aircraft": list(aircraft)}


@pytest.fixture
def warnings(hass: HomeAssistant) -> list[Event]:
    """Collect every approach event fired during a test."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_AIRCRAFT_APPROACHING, events.append)
    return events


async def next_poll(hass: HomeAssistant, freezer: Any) -> None:
    """Move time on and let the coordinator read the receiver again."""
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def moving(**values: Any) -> AircraftSummary:
    """Return an aircraft twenty kilometres north, heading somewhere."""
    flying_south: dict[str, Any] = {
        "position": (NORTH, 5.0),
        "track": float(HEADING_SOUTH),
        "speed": 300.0,
    }
    return replace(summary(None, 4000), **{**flying_south, **values})


def test_straight_at_you() -> None:
    """Test an aircraft flying directly towards the antenna."""
    approach = approach_of((52.0, 5.0), moving())

    assert approach is not None
    passing, seconds = approach
    # It passes over the antenna itself, in the time twenty kilometres takes
    # at 300 knots
    assert passing == pytest.approx(0, abs=50)
    assert seconds == pytest.approx(20_000 / (300 * 0.514444), rel=0.05)


def test_going_away_is_not_an_approach() -> None:
    """Test that an aircraft already past the antenna predicts nothing."""
    assert approach_of((52.0, 5.0), moving(track=float(HEADING_NORTH))) is None


@pytest.mark.parametrize(
    "missing",
    [{"track": None}, {"speed": None}, {"position": None}, {"on_ground": True}],
)
def test_too_little_to_say(missing: dict[str, Any]) -> None:
    """Test that a prediction needs all three, and a flying aircraft."""
    assert approach_of((52.0, 5.0), moving(**missing)) is None


async def test_it_takes_two_polls(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    warnings: list[Event],
) -> None:
    """Test that one poll pointing at you is not enough to be told."""
    set_responses(aioclient_mock, aircraft=poll(flying()))

    assert await setup_integration(hass, mock_config_entry)
    assert warnings == []

    await next_poll(hass, freezer)

    assert len(warnings) == 1
    assert warnings[0].data["flight"] == "KLM123"
    assert warnings[0].data["closest_passing_distance"] == pytest.approx(0, abs=0.5)
    assert warnings[0].data["seconds_to_closest"] > 0

    # And it is said once, not every fifteen seconds until it arrives
    await next_poll(hass, freezer)
    assert len(warnings) == 1


async def test_one_stray_heading_says_nothing(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    warnings: list[Event],
) -> None:
    """Test the case the two-poll rule exists for."""
    # One poll pointing at the antenna, the next pointing away again
    set_responses(aioclient_mock, aircraft=poll(flying()))
    assert await setup_integration(hass, mock_config_entry)

    set_responses(aioclient_mock, aircraft=poll(flying(track=HEADING_NORTH)))
    await next_poll(hass, freezer)

    assert warnings == []

    # Turning back towards you starts the count over rather than firing at once
    set_responses(aioclient_mock, aircraft=poll(flying()))
    await next_poll(hass, freezer)
    assert warnings == []
    await next_poll(hass, freezer)
    assert len(warnings) == 1


async def test_passing_wide_is_not_worth_saying(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    warnings: list[Event],
) -> None:
    """Test that an aircraft crossing well to the side says nothing."""
    # Heading south but forty kilometres to the east, so it passes wide
    set_responses(aioclient_mock, aircraft=poll(flying(lon=5.6)))

    assert await setup_integration(hass, mock_config_entry)
    await next_poll(hass, freezer)

    assert warnings == []


async def test_the_ceiling_applies_here_too(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    warnings: list[Event],
) -> None:
    """Test that traffic too high to look up at is not announced either."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PROXIMITY_MAX_ALTITUDE: 10000}
    )
    set_responses(aioclient_mock, aircraft=poll(flying(alt_baro=35000)))

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await next_poll(hass, freezer)

    assert warnings == []


async def test_the_prediction_is_on_the_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the figures ride along with the aircraft attributes."""
    # Close enough to be nearby as well, so a sensor carries it
    set_responses(aioclient_mock, aircraft=poll(flying(lat=52.05)))

    assert await setup_integration(hass, mock_config_entry)

    nearby = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    aircraft = nearby.attributes["aircraft"][0]
    assert aircraft["approaching"] is True
    assert aircraft["closest_passing_distance"] == pytest.approx(0, abs=0.5)
    assert aircraft["seconds_to_closest"] > 0
