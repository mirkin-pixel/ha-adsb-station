"""Tests for looking up what an aircraft looks like."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_LOOK_UP_PHOTOS,
    CONF_PROXIMITY_RADIUS,
    CONF_STATS_URL,
    CONF_WATCHLIST,
    DB_FLAG_PIA,
    DOMAIN,
    EVENT_WATCHLIST_MATCH,
    FEEDER_FR24,
    PHOTO_CACHE_TTL,
    PHOTO_URL,
    PHOTO_USER_AGENT,
)
from custom_components.adsb_station.photo import (
    AircraftPhoto,
    PhotoLookup,
    build_photo_lookup,
    photo_attributes,
    photographable,
)

from .conftest import (
    AIRCRAFT_URL,
    DEFAULT_PORT,
    MOCK_ALIAS,
    MOCK_HOST,
    STATS_URL,
    set_responses,
    setup_integration,
)

# The only aircraft in MOCK_AIRCRAFT that is inside the radius.
NEARBY_HEX = "484123"

# What Planespotters answers, trimmed from a real one.
PLANESPOTTERS_ANSWER: dict[str, Any] = {
    "photos": [
        {
            "id": "1978923",
            "thumbnail": {
                "src": "https://t.plnspttrs.net/27134/1978923_ff0b1a1dbf_t.jpg",
                "size": {"width": 200, "height": 133},
            },
            "thumbnail_large": {
                "src": "https://t.plnspttrs.net/27134/1978923_ff0b1a1dbf_280.jpg",
                "size": {"width": 420, "height": 280},
            },
            "link": "https://www.planespotters.net/photo/1978923/ph-bvs?utm_source=api",
            "photographer": "Jan Seler",
        }
    ]
}
PHOTO = AircraftPhoto(
    src="https://t.plnspttrs.net/27134/1978923_ff0b1a1dbf_280.jpg",
    link="https://www.planespotters.net/photo/1978923/ph-bvs?utm_source=api",
    photographer="Jan Seler",
)
NO_PHOTO: dict[str, Any] = {"photos": []}


def photo_url(hex_code: str) -> str:
    """Return where the photo of one address is asked for."""
    return PHOTO_URL.format(hex=hex_code)


@pytest.fixture
def photo_entry() -> MockConfigEntry:
    """Return an entry that looks photos up."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FR24 feeder",
        unique_id=MOCK_ALIAS,
        version=3,
        data={
            "host": MOCK_HOST,
            "port": DEFAULT_PORT,
            CONF_FEEDER_TYPE: FEEDER_FR24,
            CONF_AIRCRAFT_URL: AIRCRAFT_URL,
            CONF_STATS_URL: STATS_URL,
            "receiver_features": [],
        },
        options={
            CONF_SCAN_INTERVAL: 15,
            CONF_PROXIMITY_RADIUS: 10,
            CONF_LOOK_UP_PHOTOS: True,
        },
    )


def build_lookup(hass: HomeAssistant) -> PhotoLookup:
    """Return a lookup wired to the mocked session."""
    lookup = build_photo_lookup(async_get_clientsession(hass), True)
    assert lookup is not None
    return lookup


async def test_no_lookup_when_photos_are_off(hass: HomeAssistant) -> None:
    """Test that leaving photos off builds nothing that could ask anyone."""
    assert build_photo_lookup(async_get_clientsession(hass), False) is None


async def test_resolves_an_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reading a photo out of an answer, and saying who is asking."""
    aioclient_mock.get(photo_url(NEARBY_HEX), json=PLANESPOTTERS_ANSWER)

    photos = await build_lookup(hass).async_resolve([NEARBY_HEX])

    # The larger of the two thumbnails, which is what a card wants.
    assert photos == {NEARBY_HEX: PHOTO}
    # Planespotters refuses a request that does not name itself.
    assert aioclient_mock.mock_calls[0][3]["User-Agent"] == PHOTO_USER_AGENT


async def test_an_address_in_capitals_is_the_same_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a decoder writing the hex in capitals still gets its photo."""
    aioclient_mock.get(photo_url(NEARBY_HEX), json=PLANESPOTTERS_ANSWER)

    photos = await build_lookup(hass).async_resolve(["484123", "484123".upper()])

    assert photos == {NEARBY_HEX: PHOTO}
    assert aioclient_mock.call_count == 1


