"""Tests for the question asked once an aircraft has gone: what just flew over."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DOMAIN,
    MAX_SCAN_INTERVAL,
    PASSAGE_GAP,
)
from custom_components.adsb_station.intent import INTENT_LAST_PASSAGE
from custom_components.adsb_station.services import SERVICE_SPEAK
from custom_components.adsb_station.speech import ago_of

from .conftest import AIRCRAFT_URL, set_responses, setup_integration
from .test_passages import OVERHEAD, next_poll, poll

NOTHING = "I have heard nothing come over in the last 10 minutes."

# Home is 52.0, 5.0; a hundredth of a degree of latitude is 1.1 km. The KLM is
# at 2,000 feet, so a little over 600 metres up.
FURTHER = {**OVERHEAD, "lat": 52.03}
NEARER = {**OVERHEAD, "lat": 52.005}
EASYJET = {**OVERHEAD, "hex": "484124", "flight": "EZY22"}


@pytest.fixture(autouse=True)
async def intent_component(hass: HomeAssistant) -> None:
    """Load the component that registers the questions, as Assist does."""
    assert await async_setup_component(hass, "intent", {})


async def _ask(hass: HomeAssistant, language: str = "en") -> str:
    """Ask what just flew over, and return what is said back."""
    response = await intent.async_handle(
        hass, DOMAIN, INTENT_LAST_PASSAGE, {}, language=language
    )
    return str(response.speech["plain"]["speech"])


async def _start(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    *aircraft: dict[str, Any],
) -> None:
    set_responses(aioclient_mock, aircraft=poll(*aircraft))
    assert await setup_integration(hass, entry)


async def _then(
    hass: HomeAssistant,
    freezer: Any,
    aioclient_mock: AiohttpClientMocker,
    *aircraft: dict[str, Any],
    after: timedelta | None = None,
) -> None:
    set_responses(aioclient_mock, aircraft=poll(*aircraft))
    await next_poll(hass, freezer, after)


async def test_an_empty_sky(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the answer with nothing in memory, said of the station."""
    await _start(hass, mock_config_entry, aioclient_mock)

    assert await _ask(hass) == NOTHING
    assert await _ask(hass, "nl") == (
        "Ik heb de afgelopen 10 minuten niets horen overvliegen."
    )


async def test_one_on_its_way_in_has_not_come_over_yet(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft still closing in is said to be overhead now."""
    await _start(hass, mock_config_entry, aioclient_mock, FURTHER)
    assert await _ask(hass) == "KLM 123 is overhead, 600 metres up."

    await _then(hass, freezer, aioclient_mock, NEARER)
    assert await _ask(hass) == "KLM 123 is overhead, 600 metres up."


async def test_one_that_has_gone(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the question this is for: asked once the aircraft is out of range.

    The overhead question has nothing to say by then.
    """
    await _start(hass, mock_config_entry, aioclient_mock, OVERHEAD)
    await _then(hass, freezer, aioclient_mock)

    assert await _ask(hass) == "KLM 123 came over just now, 600 metres up."
    assert await _ask(hass, "nl") == "KLM 123 vloog net over, 600 meter hoog."

    # Counted from its closest approach, and still there just before it is
    # forgotten
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=1))
    assert await _ask(hass) == "KLM 123 came over a minute ago, 600 metres up."
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=8))
    assert await _ask(hass, "nl") == (
        "KLM 123 vloog 9 minuten geleden over, 600 meter hoog."
    )

    # Ten minutes after it was last seen it is forgotten
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=2))
    assert await _ask(hass) == NOTHING


async def test_one_still_in_view_but_further_off(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft past its closest approach has come over."""
    await _start(hass, mock_config_entry, aioclient_mock, NEARER)
    await _then(hass, freezer, aioclient_mock, FURTHER)

    assert await _ask(hass) == "KLM 123 came over just now, 600 metres up."


async def test_the_last_to_come_past_is_the_answer(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a stream: the latest closest approach, not the latest arrival."""
    await _start(hass, mock_config_entry, aioclient_mock, OVERHEAD)
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=2))
    await _then(hass, freezer, aioclient_mock, EASYJET, after=timedelta(minutes=1))
    await _then(hass, freezer, aioclient_mock)
    assert await _ask(hass) == "easyJet 22 came over just now, 600 metres up."

    # A third arrives while the easyJet is gone: it is on its way in, so it
    # is not the one that came over
    arriving = {**FURTHER, "hex": "484125", "flight": "TRA45"}
    await _then(hass, freezer, aioclient_mock, arriving)
    assert await _ask(hass) == "easyJet 22 came over just now, 600 metres up."


