"""Tests for noticing a dongle that has stopped delivering.

The way it happens in practice: the dongle drops off the bus, or a host comes
back from a reboot with the dongle not power cycled. The decoder may stop, may
hang, or may keep running on nothing, and each of those has to end in the
same place: the problem sensor on, and a repair that says what to do.

What is watched is the samples the decoder counts, not the messages. A
modest antenna hears no messages at all for twenty minutes on a quiet night,
and that must never read as a dead receiver.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    DEFAULT_STATISTICS_INTERVAL,
    DOMAIN,
    RECEIVER_SILENT_AFTER,
)

from .conftest import (
    MOCK_PIAWARE,
    MOCK_STATS,
    PIAWARE_URL,
    set_responses,
    setup_integration,
)

MINUTE = timedelta(seconds=DEFAULT_STATISTICS_INTERVAL)
MINUTES = int(RECEIVER_SILENT_AFTER / MINUTE)
START = MOCK_STATS["last1min"]["end"]
BOOM = {"exc": aiohttp.ClientError("boom")}


def _state(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the state of the receiver silent sensor."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.unique_id}_receiver_silent"
    )
    assert entity_id is not None
    return hass.states.get(entity_id).state


def _issue(hass: HomeAssistant, entry: MockConfigEntry) -> ir.IssueEntry | None:
    """Return the repair for this entry's receiver, if there is one."""
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"receiver_silent_{entry.entry_id}"
    )


def _stats(minute: int, samples: int = 143_917_056) -> dict[str, Any]:
    """Return a stats.json whose last minute ended that many minutes in."""
    window = MOCK_STATS["last1min"]
    return {
        **MOCK_STATS,
        "last1min": {
            **window,
            "end": START + 60 * minute,
            "local": {**window["local"], "samples_processed": samples},
        },
    }


async def _poll(
    hass: HomeAssistant,
    freezer: Any,
    aioclient_mock: AiohttpClientMocker,
    **responses: Any,
) -> None:
    """Let a minute pass, and poll with the given responses."""
    set_responses(aioclient_mock, **responses)
    freezer.tick(MINUTE)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_a_quiet_night_is_not_silence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that no messages for a long while is not a dead receiver.

    The dongle keeps delivering samples while nothing is flying, so twenty
    minutes in which the message counter stands still stay off.
    """
    assert await setup_integration(hass, mock_config_entry)

    for minute in range(1, 21):
        await _poll(hass, freezer, mock_api, stats=_stats(minute))

    assert _state(hass, mock_config_entry) == STATE_OFF
    assert _issue(hass, mock_config_entry) is None


async def test_a_dongle_that_stops_delivering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a decoder that keeps running, with nothing coming from the dongle."""
    assert await setup_integration(hass, mock_config_entry)

    for minute in range(1, MINUTES):
        await _poll(hass, freezer, mock_api, stats=_stats(minute, samples=0))
    # Just short of the limit, nothing is said yet.
    assert _state(hass, mock_config_entry) == STATE_OFF

    await _poll(hass, freezer, mock_api, stats=_stats(MINUTES, samples=0))
    assert _state(hass, mock_config_entry) == STATE_ON
    issue = _issue(hass, mock_config_entry)
    assert issue is not None
    assert issue.translation_key == "receiver_silent"
    assert issue.translation_placeholders == {
        "station": mock_config_entry.title,
        "minutes": "3",
    }

    # The dongle is back: the sensor and the repair clear on their own.
    await _poll(hass, freezer, mock_api, stats=_stats(MINUTES + 1))
    assert _state(hass, mock_config_entry) == STATE_OFF
    assert _issue(hass, mock_config_entry) is None


async def test_a_decoder_that_hangs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a stats.json that keeps serving the same minute."""
    assert await setup_integration(hass, mock_config_entry)

    for _ in range(MINUTES):
        await _poll(hass, freezer, mock_api, stats=_stats(0))

    assert _state(hass, mock_config_entry) == STATE_ON


async def test_silent_from_the_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a dongle that was already gone when Home Assistant started."""
    set_responses(aioclient_mock, stats=_stats(0, samples=0))
    assert await setup_integration(hass, mock_config_entry)

    for minute in range(1, MINUTES + 1):
        await _poll(hass, freezer, aioclient_mock, stats=_stats(minute, samples=0))

    assert _state(hass, mock_config_entry) == STATE_ON


async def test_a_decoder_that_does_not_answer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a decoder that stopped, with the feeder still there to report it.

    The reception entities go unavailable, which says stats.json cannot be
    read; this one stays available, because the reason it cannot is the
    thing it is there to say.
    """
    assert await setup_integration(hass, mock_config_entry)

    for _ in range(MINUTES):
        await _poll(
            hass, freezer, mock_api, aircraft_kwargs=BOOM, stats_kwargs=BOOM
        )

    assert _state(hass, mock_config_entry) == STATE_ON
    assert _issue(hass, mock_config_entry) is not None


async def test_a_station_without_a_feeder_still_gets_the_repair(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a decoder that stops, with nothing else on the entry to report it.

    Every entity goes unavailable with the decoder, this one included, so the
    repair is what is left to say why.
    """
    assert await setup_integration(hass, mock_receiver_entry)

    for _ in range(MINUTES):
        await _poll(
            hass, freezer, mock_api, aircraft_kwargs=BOOM, stats_kwargs=BOOM
        )

    assert _state(hass, mock_receiver_entry) == STATE_UNAVAILABLE
    assert _issue(hass, mock_receiver_entry) is not None


async def test_a_decoder_without_a_sample_count_is_taken_at_its_word(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a decoder we cannot judge is never called silent."""
    window = MOCK_STATS["last1min"]
    local = {k: v for k, v in window["local"].items() if k != "samples_processed"}
    without = {**MOCK_STATS, "last1min": {**window, "local": local}}
    set_responses(aioclient_mock, stats=without)
    assert await setup_integration(hass, mock_config_entry)

    for _ in range(MINUTES + 1):
        await _poll(hass, freezer, aioclient_mock, stats=without)

    assert _state(hass, mock_config_entry) == STATE_OFF


async def test_unloading_takes_the_repair_with_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a removed station does not leave a repair naming it."""
    assert await setup_integration(hass, mock_config_entry)
    for minute in range(1, MINUTES + 1):
        await _poll(hass, freezer, mock_api, stats=_stats(minute, samples=0))
    assert _issue(hass, mock_config_entry) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert _issue(hass, mock_config_entry) is None


async def test_no_sensor_without_stats(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an entry with no stats.json to read gets no such sensor."""
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    assert (
        er.async_get(hass).async_get_entity_id(
            "binary_sensor", DOMAIN, f"{mock_piaware_entry.unique_id}_receiver_silent"
        )
        is None
    )