async def test_falls_back_on_the_small_thumbnail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an answer with only the small thumbnail still has a photo."""
    answer = {"photos": [{**PLANESPOTTERS_ANSWER["photos"][0]}]}
    del answer["photos"][0]["thumbnail_large"]
    aioclient_mock.get(photo_url(NEARBY_HEX), json=answer)

    photos = await build_lookup(hass).async_resolve([NEARBY_HEX])

    assert photos[NEARBY_HEX].src.endswith("_t.jpg")


@pytest.mark.parametrize(
    "answer",
    [
        NO_PHOTO,
        # The terms ask for the photographer beside a photo and for the photo
        # to lead to its page, so one missing either cannot be shown.
        {"photos": [{**PLANESPOTTERS_ANSWER["photos"][0], "photographer": " "}]},
        {"photos": [{**PLANESPOTTERS_ANSWER["photos"][0], "link": None}]},
        {
            "photos": [
                {
                    **PLANESPOTTERS_ANSWER["photos"][0],
                    "thumbnail": {},
                    "thumbnail_large": "not a thumbnail",
                }
            ]
        },
        {"photos": ["not a photo"]},
        {"photos": "none"},
        ["not an object"],
    ],
)
async def test_without_a_usable_photo(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, answer: Any
) -> None:
    """Test that a photo that cannot be shown properly is left out."""
    aioclient_mock.get(photo_url(NEARBY_HEX), json=answer)

    assert await build_lookup(hass).async_resolve([NEARBY_HEX]) == {}


@pytest.mark.parametrize(
    ("hex_code", "expected"),
    [
        ("484123", True),
        ("43C6E1", True),
        # readsb marks an address that is not an ICAO one with a tilde.
        ("~484123", False),
        ("48412", False),
        ("", False),
    ],
)
async def test_only_icao_addresses_are_asked_about(
    hex_code: str, expected: bool
) -> None:
    """Test that an address the database is not keyed on is never sent."""
    assert photographable(hex_code) is expected


async def test_an_address_that_is_not_icao_is_never_sent(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a TIS-B track is passed over without a request."""
    assert await build_lookup(hass).async_resolve(["~484123"]) == {}
    assert aioclient_mock.call_count == 0


