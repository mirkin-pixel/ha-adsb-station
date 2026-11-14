"""Tests for the standing list of aircraft worth knowing about."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_WATCHLIST,
    DOMAIN,
    EVENT_WATCHLIST_LOST,
    EVENT_WATCHLIST_MATCH,
    MAX_SCAN_INTERVAL,
    PASSAGE_GAP,
)
from custom_components.adsb_station.coordinator import (
    _matches,
    _summarise,
    watchlist_of,
)
from custom_components.adsb_station.reference import kind_of, line_key

from .conftest import set_responses, setup_integration

# Far outside the ten kilometre radius, which is the point: a watchlist has
# no radius at all.
FAR_AWAY = {
    "hex": "484123",
    "flight": "KLM123",
    "lat": 53.0,
    "lon": 5.0,
    "alt_baro": 35000,
    "r": "PH-BXA",
    "t": "B738",
}
HELICOPTER = {
    "hex": "480123",
    "flight": "PHTRA",
    "lat": 52.05,
    "lon": 5.0,
    "alt_baro": 1200,
    "t": "EC35",
    "squawk": "7700",
}


def poll(*aircraft: dict[str, Any]) -> dict[str, Any]:
    """Return an aircraft.json holding exactly these aircraft."""
    return {"now": 1636387404.0, "messages": 1000, "aircraft": list(aircraft)}


@pytest.fixture
def lost(hass: HomeAssistant) -> list[Event]:
    """Collect every event for a watched aircraft gone out of range."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_WATCHLIST_LOST, events.append)
    return events


@pytest.fixture
def matches(hass: HomeAssistant) -> list[Event]:
    """Collect every watchlist event fired during a test."""
    events: list[Event] = []
    hass.bus.async_listen(EVENT_WATCHLIST_MATCH, events.append)
    return events


async def watching(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    lines: str,
    aircraft: dict[str, Any] | None = None,
) -> None:
    """Set a station up with a watchlist."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_WATCHLIST: lines})
    set_responses(aioclient_mock, aircraft=aircraft or poll(FAR_AWAY, HELICOPTER))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("line", "hex_code", "matched_on"),
    [
        ("484123", "484123", "hex"),
        # Written however it comes: capitals, dashes and spaces are noise
        ("ph-bxa", "484123", "registration"),
        ("PHBXA", "484123", "registration"),
        ("KLM123", "484123", "flight"),
        ("EC35", "480123", "aircraft_type"),
        ("7700", "480123", "squawk"),
    ],
)
async def test_every_shape_of_line_matches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    matches: list[Event],
    line: str,
    hex_code: str,
    matched_on: str,
) -> None:
    """Test each of the four forms a line can take."""
    await watching(hass, mock_config_entry, aioclient_mock, line)

    assert len(matches) == 1
    assert matches[0].data["hex"] == hex_code
    assert matches[0].data["watching"] == line
    assert matches[0].data["matched_on"] == matched_on


async def test_the_sensor_says_what_is_up_there(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the one sensor that stands for the whole list."""
    await watching(hass, mock_config_entry, aioclient_mock, "EC35\n484123")

    state = hass.states.get("binary_sensor.t_ehxx23_watchlist_in_range")
    assert state.state == "on"
    assert state.attributes["watching"] == ["EC35", "484123"]
    assert [item["hex"] for item in state.attributes["aircraft"]] == [
        "484123",
        "480123",
    ]


