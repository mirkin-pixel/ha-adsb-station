"""Tests for the units the integration gives its figures in."""

from __future__ import annotations

from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.location import distance
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_FOLLOW_UNITS,
    CONF_MAP_AIRCRAFT,
    CONF_PROXIMITY_MAX_ALTITUDE,
    CONF_PROXIMITY_RADIUS,
    CONF_UNITS,
    DOMAIN,
    EVENT_AIRCRAFT_PASSAGE,
    EVENT_WATCHLIST_MATCH,
)
from custom_components.adsb_station.logbook import async_describe_events
from custom_components.adsb_station.repairs import (
    set_by_hand_issue_id,
    units_issue_id,
)
from custom_components.adsb_station.units import SYSTEMS, converted, units_of

from .conftest import (
    AIRCRAFT_URL,
    HOME_LATITUDE,
    HOME_LONGITUDE,
    MOCK_ALIAS,
    set_responses,
    setup_integration,
)
from .test_config_flow import _start_receiver_step, _start_user_step, _suggested
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


@pytest.mark.parametrize("version", [3, 5])
async def test_an_upgrade_moves_the_sensors_of_an_existing_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    version: int,
) -> None:
    """Test sensors registered with fixed units following the setting.

    From 1.3, and from a release that still has the older migrations to go.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
        minor_version=1,
        unique_id=mock_config_entry.unique_id,
        data=dict(mock_config_entry.data),
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    def registered(key: str, unit: str) -> str:
        """Register a sensor as 1.3 left it: feet, knots and kilometres."""
        entity = registry.async_get_or_create(
            "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}", config_entry=entry
        )
        registry.async_update_entity_options(
            entity.entity_id,
            "sensor.private",
            {"suggested_unit_of_measurement": unit},
        )
        return entity.entity_id

    highest = registered("highest_aircraft", "ft")
    fastest = registered("fastest_aircraft", "kn")
    sector = registered("max_range_n", "km")
    # And one set to miles by hand, round the mixed units
    registry.async_update_entity_options(
        sector, "sensor", {"unit_of_measurement": "mi"}
    )

    assert await setup_integration(hass, entry)

    assert (entry.version, entry.minor_version) == (5, 3)
    units = [
        hass.states.get(entity_id).attributes.get("unit_of_measurement")
        for entity_id in (highest, fastest, sector)
    ]
    # The one set by hand stays, and is offered to follow under Repairs
    assert units == ["m", "km/h", "mi"]
    by_hand = ir.async_get(hass).async_get_issue(
        DOMAIN, set_by_hand_issue_id(entry.entry_id)
    )
    assert by_hand is not None
    assert by_hand.translation_placeholders["sensors"].endswith(": mi")

    # And it is told so, in the units it now has
    issue = ir.async_get(hass).async_get_issue(DOMAIN, units_issue_id(entry.entry_id))
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "station": entry.title,
        "units": "m, km/h, km",
    }


async def test_a_unit_set_by_hand_is_offered_to_follow_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test a station on 1.4.0b3 with km on the height: asked, and cleared on yes.

    The precision set beside it stays, and so does a unit on a sensor that
    is not in the station's units.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        minor_version=2,
        unique_id=mock_config_entry.unique_id,
        data=dict(mock_config_entry.data),
        options={CONF_UNITS: "nautical"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    highest = registry.async_get_or_create(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_highest_aircraft", config_entry=entry
    ).entity_id
    registry.async_update_entity_options(
        highest, "sensor", {"unit_of_measurement": "km", "display_precision": 1}
    )
    status = registry.async_get_or_create(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_message_rate", config_entry=entry
    ).entity_id
    registry.async_update_entity_options(
        status, "sensor", {"unit_of_measurement": "msg/min"}
    )

    assert await setup_integration(hass, entry)

    # Nothing changed by itself, and only this question asked
    assert (entry.version, entry.minor_version) == (5, 3)
    assert hass.states.get(highest).attributes["unit_of_measurement"] == "km"
    issue_id = set_by_hand_issue_id(entry.entry_id)
    assert [key[1] for key in ir.async_get(hass).issues] == [issue_id]

    assert await async_setup_component(hass, "repairs", {})
    flows = hass.data["repairs"]["flow_manager"]
    result = await flows.async_init(DOMAIN, data={"issue_id": issue_id})
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["follow", "keep"]
    assert result["description_placeholders"]["station"] == entry.title
    assert result["description_placeholders"]["sensors"].endswith(": km")
    result = await flows.async_configure(result["flow_id"], {"next_step_id": "follow"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.states.get(highest).attributes["unit_of_measurement"] == "ft"
    kept = registry.async_get(highest).options["sensor"]
    assert "unit_of_measurement" not in kept
    assert kept["display_precision"] == 1
    assert (
        registry.async_get(status).options["sensor"]["unit_of_measurement"] == "msg/min"
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_a_unit_set_by_hand_can_be_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test Keep: nothing changes, and the question goes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        minor_version=2,
        unique_id=mock_config_entry.unique_id,
        data=dict(mock_config_entry.data),
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    highest = registry.async_get_or_create(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_highest_aircraft", config_entry=entry
    ).entity_id
    registry.async_update_entity_options(
        highest, "sensor", {"unit_of_measurement": "km"}
    )
    assert await setup_integration(hass, entry)
    assert await async_setup_component(hass, "repairs", {})
    issue_id = set_by_hand_issue_id(entry.entry_id)
    flows = hass.data["repairs"]["flow_manager"]

    result = await flows.async_init(DOMAIN, data={"issue_id": issue_id})
    result = await flows.async_configure(result["flow_id"], {"next_step_id": "keep"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.states.get(highest).attributes["unit_of_measurement"] == "km"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_configure_lets_a_unit_set_by_hand_follow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the box: absent without one, under the units with one, clearing it."""
    assert await setup_integration(hass, mock_config_entry)
    flows = hass.config_entries.options

    def fields(result: Any) -> list[str]:
        return [str(key) for key in result["data_schema"].schema]

    result = await flows.async_init(mock_config_entry.entry_id)
    assert CONF_FOLLOW_UNITS not in fields(result)
    await flows.async_configure(result["flow_id"], _shown(result))

    registry = er.async_get(hass)
    highest = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_highest_aircraft"
    )
    registry.async_update_entity_options(
        highest, "sensor", {"unit_of_measurement": "km"}
    )
    await hass.async_block_till_done()
    assert _unit(hass, "highest_aircraft") == "km"

    # Shown, named, and left alone when not ticked
    result = await flows.async_init(mock_config_entry.entry_id)
    assert fields(result)[:2] == [CONF_UNITS, CONF_FOLLOW_UNITS]
    assert result["description_placeholders"]["sensors"].endswith(": km")
    await flows.async_configure(result["flow_id"], _shown(result))
    await hass.async_block_till_done()
    assert _unit(hass, "highest_aircraft") == "km"

    # Ticked: the sensor follows, the same question under Repairs goes, and
    # the tick is not kept as an option
    issue_id = set_by_hand_issue_id(mock_config_entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="units_set_by_hand",
    )
    result = await flows.async_init(mock_config_entry.entry_id)
    result = await flows.async_configure(
        result["flow_id"], {**_shown(result), CONF_FOLLOW_UNITS: True}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert _unit(hass, "highest_aircraft") == "m"
    assert CONF_FOLLOW_UNITS not in mock_config_entry.options
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    result = await flows.async_init(mock_config_entry.entry_id)
    assert CONF_FOLLOW_UNITS not in fields(result)


async def test_no_question_without_a_unit_set_by_hand(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test an upgrade with nothing set by hand asks about the units alone."""
    entry = await _upgraded(hass, mock_config_entry)
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, set_by_hand_issue_id(entry.entry_id))
        is None
    )


async def _upgraded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, **data: Any
) -> MockConfigEntry:
    """Set up a station as 1.3 left it, which asks for its units."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        minor_version=1,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, **data},
    )
    entry.add_to_hass(hass)
    assert await setup_integration(hass, entry)
    return entry


async def test_the_repair_sets_the_units_and_goes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test Aviation picked from the repair: saved, sensors moved, issue gone."""
    entry = await _upgraded(hass, mock_config_entry)
    assert await async_setup_component(hass, "repairs", {})
    issue_id = units_issue_id(entry.entry_id)
    flows = hass.data["repairs"]["flow_manager"]

    result = await flows.async_init(DOMAIN, data={"issue_id": issue_id})
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "station": entry.title,
        "units": "m, km/h, km",
    }
    result = await flows.async_configure(result["flow_id"], {CONF_UNITS: "nautical"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UNITS] == "nautical"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert _unit(hass, "highest_aircraft") == "ft"
    assert _unit(hass, "fastest_aircraft") == "kn"


async def test_units_chosen_under_configure_answer_the_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the issue gone once the units are changed another way."""
    entry = await _upgraded(hass, mock_config_entry)
    hass.config_entries.async_update_entry(entry, options={CONF_UNITS: "imperial"})
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, units_issue_id(entry.entry_id))
        is None
    )


