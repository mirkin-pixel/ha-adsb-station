"""Tests for looking up where a flight came from and where it is going."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    ADSBDB_URL,
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_PROXIMITY_RADIUS,
    CONF_ROUTE_SOURCE,
    CONF_STATS_URL,
    DOMAIN,
    FEEDER_FR24,
    ROUTE_CACHE_TTL,
    ROUTE_MISS_CACHE_TTL,
    ROUTE_SOURCE_ADSBDB,
    ROUTE_SOURCE_ROUTESET,
    ROUTESET_URL,
)
from custom_components.adsb_station.route import (
    AdsbdbLookup,
    Airport,
    FlightPosition,
    FlightRoute,
    RoutesetLookup,
    build_route_lookup,
    route_attributes,
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

# The callsign of the only aircraft in MOCK_AIRCRAFT that is inside the radius.
NEARBY_CALLSIGN = "KLM123"
ADSBDB_NEARBY_URL = ADSBDB_URL.format(callsign=NEARBY_CALLSIGN)

# Trimmed from a real answer.
ADSBDB_ANSWER: dict[str, Any] = {
    "response": {
        "flightroute": {
            "callsign": NEARBY_CALLSIGN,
            "airline": {"name": "KLM Royal Dutch Airlines", "icao": "KLM"},
            "origin": {
                "iata_code": "CDG",
                "icao_code": "LFPG",
                "municipality": "Paris",
                "name": "Charles de Gaulle International Airport",
            },
            "destination": {
                "iata_code": "AMS",
                "icao_code": "EHAM",
                "municipality": "Amsterdam",
                "name": "Amsterdam Airport Schiphol",
            },
        }
    }
}

# What routeset answers, trimmed from a real one.
ROUTESET_ANSWER: list[dict[str, Any]] = [
    {
        "_airport_codes_iata": "GOT-AMS",
        "_airports": [
            {
                "iata": "GOT",
                "icao": "ESGG",
                "location": "Gothenburg",
                "name": "Gothenburg-Landvetter Airport",
            },
            {
                "iata": "AMS",
                "icao": "EHAM",
                "location": "Amsterdam",
                "name": "Amsterdam Airport Schiphol",
            },
        ],
        "airline_code": "KLM",
        "airport_codes": "ESGG-EHAM",
        "callsign": NEARBY_CALLSIGN,
        "plausible": True,
    }
]

HERE = FlightPosition(callsign=NEARBY_CALLSIGN, latitude=52.0, longitude=5.0)


@pytest.fixture
def route_entry() -> MockConfigEntry:
    """Return an entry that looks routes up through adsbdb."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FR24 feeder",
        unique_id=MOCK_ALIAS,
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
            CONF_ROUTE_SOURCE: ROUTE_SOURCE_ADSBDB,
        },
    )


def build_lookup(
    hass: HomeAssistant, source: str = ROUTE_SOURCE_ADSBDB
) -> AdsbdbLookup | RoutesetLookup:
    """Return a lookup wired to the mocked session."""
    lookup = build_route_lookup(async_get_clientsession(hass), source)
    assert lookup is not None
    return lookup


async def test_no_lookup_without_a_source(hass: HomeAssistant) -> None:
    """Test that leaving routes off builds nothing that could ask anyone."""
    assert build_route_lookup(async_get_clientsession(hass), "none") is None
    assert build_route_lookup(async_get_clientsession(hass), "nonsense") is None


