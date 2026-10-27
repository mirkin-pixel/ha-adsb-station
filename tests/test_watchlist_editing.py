"""Tests for keeping the watchlist from a dashboard rather than the options."""

from __future__ import annotations

from typing import Any

from homeassistant.components.text import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import CONF_WATCHLIST, DOMAIN
from custom_components.adsb_station.services import SERVICE_UNWATCH, SERVICE_WATCH

from .conftest import MOCK_PIAWARE, PIAWARE_URL, set_responses, setup_integration

WATCH_BOX = "text.t_ehxx23_watchlist_add"
UNWATCH_BOX = "text.t_ehxx23_watchlist_remove"
IN_RANGE = "binary_sensor.t_ehxx23_watchlist_in_range"


async def _type(hass: HomeAssistant, entity_id: str, value: str) -> None:
    """Type a line into one of the boxes and press enter."""
    await hass.services.async_call(
        "text",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str, **data: Any) -> None:
    """Call watch or unwatch, and let the entry reload."""
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


def _watching(entry: MockConfigEntry) -> str | None:
    """Return the watchlist as it is stored."""
    return entry.options.get(CONF_WATCHLIST)


async def test_the_boxes_are_there_for_a_receiver(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a station with a decoder gets both boxes, empty."""
    assert await setup_integration(hass, mock_config_entry)

    for box in (WATCH_BOX, UNWATCH_BOX):
        state = hass.states.get(box)
        assert state is not None
        assert state.state == ""


async def test_typing_a_line_starts_watching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the whole way: typed, stored, reloaded, and watched for."""
    assert await setup_integration(hass, mock_config_entry)
    # No list, so no sensor for it yet.
    assert hass.states.get(IN_RANGE) is None

    await _type(hass, WATCH_BOX, " KLM123 ")

    assert _watching(mock_config_entry) == "KLM123"
    # The entry reloaded with the list, so there is a sensor, and the aircraft
    # in MOCK_AIRCRAFT flying as KLM123 is on it.
    state = hass.states.get(IN_RANGE)
    assert state is not None
    assert state.state == "on"
    # And the box is empty again, ready for the next one.
    box = hass.states.get(WATCH_BOX)
    assert box is not None
    assert box.state == ""


async def test_a_second_line_goes_below_the_first(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that adding keeps what was there."""
    assert await setup_integration(hass, mock_config_entry)

    await _type(hass, WATCH_BOX, "PH-BXA")
    await _type(hass, WATCH_BOX, "7700")

    assert _watching(mock_config_entry) == "PH-BXA\n7700"


async def test_a_line_already_there_is_not_added_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the same aircraft written another way is the same line."""
    assert await setup_integration(hass, mock_config_entry)
    await _type(hass, WATCH_BOX, "PH-BXA")

    await _type(hass, WATCH_BOX, "phbxa")

    assert _watching(mock_config_entry) == "PH-BXA"


@pytest.mark.parametrize("line", ["!!", "", "A"])
async def test_a_line_nobody_can_read_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    line: str,
) -> None:
    """Test the same check the options form makes, with the line named."""
    assert await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as raised:
        await _type(hass, WATCH_BOX, line)

    assert raised.value.translation_key == "unreadable_watchlist_line"
    assert _watching(mock_config_entry) is None


async def test_removing_a_line(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test taking one line off, however it is written."""
    assert await setup_integration(hass, mock_config_entry)
    await _type(hass, WATCH_BOX, "PH-BXA")
    await _type(hass, WATCH_BOX, "KLM123")

    await _type(hass, UNWATCH_BOX, "phbxa")

    assert _watching(mock_config_entry) == "KLM123"


async def test_removing_the_last_line_removes_the_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that an empty list is no list, as the options form leaves it."""
    assert await setup_integration(hass, mock_config_entry)
    await _type(hass, WATCH_BOX, "KLM123")
    assert hass.states.get(IN_RANGE) is not None

    await _type(hass, UNWATCH_BOX, "KLM123")

    assert CONF_WATCHLIST not in mock_config_entry.options
    # The rest of the options are left as they were.
    assert mock_config_entry.options == {}
    assert hass.states.get(IN_RANGE) is None


async def test_removing_what_is_not_there_says_so(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a typo is not taken for a line that came off."""
    assert await setup_integration(hass, mock_config_entry)
    await _type(hass, WATCH_BOX, "PH-BXA")

    with pytest.raises(ServiceValidationError) as raised:
        await _type(hass, UNWATCH_BOX, "PH-BXB")

    assert raised.value.translation_key == "not_on_watchlist"
    assert _watching(mock_config_entry) == "PH-BXA"


async def test_the_actions_do_the_same(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test watch and unwatch, without saying which station."""
    assert await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_WATCH, aircraft="EC35")
    await _call(hass, SERVICE_WATCH, aircraft="484123")
    assert _watching(mock_config_entry) == "EC35\n484123"

    await _call(hass, SERVICE_UNWATCH, aircraft="ec35")
    assert _watching(mock_config_entry) == "484123"

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_WATCH, aircraft="!!")


async def test_the_actions_skip_a_feeder_beside_the_receiver(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the common setup: the feeder has no watchlist, the receiver does."""
    set_responses(aioclient_mock)
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_config_entry)
    assert await setup_integration(hass, mock_piaware_entry)
    # No boxes on an entry with no receiver to watch with.
    assert set(hass.states.async_entity_ids("text")) == {WATCH_BOX, UNWATCH_BOX}

    await _call(hass, SERVICE_WATCH, aircraft="KLM123")
    assert _watching(mock_config_entry) == "KLM123"
    assert CONF_WATCHLIST not in mock_piaware_entry.options

    # Naming the feeder says why it cannot be done rather than doing nothing.
    with pytest.raises(ServiceValidationError) as raised:
        await _call(
            hass,
            SERVICE_WATCH,
            aircraft="KLM123",
            config_entry=mock_piaware_entry.entry_id,
        )
    assert raised.value.translation_key == "station_without_aircraft"


async def test_the_actions_name_the_station_when_there_are_two(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that two antennas make the station field necessary."""
    assert await setup_integration(hass, mock_config_entry)
    assert await setup_integration(hass, mock_receiver_entry)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_WATCH, aircraft="KLM123")
    assert raised.value.translation_key == "several_receivers"

    await _call(
        hass,
        SERVICE_WATCH,
        aircraft="KLM123",
        config_entry=mock_receiver_entry.entry_id,
    )
    assert _watching(mock_receiver_entry) == "KLM123"
    assert _watching(mock_config_entry) is None

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_WATCH, aircraft="KLM123", config_entry="nope")
    assert raised.value.translation_key == "station_not_loaded"


async def test_the_actions_without_a_receiver_anywhere(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a setup with feeders only says there is no list to change."""
    set_responses(aioclient_mock)
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_WATCH, aircraft="KLM123")
    assert raised.value.translation_key == "no_watchlist_station"


async def test_the_actions_are_for_administrators(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that changing the options takes what the options form takes."""
    assert await setup_integration(hass, mock_config_entry)

    for service in (SERVICE_WATCH, SERVICE_UNWATCH):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                service,
                {"aircraft": "KLM123"},
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
    assert _watching(mock_config_entry) is None
