"""Where a flight came from and where it is going, from routeset.

No broadcast carries a route, so this asks adsb.im's routeset, as tar1090
does. It checks each route against the aircraft's position, which rules out
the other legs a callsign flies that day. Only nearby and tapped aircraft
are asked about, answers are cached, and requests are at least thirty
seconds apart.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .const import (
    ROUTE_CACHE_MAX_ENTRIES,
    ROUTE_CACHE_TTL,
    ROUTE_MAX_LOOKUPS_PER_POLL,
    ROUTE_MISS_CACHE_TTL,
    ROUTESET_MAX_PLANES,
    ROUTESET_MIN_INTERVAL,
    ROUTESET_URL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

# A route lookup is a courtesy from someone else's server and never worth
# holding up a poll for, so it gets less patience than the receiver does.
TIMEOUT = 8


@dataclass(frozen=True, kw_only=True)
class Airport:
    """One end of a route."""

    iata: str | None
    icao: str | None
    name: str | None
    # The city the airport serves, which is what a notification wants to say.
    location: str | None
    # Where it is, for drawing the route on a map.
    latitude: float | None = None
    longitude: float | None = None

    @property
    def code(self) -> str | None:
        """Return the short code to show, preferring the one people know."""
        return self.iata or self.icao


@dataclass(frozen=True, kw_only=True)
class FlightRoute:
    """Where a callsign is flying from and to."""

    origin: Airport | None
    destination: Airport | None

    @property
    def label(self) -> str | None:
        """Return the route as one string, or None if neither end is known."""
        first = None if self.origin is None else self.origin.code
        last = None if self.destination is None else self.destination.code
        if first is None and last is None:
            return None
        return f"{first or '?'}-{last or '?'}"


@dataclass(frozen=True, kw_only=True)
class FlightPosition:
    """A callsign, and where it was heard, for routeset to check the route."""

    callsign: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, kw_only=True)
class _CachedRoute:
    """What we last learned about a callsign, and until when to believe it."""

    route: FlightRoute | None
    expires: datetime


def _text(value: Any) -> str | None:
    """Return a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class RouteLookupError(Exception):
    """Routeset could not be asked, or did not answer."""


async def _until(waiter: asyncio.Future[None], seconds: float) -> None:
    """Wait for the waiter to be done, or for the seconds to pass."""
    await asyncio.wait((waiter,), timeout=seconds)


