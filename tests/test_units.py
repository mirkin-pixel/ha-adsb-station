"""Tests for the units the integration gives its figures in."""

from __future__ import annotations

from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_UNITS,
    DOMAIN,
    EVENT_AIRCRAFT_PASSAGE,
    EVENT_WATCHLIST_MATCH,
)
from custom_components.adsb_station.logbook import async_describe_events
from custom_components.adsb_station.units import SYSTEMS, converted, units_of

from .conftest import AIRCRAFT_URL, MOCK_ALIAS, set_responses, setup_integration
from .test_config_flow import _start_user_step
from .test_passages import OVERHEAD, poll

# A kilometre north of home, 2,000 ft up, at 250 kt, climbing 1,000 ft/min
AIRCRAFT = {"altitude": 2000, "speed": 250, "vertical_rate": 1000, "distance": 1.1}


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        (
            "nautical",
            {"altitude": 2000, "speed": 250, "vertical_rate": 1000, "distance": 0.6},
        ),
        (
            "metric",
            {"altitude": 610, "speed": 463, "vertical_rate": 5.1, "distance": 1.1},
        ),
        (
            "imperial",
            {"altitude": 2000, "speed": 288, "vertical_rate": 1000, "distance": 0.7},
        ),
    ],
)
def test_converted(system: str, expected: dict[str, Any]) -> None:
    """Test each system, through a nested list as a nearby sensor has one."""
    assert converted(AIRCRAFT, SYSTEMS[system]) == expected
    nested = converted({"radius": 10, "aircraft": [AIRCRAFT]}, SYSTEMS[system])
    assert nested["aircraft"] == [expected]
    # Not a figure, so left alone
    assert converted({"flight": "KLM123", "on_ground": True}, SYSTEMS[system]) == {
        "flight": "KLM123",
        "on_ground": True,
    }


async def test_auto_is_home_assistant_s_own(hass: HomeAssistant) -> None:
    """Test metric, and imperial for Home Assistant's US units."""
    assert units_of(hass, "auto").system == "metric"
    assert units_of(hass, None).system == "metric"
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert units_of(hass, "auto").system == "imperial"
    assert units_of(hass, "nautical").system == "nautical"


def _unit(hass: HomeAssistant, key: str) -> str | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None
    return hass.states.get(entity_id).attributes.get("unit_of_measurement")


async def test_a_change_moves_the_sensors_but_not_a_choice_of_your_own(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test existing sensors following the setting, as on a unit system change."""
    assert await setup_integration(hass, mock_config_entry)
    assert (_unit(hass, "closest_aircraft"), _unit(hass, "highest_aircraft")) == (
        "km",
        "m",
    )
    assert _unit(hass, "fastest_aircraft") == "km/h"

    # A unit set on the sensor itself, which must survive
    registry = er.async_get(hass)
    sector = registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_max_range_n")
    registry.async_update_entity_options(sector, "sensor", {"unit_of_measurement": "m"})
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        mock_config_entry, options={**mock_config_entry.options, CONF_UNITS: "nautical"}
    )
    await hass.async_block_till_done()

    assert _unit(hass, "closest_aircraft") == "nmi"
    assert _unit(hass, "max_range") == "nmi"
    assert _unit(hass, "highest_aircraft") == "ft"
    assert _unit(hass, "fastest_aircraft") == "kn"
    assert _unit(hass, "max_range_n") == "m"
    attributes = hass.states.get(
        registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft")
    ).attributes
    assert attributes["altitude"] == 2000


async def test_events_say_what_their_figures_are_in(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a passage in nautical units, named for a template to use."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_AIRCRAFT_PASSAGE, events.append)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_UNITS: "nautical"}
    )
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [event] = events
    assert event.data["altitude"] == 2000
    assert event.data["distance"] == 0.6
    assert (event.data["altitude_unit"], event.data["distance_unit"]) == ("ft", "nmi")
    assert (event.data["speed_unit"], event.data["vertical_rate_unit"]) == (
        "kn",
        "ft/min",
    )


async def test_asked_for_when_a_station_is_added(
    hass: HomeAssistant, mock_api: AiohttpClientMocker
) -> None:
    """Test the choice in the setup, kept as an option, and left out when automatic."""
    result = await _start_user_step(hass)
    assert CONF_UNITS in result["data_schema"].schema
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL, CONF_UNITS: "nautical"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_UNITS: "nautical"}


def test_an_activity_line_in_the_unit_it_was_fired_in(hass: HomeAssistant) -> None:
    """Test the distance named as the event names it, and km for older events."""
    described: dict[str, Any] = {}
    async_describe_events(
        hass, lambda _, kind, describe: described.update({kind: describe})
    )
    describe = described[EVENT_WATCHLIST_MATCH]
    data = {"station": "Garage", "flight": "KLM123", "distance": 6.6}
    line = describe(Event(EVENT_WATCHLIST_MATCH, {**data, "distance_unit": "nmi"}))
    assert line[LOGBOOK_ENTRY_MESSAGE] == "heard KLM123 from the watchlist, 6.6 NM away"
    line = describe(Event(EVENT_WATCHLIST_MATCH, data))
    assert line[LOGBOOK_ENTRY_MESSAGE] == "heard KLM123 from the watchlist, 6.6 km away"
