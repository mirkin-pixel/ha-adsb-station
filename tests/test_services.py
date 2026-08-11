"""Tests for the services that answer."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN
from custom_components.adsb_station.services import (
    SERVICE_LIST_AIRCRAFT,
    SERVICE_LOOK_UP_AIRCRAFT,
)

from .conftest import MOCK_PIAWARE, PIAWARE_URL, set_responses, setup_integration

# Two in range and one far out, so a service can be told from the nearby list.
MOCK_SKY: dict[str, Any] = {
    "now": 1636387404.0,
    "messages": 10,
    "aircraft": [
        {
            "hex": "484123",
            "flight": "KLM123",
            "lat": 52.01,
            "lon": 5.0,
            "alt_baro": 2000,
            "gs": 250,
        },
        {
            "hex": "3c6444",
            "flight": "DLH99",
            "lat": 52.005,
            "lon": 5.0,
            "alt_baro": 35000,
            "category": "A3",
        },
        # A hundred kilometres north, so well outside the ten kilometre radius
        {
            "hex": "480123",
            "flight": "NAF11",
            "lat": 53.0,
            "lon": 5.0,
            "alt_baro": 8000,
            "category": "A7",
        },
    ],
}


async def _call(
    hass: HomeAssistant, service: str, **data: Any
) -> dict[str, Any] | None:
    """Call one of the services and return its answer."""
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aircraft: dict[str, Any] | None = None,
) -> None:
    set_responses(aioclient_mock, aircraft=aircraft or MOCK_SKY)
    assert await setup_integration(hass, entry)


@pytest.mark.parametrize("wanted", ["484123", "484123".upper(), "klm123", " KLM123 "])
async def test_look_up_by_hex_or_callsign(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    wanted: str,
) -> None:
    """Test that either name finds the aircraft, in either case."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(hass, SERVICE_LOOK_UP_AIRCRAFT, aircraft=wanted)

    aircraft = answer["aircraft"]
    assert aircraft["hex"] == "484123"
    assert aircraft["flight"] == "KLM123"
    assert aircraft["altitude"] == 2000
    # The distance the attributes leave out, and the direction no attribute
    # set carries at all
    assert aircraft["distance"] == 1.1
    assert aircraft["sector"] == "n"


async def test_look_up_an_aircraft_that_is_not_there(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that hearing nothing is an answer rather than a failure."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(hass, SERVICE_LOOK_UP_AIRCRAFT, aircraft="BAW1")

    assert answer == {"aircraft": None}


async def test_look_up_reaches_beyond_the_radius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft nowhere near you can still be looked up."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(hass, SERVICE_LOOK_UP_AIRCRAFT, aircraft="NAF11")

    assert answer["aircraft"]["hex"] == "480123"
    assert answer["aircraft"]["distance"] == pytest.approx(111.2, abs=0.5)


async def test_list_everything_nearest_first(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that without a filter the answer is the whole sky, in order."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(hass, SERVICE_LIST_AIRCRAFT)

    assert [item["hex"] for item in answer["aircraft"]] == [
        "3c6444",
        "484123",
        "480123",
    ]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"max_distance": 10}, ["3c6444", "484123"]),
        ({"min_altitude": 5000}, ["3c6444", "480123"]),
        ({"max_altitude": 5000}, ["484123"]),
        ({"min_altitude": 5000, "max_altitude": 10000}, ["480123"]),
        ({"category": "A7"}, ["480123"]),
        # Written however it arrives, because it is a code and not a word
        ({"category": "a7"}, ["480123"]),
        ({"category": "B6"}, []),
        # NAF11 has no dbFlags but its address sits in the range the
        # Netherlands keeps for its own aircraft, so the table answers for it
        ({"military": True}, ["480123"]),
        ({"military": False}, ["3c6444", "484123"]),
        ({"max_distance": 10, "min_altitude": 10000}, ["3c6444"]),
    ],
)
async def test_list_filters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    filters: dict[str, Any],
    expected: list[str],
) -> None:
    """Test each filter on its own, and two of them together."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(hass, SERVICE_LIST_AIRCRAFT, **filters)

    assert [item["hex"] for item in answer["aircraft"]] == expected


async def test_aircraft_without_a_figure_are_left_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a filter excludes what it cannot judge."""
    await _setup(
        hass,
        mock_config_entry,
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            # Heard over Mode S alone: no position and no altitude
            "aircraft": [{"hex": "484125", "flight": "EZY22"}],
        },
    )

    # It is there when nothing is asked of it
    answer = await _call(hass, SERVICE_LIST_AIRCRAFT)
    assert [item["hex"] for item in answer["aircraft"]] == ["484125"]
    assert answer["aircraft"][0]["distance"] is None
    assert answer["aircraft"][0]["sector"] is None

    for filters in (
        {"max_distance": 500},
        {"min_altitude": 0},
        {"max_altitude": 60000},
    ):
        answer = await _call(hass, SERVICE_LIST_AIRCRAFT, **filters)
        assert answer["aircraft"] == [], filters


async def test_the_station_may_be_named(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test asking one station by name, and asking one that cannot answer."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    answer = await _call(
        hass,
        SERVICE_LOOK_UP_AIRCRAFT,
        aircraft="KLM123",
        config_entry=mock_config_entry.entry_id,
    )
    assert answer["aircraft"]["hex"] == "484123"

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_LOOK_UP_AIRCRAFT,
            aircraft="KLM123",
            config_entry="not-a-station",
        )


async def test_a_feeder_beside_the_receiver_is_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the common setup: several feeders, one of them with the decoder."""
    await _setup(hass, mock_config_entry, aioclient_mock)
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    # The PiAware entry has no receiver of its own, so it is not a candidate
    # and the field can still be left out
    answer = await _call(hass, SERVICE_LOOK_UP_AIRCRAFT, aircraft="KLM123")
    assert answer["aircraft"]["hex"] == "484123"

    # Naming it explicitly says so rather than answering with nothing
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_LOOK_UP_AIRCRAFT,
            aircraft="KLM123",
            config_entry=mock_piaware_entry.entry_id,
        )


async def test_two_receivers_need_saying_which(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that two antennas make the station field necessary."""
    await _setup(hass, mock_config_entry, aioclient_mock)
    assert await setup_integration(hass, mock_receiver_entry)

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_LIST_AIRCRAFT)

    answer = await _call(
        hass, SERVICE_LIST_AIRCRAFT, config_entry=mock_config_entry.entry_id
    )
    assert len(answer["aircraft"]) == 3


async def test_without_a_station_at_all(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a setup with no receiver says so."""
    set_responses(aioclient_mock)
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_LIST_AIRCRAFT)