async def test_adsbdb_resolves_a_callsign(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reading a route out of an adsbdb answer."""
    aioclient_mock.get(ADSBDB_NEARBY_URL, json=ADSBDB_ANSWER)

    routes = await build_lookup(hass).async_resolve([HERE])

    route = routes[NEARBY_CALLSIGN]
    assert route.label == "CDG-AMS"
    assert route.origin == Airport(
        iata="CDG",
        icao="LFPG",
        name="Charles de Gaulle International Airport",
        location="Paris",
    )
    assert route.destination is not None
    assert route.destination.code == "AMS"


@pytest.mark.parametrize(
    "answer",
    [
        # An unknown callsign, which adsbdb says in words rather than a shape.
        {"response": "unknown callsign"},
        # A callsign it knows as an aircraft but not as a flight.
        {"response": {"aircraft": {"registration": "PH-BXA"}}},
        [],
    ],
)
async def test_adsbdb_without_a_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, answer: Any
) -> None:
    """Test that an answer holding no route resolves to nothing."""
    aioclient_mock.get(ADSBDB_NEARBY_URL, json=answer)

    assert await build_lookup(hass).async_resolve([HERE]) == {}


async def test_adsbdb_treats_a_404_as_an_answer(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a callsign the database never heard of is not an error."""
    aioclient_mock.get(ADSBDB_NEARBY_URL, status=404)
    lookup = build_lookup(hass)

    assert await lookup.async_resolve([HERE]) == {}
    # And it is remembered, so the next poll does not ask again.
    assert await lookup.async_resolve([HERE]) == {}
    assert aioclient_mock.call_count == 1


async def test_a_failing_source_costs_nothing_but_the_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a source that is down is not cached and not fatal."""
    aioclient_mock.get(ADSBDB_NEARBY_URL, status=500)
    lookup = build_lookup(hass)

    assert await lookup.async_resolve([HERE]) == {}

    # Nothing was learned, so the next poll is free to try again.
    aioclient_mock.clear_requests()
    aioclient_mock.get(ADSBDB_NEARBY_URL, json=ADSBDB_ANSWER)
    routes = await lookup.async_resolve([HERE])
    assert routes[NEARBY_CALLSIGN].label == "CDG-AMS"


async def test_an_answer_is_kept_until_it_expires(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: Any
) -> None:
    """Test that the same callsign is not asked about twice in a day."""
    aioclient_mock.get(ADSBDB_NEARBY_URL, json=ADSBDB_ANSWER)
    lookup = build_lookup(hass)

    assert (await lookup.async_resolve([HERE]))[NEARBY_CALLSIGN].label == "CDG-AMS"
    assert (await lookup.async_resolve([HERE]))[NEARBY_CALLSIGN].label == "CDG-AMS"
    assert aioclient_mock.call_count == 1

    freezer.tick(ROUTE_CACHE_TTL + timedelta(minutes=1))
    assert (await lookup.async_resolve([HERE]))[NEARBY_CALLSIGN].label == "CDG-AMS"
    assert aioclient_mock.call_count == 2


async def test_a_callsign_with_no_route_is_retried_sooner(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: Any
) -> None:
    """Test that an unknown callsign is given another chance the same day.

    A flight the database has not caught up with yet is worth asking about
    again, but not on every poll.
    """
    aioclient_mock.get(ADSBDB_NEARBY_URL, json={"response": "unknown callsign"})
    lookup = build_lookup(hass)

    assert await lookup.async_resolve([HERE]) == {}
    freezer.tick(ROUTE_MISS_CACHE_TTL - timedelta(minutes=1))
    assert await lookup.async_resolve([HERE]) == {}
    assert aioclient_mock.call_count == 1

    freezer.tick(timedelta(minutes=2))
    assert await lookup.async_resolve([HERE]) == {}
    assert aioclient_mock.call_count == 2


async def test_the_cache_does_not_grow_without_bound(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a stream of unknown callsigns cannot fill memory."""
    for number in range(4):
        aioclient_mock.get(ADSBDB_URL.format(callsign=f"TEST{number}"), status=404)
    lookup = build_lookup(hass)

    with patch("custom_components.adsb_station.route.ROUTE_CACHE_MAX_ENTRIES", 2):
        for number in range(4):
            await lookup.async_resolve(
                [FlightPosition(callsign=f"TEST{number}", latitude=52.0, longitude=5.0)]
            )

    assert len(lookup._cache) == 2


async def test_only_so_many_callsigns_are_asked_about_per_poll(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a busy sky cannot turn into a burst of requests."""
    flights = [
        FlightPosition(callsign=f"TEST{number}", latitude=52.0, longitude=5.0)
        for number in range(5)
    ]
    for flight in flights:
        aioclient_mock.get(ADSBDB_URL.format(callsign=flight.callsign), status=404)
    lookup = build_lookup(hass)

    with patch("custom_components.adsb_station.route.ROUTE_MAX_LOOKUPS_PER_POLL", 2):
        await lookup.async_resolve(flights)
        assert aioclient_mock.call_count == 2
        # The rest are still unknown, so the next poll picks them up.
        await lookup.async_resolve(flights)
        assert aioclient_mock.call_count == 4


async def test_routeset_resolves_a_callsign(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reading a route out of a routeset answer."""
    aioclient_mock.post(ROUTESET_URL, json=ROUTESET_ANSWER)

    routes = await build_lookup(hass, ROUTE_SOURCE_ROUTESET).async_resolve([HERE])

    route = routes[NEARBY_CALLSIGN]
    assert route.label == "GOT-AMS"
    assert route.destination is not None
    assert route.destination.location == "Amsterdam"

    # It is told where the aircraft was heard, which is what lets it judge.
    assert aioclient_mock.mock_calls[0][2] == {
        "planes": [{"callsign": NEARBY_CALLSIGN, "lat": 52.0, "lng": 5.0}]
    }


async def test_routeset_asks_about_every_callsign_at_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a batch of callsigns costs one request rather than many."""
    aioclient_mock.post(ROUTESET_URL, json=[])
    flights = [
        FlightPosition(callsign=f"TEST{number}", latitude=52.0, longitude=5.0)
        for number in range(5)
    ]

    await build_lookup(hass, ROUTE_SOURCE_ROUTESET).async_resolve(flights)

    assert aioclient_mock.call_count == 1
    assert len(aioclient_mock.mock_calls[0][2]["planes"]) == 5


async def test_routeset_keeps_the_two_ends_of_a_flight_with_a_stop(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a multi-leg route is reported as where it starts and ends."""
    answer = [
        {
            **ROUTESET_ANSWER[0],
            "_airports": [
                {"iata": "GOT", "icao": "ESGG", "location": "Gothenburg", "name": "A"},
                {"iata": "CPH", "icao": "EKCH", "location": "Copenhagen", "name": "B"},
                {"iata": "AMS", "icao": "EHAM", "location": "Amsterdam", "name": "C"},
            ],
        }
    ]
    aioclient_mock.post(ROUTESET_URL, json=answer)

    routes = await build_lookup(hass, ROUTE_SOURCE_ROUTESET).async_resolve([HERE])

    assert routes[NEARBY_CALLSIGN].label == "GOT-AMS"


@pytest.mark.parametrize(
    "answer",
    [
        # The API saying it has nothing.
        [{"callsign": NEARBY_CALLSIGN, "airport_codes": "unknown", "_airports": []}],
        # A route it found but does not believe belongs to this aircraft.
        [{**ROUTESET_ANSWER[0], "plausible": False}],
        # Nothing usable in the answer at all.
        [{**ROUTESET_ANSWER[0], "_airports": []}],
        ["not a route"],
        {"planes": []},
    ],
)
async def test_routeset_without_a_usable_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, answer: Any
) -> None:
    """Test that a doubtful route is left out rather than guessed at."""
    aioclient_mock.post(ROUTESET_URL, json=answer)

    assert await build_lookup(hass, ROUTE_SOURCE_ROUTESET).async_resolve([HERE]) == {}


async def test_a_failing_routeset_is_not_held_against_the_callsign(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that routeset being down is not remembered as "no route"."""
    aioclient_mock.post(ROUTESET_URL, status=502)
    lookup = build_lookup(hass, ROUTE_SOURCE_ROUTESET)

    assert await lookup.async_resolve([HERE]) == {}
    assert not lookup._cache

    aioclient_mock.clear_requests()
    aioclient_mock.post(ROUTESET_URL, json=ROUTESET_ANSWER)
    assert (await lookup.async_resolve([HERE]))[NEARBY_CALLSIGN].label == "GOT-AMS"


async def test_route_attributes_leave_out_what_is_not_known() -> None:
    """Test that a half-known route says only what it knows."""
    assert route_attributes(None) == {}
    assert route_attributes(
        FlightRoute(
            origin=Airport(iata=None, icao="EHAM", name=None, location=None),
            destination=None,
        )
    ) == {"route": "EHAM-?", "origin": "EHAM"}
    # An airport with no code at all leaves nothing to call the route.
    nameless = Airport(iata=None, icao=None, name=None, location=None)
    assert FlightRoute(origin=nameless, destination=None).label is None
    assert route_attributes(FlightRoute(origin=nameless, destination=None)) == {}


async def test_adsbdb_answering_with_blanks(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that empty and missing fields are treated as absent, not as text."""
    aioclient_mock.get(
        ADSBDB_NEARBY_URL,
        json={
            "response": {
                "flightroute": {
                    "airline": {"name": "   "},
                    "origin": {"iata_code": "CDG", "name": None},
                    "destination": "not an airport",
                }
            }
        },
    )

    route = (await build_lookup(hass).async_resolve([HERE]))[NEARBY_CALLSIGN]

    assert route.label == "CDG-?"
    assert route.origin is not None
    assert route.origin.name is None
    assert route.destination is None


async def test_routeset_skips_an_entry_without_a_callsign(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an answer we cannot tie to an aircraft is passed over."""
    aioclient_mock.post(
        ROUTESET_URL,
        json=[{**ROUTESET_ANSWER[0], "callsign": ""}, *ROUTESET_ANSWER],
    )

    routes = await build_lookup(hass, ROUTE_SOURCE_ROUTESET).async_resolve([HERE])

    assert list(routes) == [NEARBY_CALLSIGN]


async def test_the_nearby_aircraft_carry_their_route(
    hass: HomeAssistant,
    route_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the whole way through: a route reaches the entity attributes."""
    set_responses(aioclient_mock)
    aioclient_mock.get(ADSBDB_NEARBY_URL, json=ADSBDB_ANSWER)

    assert await setup_integration(hass, route_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    nearby = state.attributes["aircraft"]
    assert len(nearby) == 1
    assert nearby[0]["flight"] == NEARBY_CALLSIGN
    assert nearby[0]["route"] == "CDG-AMS"
    assert nearby[0]["origin"] == "CDG"
    assert nearby[0]["origin_location"] == "Paris"
    assert nearby[0]["destination"] == "AMS"
    # The answer calls this one KLM Royal Dutch Airlines and is not read for
    # it: the airline comes off the callsign against the table we ship, so it
    # reads the same on the flights no source knows.
    assert nearby[0]["airline"] == "KLM"

    overhead = hass.states.get("binary_sensor.t_ehxx23_aircraft_overhead")
    assert overhead is not None
    assert overhead.attributes["aircraft"][0]["route"] == "CDG-AMS"


async def test_an_aircraft_without_a_callsign_is_not_asked_about(
    hass: HomeAssistant,
    route_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a nearby aircraft broadcasting no flight number is left alone.

    There is nothing to ask about, and the mocker refuses any request that was
    not registered, so reaching a state at all is the assertion.
    """
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 1000,
            "aircraft": [{"hex": "484123", "lat": 52.01, "lon": 5.0, "altitude": 2000}],
        },
    )

    assert await setup_integration(hass, route_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    assert state.state == "1"
    assert "route" not in state.attributes["aircraft"][0]


async def test_nothing_is_asked_when_routes_are_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the default setup reaches nothing outside your network.

    The mocker refuses a request it was not told about, so an aircraft going
    past without a single route request is the whole assertion.
    """
    assert await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.t_ehxx23_aircraft_nearby")
    assert state is not None
    assert "route" not in state.attributes["aircraft"][0]
    assert mock_config_entry.runtime_data.route_lookup is None