async def test_no_repair_for_a_new_station_or_one_without_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test it asked only where figures changed: an upgraded station with a receiver."""
    assert await setup_integration(hass, mock_config_entry)
    assert not ir.async_get(hass).issues
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A feeder that reads no aircraft has no figures to change
    entry = await _upgraded(hass, mock_config_entry, **{CONF_AIRCRAFT_URL: None})
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, units_issue_id(entry.entry_id))
        is None
    )


async def test_a_removed_station_takes_its_repair_along(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test no question left behind about a station that is gone."""
    entry = await _upgraded(hass, mock_config_entry)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, units_issue_id(entry.entry_id))
        is None
    )


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


async def test_a_distance_is_rounded_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test 1.755 km as 0.9 NM, not 1.8 km first and then 1.0 NM."""
    latitude = HOME_LATITUDE + 1.755 / 111.25
    km = distance(HOME_LATITUDE, HOME_LONGITUDE, latitude, HOME_LONGITUDE) / 1000
    assert round(km, 1) == 1.8
    assert round(round(km, 1) / 1.852, 1) == 1.0
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_UNITS: "nautical"}
    )
    set_responses(
        aioclient_mock,
        aircraft=poll({**OVERHEAD, "lat": latitude, "lon": HOME_LONGITUDE}),
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_aircraft_nearby"
    )
    [plane] = hass.states.get(entity_id).attributes["aircraft"]
    assert plane["distance"] == round(km / 1.852, 1) == 0.9


async def test_an_aircraft_on_the_map_in_the_same_unit_as_its_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the distance that is the state named as the attributes name it."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True, CONF_UNITS: "nautical"}
    )
    set_responses(aioclient_mock, aircraft=poll(OVERHEAD))
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [entity_id] = hass.states.async_entity_ids("geo_location")
    state = hass.states.get(entity_id)
    assert (state.state, state.attributes["unit_of_measurement"]) == ("0.6", "nmi")
    assert state.attributes["distance_unit"] == "nmi"


def _shown(result: Any) -> dict[str, Any]:
    """Return what an options form fills its fields with."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