class RouteLookup:
    """Resolves callsigns to routes, remembering what it has been told."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the lookup."""
        self._session = session
        self._cache: dict[str, _CachedRoute] = {}
        self._asked_at: datetime | None = None
        # Tapped callsigns waiting for a turn; whoever asks next takes them along.
        self._waiting: dict[str, tuple[FlightPosition, asyncio.Future[None]]] = {}

    async def async_resolve(
        self, flights: Sequence[FlightPosition]
    ) -> dict[str, FlightRoute]:
        """Return the route of every callsign we know, asking about the rest.

        Within thirty seconds of the last question the rest wait for the next
        poll. Never raises.
        """
        now = dt_util.utcnow()
        self._drop_expired(now)
        known, pending = self._split(flights)
        if not pending or self._remaining(now) > 0:
            return known

        waiting = [flight for flight, _ in self._waiting.values()]
        answers = await self._async_ask([*waiting, *pending.values()], now)
        for callsign in pending:
            if (route := (answers or {}).get(callsign)) is not None:
                known[callsign] = route
        return known

    async def async_look_up(self, flight: FlightPosition) -> FlightRoute | None:
        """Return the route of one tapped callsign, or None if nobody knows it.

        Waits for routeset's next turn, at most thirty seconds away; a
        poll that takes that turn asks about this callsign too. Raises
        RouteLookupError when routeset could not answer.
        """
        callsign = flight.callsign
        while True:
            now = dt_util.utcnow()
            self._drop_expired(now)
            if (cached := self._cache.get(callsign)) is not None:
                return cached.route
            remaining = self._remaining(now)
            if remaining <= 0:
                break
            if callsign not in self._waiting:
                waiter = asyncio.get_running_loop().create_future()
                self._waiting[callsign] = (flight, waiter)
            waiter = self._waiting[callsign][1]
            await _until(waiter, remaining)
            if waiter.done():
                # Asked about by someone else; no answer in the cache means
                # that question failed.
                if (cached := self._cache.get(callsign)) is not None:
                    return cached.route
                raise RouteLookupError

        waiting = [other for other, _ in self._waiting.values()]
        answers = await self._async_ask([flight, *waiting], now)
        if answers is None:
            raise RouteLookupError
        return answers.get(callsign)

    def _remaining(self, now: datetime) -> float:
        """Return the seconds until routeset may be asked again."""
        if self._asked_at is None:
            return 0.0
        return (self._asked_at + ROUTESET_MIN_INTERVAL - now).total_seconds()

    async def _async_ask(
        self, flights: Sequence[FlightPosition], now: datetime
    ) -> dict[str, FlightRoute] | None:
        """Take routeset's turn for these callsigns, first ones first.

        Return what it answered, or None when it could not be asked. Every
        tap waiting on a callsign asked about is told, either way.
        """
        asking: dict[str, FlightPosition] = {}
        for flight in flights:
            asking.setdefault(flight.callsign, flight)
        if len(asking) > ROUTE_MAX_LOOKUPS_PER_POLL:
            _LOGGER.debug(
                "Asking about %d of %d new callsigns this poll; the rest wait "
                "for the next one",
                ROUTE_MAX_LOOKUPS_PER_POLL,
                len(asking),
            )
            asking = dict(list(asking.items())[:ROUTE_MAX_LOOKUPS_PER_POLL])
        told = [self._waiting.pop(c)[1] for c in asking if c in self._waiting]

        self._asked_at = now
        try:
            answers = await self._async_fetch(list(asking.values()))
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            # Nothing is cached on a failure, so the next poll tries again.
            _LOGGER.debug("Could not reach routeset for a route: %s", err)
            return None
        else:
            for callsign in asking:
                self._remember(callsign, answers.get(callsign), now)
            return answers
        finally:
            for waiter in told:
                if not waiter.done():
                    waiter.set_result(None)

    def _split(
        self, flights: Sequence[FlightPosition]
    ) -> tuple[dict[str, FlightRoute], dict[str, FlightPosition]]:
        """Return the routes already known, and the callsigns still to ask."""
        known: dict[str, FlightRoute] = {}
        pending: dict[str, FlightPosition] = {}
        for flight in flights:
            if (cached := self._cache.get(flight.callsign)) is not None:
                if cached.route is not None:
                    known[flight.callsign] = cached.route
            else:
                pending.setdefault(flight.callsign, flight)
        return known, pending

    def _drop_expired(self, now: datetime) -> None:
        """Forget what we are no longer entitled to believe."""
        for callsign in [
            callsign
            for callsign, cached in self._cache.items()
            if cached.expires <= now
        ]:
            del self._cache[callsign]

    def _remember(
        self, callsign: str, route: FlightRoute | None, now: datetime
    ) -> None:
        """Hold on to an answer, including the answer that there is none."""
        while len(self._cache) >= ROUTE_CACHE_MAX_ENTRIES:
            # Insertion order, so this is the answer we have held longest.
            del self._cache[next(iter(self._cache))]
        ttl = ROUTE_CACHE_TTL if route is not None else ROUTE_MISS_CACHE_TTL
        self._cache[callsign] = _CachedRoute(route=route, expires=now + ttl)

    async def _async_fetch(
        self, flights: Sequence[FlightPosition]
    ) -> dict[str, FlightRoute]:
        """Ask about every callsign at once, in batches the API accepts.

        A failed batch fails the whole answer; nothing is cached, so the next
        poll asks again.
        """
        routes: dict[str, FlightRoute] = {}
        for start in range(0, len(flights), ROUTESET_MAX_PLANES):
            batch = flights[start : start + ROUTESET_MAX_PLANES]
            routes.update(await self._async_batch(batch))
        return routes

    async def _async_batch(
        self, flights: Sequence[FlightPosition]
    ) -> dict[str, FlightRoute]:
        """Ask about one batch of callsigns."""
        planes = [
            {
                "callsign": flight.callsign,
                # Required by the API; in practice every flight asked has one.
                "lat": flight.latitude or 0.0,
                "lng": flight.longitude or 0.0,
            }
            for flight in flights
        ]
        async with asyncio.timeout(TIMEOUT):
            response = await self._session.post(
                ROUTESET_URL,
                json={"planes": planes},
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = await response.json(content_type=None)

        if not isinstance(payload, list):
            _LOGGER.debug("routeset answered with %s rather than a list", type(payload))
            return {}

        routes: dict[str, FlightRoute] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            callsign = _text(item.get("callsign"))
            if callsign is None:
                continue
            if (route := _routeset_route(item)) is not None:
                routes[callsign] = route
        return routes


def _routeset_route(item: dict[str, Any]) -> FlightRoute | None:
    """Read one entry of a routeset answer."""
    # Unknown or implausible: no route beats a wrong one.
    if _text(item.get("airport_codes")) in (None, "unknown"):
        return None
    if item.get("plausible") is False:
        _LOGGER.debug(
            "routeset does not believe %s is on %s from where it was heard",
            item.get("callsign"),
            item.get("airport_codes"),
        )
        return None

    airports = [
        _routeset_airport(airport)
        for airport in item.get("_airports", [])
        if isinstance(airport, dict)
    ]
    if not airports:
        return None
    # With a stop on the way, the first and last airports. The airline is not
    # read: routeset gives only the code, the shipped table gives the name.
    return FlightRoute(
        origin=airports[0],
        destination=airports[-1] if len(airports) > 1 else None,
    )


def _routeset_airport(payload: dict[str, Any]) -> Airport:
    """Read one airport of a routeset answer."""
    return Airport(
        iata=_text(payload.get("iata")),
        icao=_text(payload.get("icao")),
        name=_text(payload.get("name")),
        location=_text(payload.get("location")),
        latitude=_coordinate(payload.get("lat")),
        longitude=_coordinate(payload.get("lon")),
    )


def _coordinate(value: Any) -> float | None:
    """Return a latitude or longitude, or None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def route_points(route: FlightRoute | None) -> dict[str, Any] | None:
    """Describe a route for a map: both ends, each with where it is, or None."""
    if route is None or route.origin is None or route.destination is None:
        return None
    ends = []
    for airport in (route.origin, route.destination):
        if airport.latitude is None or airport.longitude is None:
            return None
        ends.append(
            {
                "code": airport.code,
                "location": airport.location,
                "latitude": airport.latitude,
                "longitude": airport.longitude,
            }
        )
    return {"origin": ends[0], "destination": ends[1]}


def build_route_lookup(
    session: aiohttp.ClientSession, enabled: bool
) -> RouteLookup | None:
    """Return a lookup, or None when routes are switched off."""
    return RouteLookup(session) if enabled else None


def route_attributes(route: FlightRoute | None) -> dict[str, Any]:
    """Describe a route for the attributes of an aircraft, leaving out unknowns."""
    if route is None:
        return {}
    attributes: dict[str, Any] = {}
    if (label := route.label) is not None:
        attributes["route"] = label
    for key, airport in (("origin", route.origin), ("destination", route.destination)):
        if airport is None:
            continue
        if (code := airport.code) is not None:
            attributes[key] = code
        if airport.location is not None:
            attributes[f"{key}_location"] = airport.location
        if airport.name is not None:
            attributes[f"{key}_name"] = airport.name
    return attributes
