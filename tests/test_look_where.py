"""Tests for which way and how high to look for an aircraft."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.coordinator import (
    _elevation,
    _summarise,
    aircraft_attributes,
)

from .conftest import set_responses, setup_integration
from .test_sensor import _attributes


@pytest.mark.parametrize(
    ("metres", "feet", "degrees"),
    [
        # Straight up
        (0, 2000, 90.0),
        # Ten kilometres off and ten up: the curve takes a little off 45
        (10_000, 10_000 / 0.3048, 44.93),
        # At a hundred kilometres the curve hides nearly a kilometre of height
        (100_000, 10_000 / 0.3048, 5.26),
        # Low and far: below the horizon
        (100_000, 1000, -0.27),
    ],
)
def test_elevation(metres: float, feet: float, degrees: float) -> None:
    """Test the angle above the horizon against worked examples."""
    assert _elevation(metres, feet) == pytest.approx(degrees, abs=0.01)


def test_nothing_to_say_without_a_position_or_a_height() -> None:
    """Test that unknowns are left out rather than guessed."""
    assert _elevation(None, 2000) is None
    assert _elevation(1000, None) is None
    attributes = aircraft_attributes(_summarise({"hex": "484125"}, None))
    assert "bearing" not in attributes
    assert "elevation" not in attributes


async def test_which_way_and_how_high(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the attributes of a low aircraft due north and a high one far off."""
    assert await setup_integration(hass, mock_config_entry)

    closest = _attributes(hass, "closest_aircraft")
    assert closest["bearing"] == 0
    # 2,000 feet up, 1.1 km away
    assert closest["elevation"] == pytest.approx(28.7, abs=0.1)

    highest = _attributes(hass, "highest_aircraft")
    assert highest["bearing"] == 0
    assert highest["elevation"] == pytest.approx(5.0, abs=0.1)


async def test_due_east(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a bearing that is not north."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1.0,
            "aircraft": [{"hex": "484126", "lat": 52.0, "lon": 5.02, "alt_baro": 3000}],
        },
    )
    assert await setup_integration(hass, mock_config_entry)

    assert _attributes(hass, "closest_aircraft")["bearing"] == 90
