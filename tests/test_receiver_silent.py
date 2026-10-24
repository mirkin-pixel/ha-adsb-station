"""Tests for noticing a receiver that has stopped hearing anything.

The way it happens in practice: the dongle drops off the bus, or a host comes
back from a reboot with the dongle not power cycled. The decoder may stop, may
hang on its last aircraft.json, or may keep serving an empty one, and each of
those has to end in the same place: the problem sensor on, and a repair that
says what to do about it.
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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RECEIVER_SILENT_AFTER,
)

from .conftest import (
    MOCK_AIRCRAFT,
    MOCK_PIAWARE,
    PIAWARE_URL,
    set_responses,
    setup_integration,
)

POLL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


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


async def _poll(
    hass: HomeAssistant,
    freezer: Any,
    aioclient_mock: AiohttpClientMocker,
    after: timedelta = POLL,
    **responses: Any,
) -> None:
    """Let some time pass, and poll with the given responses."""
    set_responses(aioclient_mock, **responses)
    freezer.tick(after)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _counted(messages: int) -> dict[str, Any]:
    """Return an aircraft.json whose counter stands at the given number."""
    return {"aircraft": {**MOCK_AIRCRAFT, "messages": messages}}


async def test_a_receiver_that_hears_is_not_silent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a counter going up keeps the sensor off, however long."""
    assert await setup_integration(hass, mock_config_entry)

    for messages in range(1_000_100, 1_004_100, 100):
        await _poll(hass, freezer, mock_api, **_counted(messages))

    assert _state(hass, mock_config_entry) == STATE_OFF
    assert _issue(hass, mock_config_entry) is None


async def test_a_counter_that_stops_is_silence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a decoder that keeps answering but counts nothing new."""
    assert await setup_integration(hass, mock_config_entry)
    await _poll(hass, freezer, mock_api, **_counted(1_000_500))

    # Just short of the limit, nothing is said yet.
    await _poll(
        hass, freezer, mock_api, RECEIVER_SILENT_AFTER - POLL, **_counted(1_000_500)
    )
    assert _state(hass, mock_config_entry) == STATE_OFF

    await _poll(hass, freezer, mock_api, POLL, **_counted(1_000_500))
    assert _state(hass, mock_config_entry) == STATE_ON
    issue = _issue(hass, mock_config_entry)
    assert issue is not None
    assert issue.translation_key == "receiver_silent"
    assert issue.translation_placeholders == {
        "station": mock_config_entry.title,
        "minutes": "10",
    }

    # The dongle is back: the sensor and the repair clear on their own.
    await _poll(hass, freezer, mock_api, **_counted(1_000_900))
    assert _state(hass, mock_config_entry) == STATE_OFF
    assert _issue(hass, mock_config_entry) is None


async def test_silent_from_the_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a dongle that was already gone when Home Assistant started."""
    assert await setup_integration(hass, mock_config_entry)

    await _poll(hass, freezer, mock_api, RECEIVER_SILENT_AFTER)

    assert _state(hass, mock_config_entry) == STATE_ON


async def test_a_decoder_that_does_not_answer_is_silence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test a decoder that stopped, with the feeder still there to report it.

    The aircraft entities go unavailable, which says the decoder cannot be
    read; this one stays available, because the reason it cannot is the
    thing it is there to say.
    """
    assert await setup_integration(hass, mock_config_entry)

    await _poll(
        hass,
        freezer,
        mock_api,
        RECEIVER_SILENT_AFTER,
        aircraft_kwargs={"exc": aiohttp.ClientError("boom")},
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

    await _poll(
        hass,
        freezer,
        mock_api,
        RECEIVER_SILENT_AFTER,
        aircraft_kwargs={"exc": aiohttp.ClientError("boom")},
    )

    assert _state(hass, mock_receiver_entry) == STATE_UNAVAILABLE
    assert _issue(hass, mock_receiver_entry) is not None


async def test_a_restarted_decoder_is_not_silence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a counter starting over counts again from its new start."""
    assert await setup_integration(hass, mock_config_entry)

    await _poll(hass, freezer, mock_api, RECEIVER_SILENT_AFTER - POLL, **_counted(20))
    await _poll(hass, freezer, mock_api, **_counted(400))

    assert _state(hass, mock_config_entry) == STATE_OFF


async def test_a_decoder_without_a_counter_is_taken_at_its_word(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a decoder we cannot judge is never called silent."""
    without = {key: value for key, value in MOCK_AIRCRAFT.items() if key != "messages"}
    set_responses(mock_api, aircraft=without)
    assert await setup_integration(hass, mock_config_entry)

    await _poll(hass, freezer, mock_api, RECEIVER_SILENT_AFTER, aircraft=without)

    assert _state(hass, mock_config_entry) == STATE_OFF


async def test_unloading_takes_the_repair_with_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    freezer: Any,
) -> None:
    """Test that a removed station does not leave a repair naming it."""
    assert await setup_integration(hass, mock_config_entry)
    await _poll(hass, freezer, mock_api, RECEIVER_SILENT_AFTER)
    assert _issue(hass, mock_config_entry) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert _issue(hass, mock_config_entry) is None


async def test_no_sensor_without_a_decoder(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a feeder with no decoder of its own gets no such sensor."""
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    assert (
        er.async_get(hass).async_get_entity_id(
            "binary_sensor", DOMAIN, f"{mock_piaware_entry.unique_id}_receiver_silent"
        )
        is None
    )