async def test_no_sensor_without_a_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that an empty watchlist creates no entity at all."""
    assert await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.t_ehxx23_watchlist_in_range") is None


async def test_one_flypast_is_one_message(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    matches: list[Event],
    lost: list[Event],
) -> None:
    """Test that an aircraft in range for a long time is announced once.

    As the docs promise: not repeated while it stays in the air, and again
    once it has been gone for ten minutes.
    """
    await watching(hass, mock_config_entry, aioclient_mock, "484123")
    assert len(matches) == 1

    async def poll_after(after: timedelta) -> None:
        freezer.tick(after)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # In range for well over the gap, seen every minute
    for _ in range(15):
        await poll_after(timedelta(minutes=1))
    assert len(matches) == 1

    # Out of range for just under the gap, then back: the same flight
    set_responses(aioclient_mock, aircraft=poll(HELICOPTER))
    await poll_after(timedelta(minutes=1))
    await poll_after(PASSAGE_GAP - timedelta(minutes=2))
    set_responses(aioclient_mock, aircraft=poll(FAR_AWAY, HELICOPTER))
    await poll_after(timedelta(minutes=1))
    assert len(matches) == 1
    assert lost == []

    # Gone for longer than the gap, then back: worth hearing about again
    set_responses(aioclient_mock, aircraft=poll(HELICOPTER))
    await poll_after(timedelta(minutes=1))
    await poll_after(PASSAGE_GAP + timedelta(minutes=1))
    # Said once the gap has passed, not the moment it drops out
    [gone] = lost
    assert gone.data["watching"] == "484123"
    assert gone.data["flight"] == "KLM123"
    # From the first poll to the last one it was heard: 15 + 1 + 8 + 1 minutes
    assert gone.data["duration"] == 25 * 60
    set_responses(aioclient_mock, aircraft=poll(FAR_AWAY, HELICOPTER))
    await poll_after(timedelta(minutes=1))
    assert len(matches) == 2
    assert len(lost) == 1


async def test_one_aircraft_is_one_message_however_many_lines_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    matches: list[Event],
) -> None:
    """Test that a hex and a type naming the same aircraft say it once."""
    await watching(hass, mock_config_entry, aioclient_mock, "484123\nB738")

    assert len(matches) == 1
    # The first line of the list wins, so the message says what was asked for
    assert matches[0].data["watching"] == "484123"


async def test_the_options_flow_refuses_a_line_it_cannot_read(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a typo is refused rather than silently never matching."""
    assert await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 15,
            "proximity_radius": 10,
            "map_aircraft": False,
            "look_up_routes": False,
            CONF_WATCHLIST: "484123\n!!\nEC35",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_WATCHLIST: "unreadable_watchlist"}
    assert result["description_placeholders"] == {"lines": "!!"}


async def test_one_flypast_is_one_message_at_the_slowest_interval(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    matches: list[Event],
    lost: list[Event],
) -> None:
    """Test the slowest interval, where polls are as far apart as the gap.

    The next poll is planned once the last one is done, so in practice they
    are a little further apart than the interval.
    """
    await watching(hass, mock_config_entry, aioclient_mock, "484123")
    mock_config_entry.runtime_data.update_interval = timedelta(
        seconds=MAX_SCAN_INTERVAL
    )

    for _ in range(4):
        freezer.tick(timedelta(seconds=MAX_SCAN_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(matches) == 1
    assert lost == []


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("KLM*", "prefix"),
        ("PH-B*", "prefix"),
        ("Military", "military"),
        ("helicopter", "helicopter"),
        ("country:US", "country"),
        ("COUNTRY: nl", "country"),
        # Too short, a * in the middle, a country that is not two letters
        ("K*", None),
        ("KL*M", None),
        ("country:USA", None),
        ("type:B738", None),
    ],
)
def test_the_shape_of_a_group(line: str, kind: str | None) -> None:
    """Test the lines that stand for more than one aircraft, and the misspelt."""
    assert kind_of(line, {}) == kind


@pytest.mark.parametrize(
    ("line", "entry", "matched_on"),
    [
        ("PH-B*", {"hex": "484123", "r": "PH-BXA"}, "registration"),
        ("KLM*", {"hex": "484123", "flight": "KLM123"}, "flight"),
        ("military", {"hex": "484123", "dbFlags": 1}, "military"),
        ("helicopter", {"hex": "480123", "category": "A7"}, "category"),
        ("country:nl", {"hex": "484123"}, "country"),
        ("KLM*", {"hex": "484123", "flight": "TRA45"}, None),
        ("military", {"hex": "484123", "dbFlags": 0}, None),
        ("helicopter", {"hex": "484123", "category": "A3"}, None),
    ],
)
def test_a_group_matches(
    line: str, entry: dict[str, Any], matched_on: str | None
) -> None:
    """Test what each group matches on, and what it leaves alone."""
    summary = replace(_summarise(entry, None), country="NL")
    [watched] = watchlist_of(
        MockConfigEntry(domain=DOMAIN, options={CONF_WATCHLIST: line}), {}
    )
    assert _matches(watched, summary, "") == matched_on


def test_a_star_makes_another_line() -> None:
    """Test that KLM* is not KLM written another way, as PH-BXA is PHBXA."""
    assert line_key("PH-BXA") == line_key("phbxa")
    assert line_key("KLM*") != line_key("KLM")