async def test_of_two_on_the_same_poll_the_nearer(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the tie: both nearest on one poll, both gone on the next."""
    # The KLM arrives first, so it is first in memory as well; both are
    # nearest on the second poll, and the easyJet came closer
    await _start(hass, mock_config_entry, aioclient_mock, FURTHER)
    await _then(
        hass,
        freezer,
        aioclient_mock,
        {**OVERHEAD, "lat": 52.02},
        {**NEARER, "hex": "484124", "flight": "EZY22"},
    )
    await _then(hass, freezer, aioclient_mock)

    assert await _ask(hass) == "easyJet 22 came over just now, 600 metres up."


async def test_one_that_stayed_is_counted_from_when_it_left(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a helicopter that circled for longer than the gap, then left."""
    helicopter = {**OVERHEAD, "hex": "480123", "flight": "PHTRA", "category": "A7"}
    await _start(hass, mock_config_entry, aioclient_mock, NEARER | helicopter)

    # Circling further off for a quarter of an hour: past its closest
    # approach so long ago that it is simply overhead now
    circling = {**helicopter, "lat": 52.02}
    for _ in range(15):
        await _then(hass, freezer, aioclient_mock, circling, after=timedelta(minutes=1))
    assert await _ask(hass) == "P H T R A is overhead, 600 metres up."

    # Gone two minutes ago: that is what is recent, not its closest approach
    await _then(hass, freezer, aioclient_mock, after=timedelta(minutes=2))
    assert await _ask(hass) == "P H T R A came over 2 minutes ago, 600 metres up."


async def test_speak_answers_it_too(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the same answer through the action, without sentence files."""
    await _start(hass, mock_config_entry, aioclient_mock, OVERHEAD)
    await _then(hass, freezer, aioclient_mock)

    spoken = await hass.services.async_call(
        DOMAIN,
        SERVICE_SPEAK,
        {"question": "last_passage", "language": "nl"},
        blocking=True,
        return_response=True,
    )
    assert spoken == {"speech": "KLM 123 vloog net over, 600 meter hoog."}


@pytest.mark.parametrize(
    ("seconds", "spoken"),
    [
        (0, "just now"),
        (59, "just now"),
        (60, "a minute ago"),
        (119, "a minute ago"),
        (120, "2 minutes ago"),
        (PASSAGE_GAP.total_seconds(), "10 minutes ago"),
    ],
)
def test_ago_of(seconds: float, spoken: str) -> None:
    """Test how long ago is said, in whole minutes once it is one."""
    assert ago_of(seconds, "en") == spoken


async def test_a_memory_no_poll_refreshes_still_ages(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that what was seen is not said forever once the polls stop.

    The coordinator forgets a passage on the next poll; with the decoder gone
    there is none, so the question measures against the clock itself.
    """
    await _start(hass, mock_config_entry, aioclient_mock, OVERHEAD)
    await _then(hass, freezer, aioclient_mock)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_passed(dt_util.utcnow()) is not None

    later = dt_util.utcnow() + PASSAGE_GAP + timedelta(minutes=1)
    assert coordinator.last_passed(later) is None


async def test_a_slow_interval_still_says_it_came_over(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the slowest interval, where gone is only known a poll later."""
    await _start(hass, mock_config_entry, aioclient_mock, OVERHEAD)
    coordinator = mock_config_entry.runtime_data
    coordinator.update_interval = timedelta(seconds=MAX_SCAN_INTERVAL)
    await _then(
        hass,
        freezer,
        aioclient_mock,
        after=timedelta(seconds=MAX_SCAN_INTERVAL),
    )

    # Asked before the poll after that, which will forget it
    freezer.tick(timedelta(minutes=2))
    assert await _ask(hass) == "KLM 123 came over 12 minutes ago, 600 metres up."


async def test_a_silent_station_stops_saying_it_is_overhead(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a decoder gone while an aircraft was on its way in.

    No poll clears what it last saw, so the clock has to.
    """
    await _start(hass, mock_config_entry, aioclient_mock, FURTHER)
    aioclient_mock.clear_requests()
    aioclient_mock.get(AIRCRAFT_URL, exc=ClientError())
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert await _ask(hass) == NOTHING
