"""Tests for spotting GPS interference from the aircraft's own accuracy."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN, GPS_WINDOW
from custom_components.adsb_station.coordinator import gps_level, gps_poor

from .conftest import MOCK_ALIAS, set_responses, setup_integration
from .test_passages import next_poll, poll
from .test_sensor import _state

FLYING = {"alt_baro": 35000, "gs": 450, "nac_p": 9}


def fleet(good: int, poor: int) -> dict[str, Any]:
    """Return a sky of airliners, some of them with poor GPS."""
    return poll(
        *({**FLYING, "hex": f"40{n:04x}"} for n in range(good)),
        *({**FLYING, "hex": f"50{n:04x}", "nac_p": 1} for n in range(poor)),
    )


@pytest.mark.parametrize(
    ("entry", "poor"),
    [
        ({**FLYING}, False),
        ({**FLYING, "nac_p": 2}, True),
        ({**FLYING, "nac_p": 3}, False),
        # readsb's own verdict, whatever the last accuracy said
        ({**FLYING, "gpsOkBefore": 1794655098.1}, True),
        # Nothing to say: on the ground, taxiing, or no accuracy sent
        ({**FLYING, "alt_baro": "ground", "nac_p": 0}, None),
        ({**FLYING, "gs": 20, "nac_p": 0}, None),
        ({"alt_baro": 35000, "gs": 450}, None),
    ],
)
def test_one_aircraft(entry: dict[str, Any], poor: bool | None) -> None:
    """Test what counts as poor GPS for one aircraft."""
    assert gps_poor(entry) is poor


@pytest.mark.parametrize(
    ("share", "level"),
    [
        (None, None),
        (0.0, "none"),
        (1.9, "none"),
        (2.0, "possible"),
        (10.0, "possible"),
        (10.1, "likely"),
    ],
)
def test_the_level(share: float | None, level: str | None) -> None:
    """Test GPSJAM's bands: under 2, 2 to 10, over 10 percent."""
    assert gps_level(share) == level


def _binary(hass: HomeAssistant) -> Any:
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_gps_interference"
    )
    assert entity_id is not None
    return hass.states.get(entity_id)


async def test_a_station_under_interference(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test one faulty receiver ignored, real interference noticed, and forgotten."""
    set_responses(aioclient_mock, aircraft=fleet(good=19, poor=1))
    assert await setup_integration(hass, mock_config_entry)
    # One aircraft alone is taken off, as GPSJAM does.
    assert float(_state(hass, "gps_interference")) == 0
    assert _binary(hass).state == "off"
    assert _binary(hass).attributes["level"] == "none"

    set_responses(aioclient_mock, aircraft=fleet(good=19, poor=3))
    await next_poll(hass, freezer)
    # 22 aircraft heard in the window, three poor: (3 - 1) / 22
    assert float(_state(hass, "gps_interference")) == 9.1
    assert _binary(hass).attributes["level"] == "possible"

    set_responses(aioclient_mock, aircraft=fleet(good=10, poor=6))
    await next_poll(hass, freezer)
    # The 19 good ones still count within the window: (6 - 1) / 25
    assert float(_state(hass, "gps_interference")) == 20
    assert _binary(hass).state == "on"
    assert _binary(hass).attributes["level"] == "likely"

    # Once the window has passed with good GPS all round, it is over.
    set_responses(aioclient_mock, aircraft=fleet(good=20, poor=0))
    await next_poll(hass, freezer, GPS_WINDOW + timedelta(minutes=1))
    await next_poll(hass, freezer)
    assert float(_state(hass, "gps_interference")) == 0
    assert _binary(hass).state == "off"