async def test_a_failing_source_costs_nothing_but_the_photo(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the source being down is not remembered as "no photo"."""
    aioclient_mock.get(photo_url(NEARBY_HEX), status=503)
    lookup = build_lookup(hass)

    # The second address waits: a source that just failed is not sent the
    # next request straight away. The mocker would refuse it if it were.
    assert await lookup.async_resolve([NEARBY_HEX, "484124"]) == {}
    assert aioclient_mock.call_count == 1
    assert not lookup._cache

    # Nothing was learned, so the next poll is free to try again.
    aioclient_mock.clear_requests()
    aioclient_mock.get(photo_url(NEARBY_HEX), json=PLANESPOTTERS_ANSWER)
    assert await lookup.async_resolve([NEARBY_HEX]) == {NEARBY_HEX: PHOTO}


async def test_an_answer_is_kept_for_a_day(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: Any
) -> None:
    """Test that the same airframe is asked about once a day, and no less.

    A day is as long as the terms let an answer be kept.
    """
    aioclient_mock.get(photo_url(NEARBY_HEX), json=PLANESPOTTERS_ANSWER)
    lookup = build_lookup(hass)

    assert await lookup.async_resolve([NEARBY_HEX]) == {NEARBY_HEX: PHOTO}
    assert await lookup.async_resolve([NEARBY_HEX]) == {NEARBY_HEX: PHOTO}
    assert aioclient_mock.call_count == 1

    freezer.tick(PHOTO_CACHE_TTL + timedelta(minutes=1))
    assert await lookup.async_resolve([NEARBY_HEX]) == {NEARBY_HEX: PHOTO}
    assert aioclient_mock.call_count == 2


async def test_an_airframe_without_a_photo_is_not_asked_about_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that "no photo" is an answer too, and is remembered."""
    aioclient_mock.get(photo_url(NEARBY_HEX), json=NO_PHOTO)
    lookup = build_lookup(hass)

    assert await lookup.async_resolve([NEARBY_HEX]) == {}
    assert await lookup.async_resolve([NEARBY_HEX]) == {}
    assert aioclient_mock.call_count == 1


async def test_the_cache_does_not_grow_without_bound(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a stream of new airframes cannot fill memory."""
    for number in range(4):
        aioclient_mock.get(photo_url(f"48412{number}"), json=NO_PHOTO)
    lookup = build_lookup(hass)

    with patch("custom_components.adsb_station.photo.PHOTO_CACHE_MAX_ENTRIES", 2):
        for number in range(4):
            await lookup.async_resolve([f"48412{number}"])

    assert len(lookup._cache) == 2


async def test_only_so_many_airframes_are_asked_about_per_poll(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a busy sky cannot turn into a burst of requests."""
    addresses = [f"48412{number}" for number in range(5)]
    for hex_code in addresses:
        aioclient_mock.get(photo_url(hex_code), json=NO_PHOTO)
    lookup = build_lookup(hass)

    with patch("custom_components.adsb_station.photo.PHOTO_MAX_LOOKUPS_PER_POLL", 2):
        await lookup.async_resolve(addresses)
        assert aioclient_mock.call_count == 2
        # The rest are still unknown, so the next poll picks them up.
        await lookup.async_resolve(addresses)
        assert aioclient_mock.call_count == 4
        assert str(aioclient_mock.mock_calls[3][1]).endswith("/484123")


async def test_photo_attributes_come_as_a_set() -> None:
    """Test that a photo is never described without its credit and link."""
    assert photo_attributes(None) == {}
    assert photo_attributes(PHOTO) == {
        "photo": PHOTO.src,
        "photo_link": PHOTO.link,
        "photographer": "Jan Seler",
    }


async def test_the_nearby_aircraft_carry_their_photo(
    hass: HomeAssistant,
    photo_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the whole way through: a photo reaches the entity attributes.

    Only the nearby aircraft is asked about. The mocker refuses any request
    it was not told about, so the other two going unasked is asserted too.
    """
    set_responses(aioclient_mock)
    aioclient_mock.get(photo_url(NEARBY_HEX), json=PLANESPOTTERS_ANSWER)

    assert await setup_integration(hass, photo_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    nearby = state.attributes["aircraft"]
    assert nearby[0]["hex"] == NEARBY_HEX
    assert nearby[0]["photo"] == PHOTO.src
    assert nearby[0]["photo_link"] == PHOTO.link
    assert nearby[0]["photographer"] == "Jan Seler"

    overhead = hass.states.get("binary_sensor.t_ehxx23_aircraft_overhead")
    assert overhead is not None
    assert overhead.attributes["aircraft"][0]["photographer"] == "Jan Seler"


async def test_a_watched_aircraft_gets_its_photo_wherever_it_is(
    hass: HomeAssistant,
    photo_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the watchlist has no radius for photos either.

    The nearby aircraft beside it has no photo, and goes without rather than
    being handed the watched one's.
    """
    far_away = {"hex": "484124", "flight": "TRA45", "lat": 53.0, "lon": 5.0}
    nearby = {"hex": NEARBY_HEX, "lat": 52.01, "lon": 5.0, "altitude": 2000}
    matches: list[Event] = []
    hass.bus.async_listen(EVENT_WATCHLIST_MATCH, matches.append)
    photo_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        photo_entry, options={**photo_entry.options, CONF_WATCHLIST: "484124"}
    )
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 1000,
            "aircraft": [far_away, nearby],
        },
    )
    aioclient_mock.get(photo_url("484124"), json=PLANESPOTTERS_ANSWER)
    aioclient_mock.get(photo_url(NEARBY_HEX), json=NO_PHOTO)

    assert await hass.config_entries.async_setup(photo_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.t_ehxx23_watchlist_in_range")
    assert state is not None
    assert state.attributes["aircraft"][0]["photo"] == PHOTO.src
    assert matches[0].data["photographer"] == "Jan Seler"
    nearby_state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert nearby_state is not None
    assert "photo" not in nearby_state.attributes["aircraft"][0]


async def test_an_aircraft_under_a_pia_address_is_not_asked_about(
    hass: HomeAssistant,
    photo_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a borrowed address is not taken for the airframe flying it.

    The mocker refuses any request it was not told about, so reaching a state
    at all is the assertion.
    """
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 1000,
            "aircraft": [
                {
                    "hex": "a1b2c3",
                    "lat": 52.01,
                    "lon": 5.0,
                    "altitude": 2000,
                    "dbFlags": DB_FLAG_PIA,
                }
            ],
        },
    )

    assert await setup_integration(hass, photo_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    assert state.state == "1"
    assert "photo" not in state.attributes["aircraft"][0]


async def test_nothing_is_asked_when_photos_are_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the default setup asks nobody for a photo."""
    assert await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    assert "photo" not in state.attributes["aircraft"][0]
    assert mock_config_entry.runtime_data.photo_lookup is None