async def test_the_radius_and_ceiling_are_filled_in_in_the_chosen_units(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test them shown in NM and metres, kept exactly, and read in what was shown."""
    stored = {CONF_UNITS: "nautical", CONF_PROXIMITY_RADIUS: 10}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=stored)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert _shown(result)[CONF_PROXIMITY_RADIUS] == 5.4
    # Saved as shown, it stays ten kilometres, not 5.4 NM's 10.001
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_UNITS: "metric", CONF_PROXIMITY_RADIUS: 5.4},
    )
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_PROXIMITY_RADIUS] == 10

    # Now in metric: a ceiling of 3,000 m is kept as feet
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert _shown(result)[CONF_PROXIMITY_RADIUS] == 10
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PROXIMITY_RADIUS: 10, CONF_PROXIMITY_MAX_ALTITUDE: 3000},
    )
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_PROXIMITY_MAX_ALTITUDE] == 9842.52
    assert (
        _shown(
            await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        )[CONF_PROXIMITY_MAX_ALTITUDE]
        == 3000
    )


@pytest.mark.parametrize("system", ["nautical", "imperial"])
@pytest.mark.parametrize("typed", ["min", "max"])
async def test_a_radius_at_either_end_can_be_saved_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    system: str,
    typed: str,
) -> None:
    """Test the lowest and highest radius of one system, then shown in another."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_UNITS: system}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async def save(values: dict[str, Any]) -> None:
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        field = next(
            key for key in result["data_schema"].schema if key == CONF_PROXIMITY_RADIUS
        )
        config = result["data_schema"].schema[field].config
        radius = {"min": config["min"], "max": config["max"]}[typed]
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_PROXIMITY_RADIUS: radius, **values}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY

    # The end of the range in this system, saved while switching to metric
    await save({CONF_UNITS: "metric"})
    assert 1 <= mock_config_entry.options[CONF_PROXIMITY_RADIUS] <= 500
    # And opened and saved untouched in metric
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _shown(result)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_the_units_chosen_survive_a_wrong_address(
    hass: HomeAssistant, mock_api: AiohttpClientMocker
) -> None:
    """Test the choice still made when the step is shown again."""
    result = await _start_receiver_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: "", CONF_UNITS: "nautical"}
    )
    assert result["errors"] == {"base": "aircraft_url_required"}
    assert _suggested(result, CONF_UNITS) == "nautical"


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
