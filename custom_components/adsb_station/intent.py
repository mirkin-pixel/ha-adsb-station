"""Five spoken questions for Assist, answered from the last poll.

The sentences ship as files and must be copied into the configuration
directory, by hand or with `adsb_station.install_sentences`.
"""

from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util.unit_system import UnitSystem

from .coordinator import (
    AdsbStationDataUpdateCoordinator,
    AircraftStats,
    AircraftSummary,
    receivers,
    sector_from,
)
from .speech import (
    altitude_of,
    counted,
    distance_of,
    language_of,
    name_of,
    say,
    sector_word,
)

INTENT_OVERHEAD: Final = "AdsbStationOverhead"
INTENT_COUNT: Final = "AdsbStationCount"
INTENT_CLOSEST: Final = "AdsbStationClosest"
INTENT_TRAFFIC: Final = "AdsbStationTraffic"
INTENT_ROUTE: Final = "AdsbStationRoute"

# Military is a marker; the others are broadcast emitter categories.
TRAFFIC_KINDS: Final[dict[str, str | None]] = {
    "military": None,
    "helicopter": "A7",
    "drone": "B6",
}

# How many matching aircraft to name before counting the rest. One sentence
# is an answer; five is a list nobody can follow by ear.
_SPOKEN_MATCHES: Final = 1


class _AdsbStationIntent(intent.IntentHandler):
    """Shared ground: find the station, pick the language, say one thing.

    With two receivers the first by name answers; the services can pick one.
    """

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Answer, in the language the question was asked in."""
        language = language_of(intent_obj.language)
        response = intent_obj.create_response()

        stations = receivers(intent_obj.hass)
        if not stations:
            response.async_set_speech(say(language, "no_station"))
            return response

        coordinator, aircraft = stations[0]
        response.async_set_speech(
            self.answer(
                coordinator,
                aircraft,
                language,
                intent_obj.hass.config.units,
                intent_obj.slots,
            )
        )
        return response

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Return the sentence to speak."""
        raise NotImplementedError

    def placed(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        summary: AircraftSummary,
        language: str,
        units: UnitSystem,
    ) -> dict[str, str]:
        """Return how far away and which way an aircraft is, in words."""
        sector = sector_word(
            sector_from(coordinator.origin, summary.position), language
        )
        return {
            "aircraft": name_of(summary, language),
            "distance": (
                ""
                if summary.distance is None
                else distance_of(summary.distance, language, units)
            ),
            "sector": sector or "",
            "altitude": altitude_of(summary, language, units),
        }


class OverheadIntent(_AdsbStationIntent):
    """What is over the house right now."""

    intent_type = INTENT_OVERHEAD
    description = "Says which aircraft is overhead right now, if any"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the aircraft that is overhead, or with silence."""
        if (passage := coordinator.overhead) is None:
            return say(language, "nothing_overhead")
        spoken = self.placed(coordinator, passage.current, language, units)
        return say(
            language,
            "overhead",
            aircraft=spoken["aircraft"],
            altitude=spoken["altitude"],
        )


class CountIntent(_AdsbStationIntent):
    """How much is up there."""

    intent_type = INTENT_COUNT
    description = "Says how many aircraft are nearby and how many the station hears"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Answer with both figures, because either alone reads as the whole sky."""
        heard = counted(aircraft.total, language)
        if not aircraft.nearby:
            return say(language, "nothing_nearby", heard=heard)
        return say(
            language,
            "count",
            nearby=counted(len(aircraft.nearby), language),
            heard=aircraft.total,
        )


class ClosestIntent(_AdsbStationIntent):
    """What is nearest, whether or not it is overhead."""

    intent_type = INTENT_CLOSEST
    description = "Says which aircraft is closest, how far away and in which direction"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the nearest aircraft that has a position."""
        if (closest := aircraft.closest) is None:
            return say(language, "nothing_overhead")
        spoken = self.placed(coordinator, closest, language, units)
        return say(language, "closest", **spoken)


class TrafficIntent(_AdsbStationIntent):
    """Military traffic, helicopters or drones."""

    intent_type = INTENT_TRAFFIC
    description = "Says whether military traffic, helicopters or drones are in range"

    @property
    def slot_schema(self) -> dict[Any, Any]:
        """Return what the sentence has to name."""
        return {"kind": cv.string}

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the nearest one of its kind, and how many others."""
        kind = str(slots.get("kind", {}).get("value", "")).strip().lower()
        if kind not in TRAFFIC_KINDS:
            # A slot is outside text; do not fall through to "military".
            return say(language, "nothing_matching")
        category = TRAFFIC_KINDS[kind]

        matching = [
            summary
            for summary in aircraft.heard
            if (summary.military if category is None else summary.category == category)
        ]
        if not matching:
            return say(language, "nothing_matching")

        # Nearest first, and the ones we cannot place last: an aircraft with
        # no position can be named but not pointed at.
        matching.sort(key=lambda item: (item.distance is None, item.distance or 0))
        spoken = self.placed(coordinator, matching[0], language, units)
        first = say(language, "matching", **spoken)
        if len(matching) <= _SPOKEN_MATCHES:
            return first
        return say(
            language, "and_more", first=first, count=len(matching) - _SPOKEN_MATCHES
        )


class RouteIntent(_AdsbStationIntent):
    """Where the aircraft overhead came from and is going."""

    intent_type = INTENT_ROUTE
    description = "Says where the aircraft overhead is flying from and to"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: UnitSystem,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the route, or with why there is not one."""
        if (passage := coordinator.overhead) is None:
            return say(language, "nothing_overhead")

        summary = passage.current
        spoken = name_of(summary, language)
        if coordinator.route_lookup is None:
            # Worth saying out loud rather than answering "I don't know": the
            # setting is off by default, and nothing on the dashboard says so.
            return say(language, "routes_off")
        if (route := summary.route) is None:
            return say(language, "no_route", aircraft=spoken)

        origin = _place(route.origin)
        destination = _place(route.destination)
        if origin is None or destination is None:
            return say(language, "no_route", aircraft=spoken)
        return say(
            language, "route", aircraft=spoken, origin=origin, destination=destination
        )


def _place(airport: Any) -> str | None:
    """Return what to call one end of a route out loud: the city, not the code."""
    if airport is None:
        return None
    return airport.location or airport.name or airport.code


# The names `adsb_station.speak` takes, for answers without the sentence files.
QUESTIONS: Final[dict[str, _AdsbStationIntent]] = {
    "overhead": OverheadIntent(),
    "count": CountIntent(),
    "closest": ClosestIntent(),
    "traffic": TrafficIntent(),
    "route": RouteIntent(),
}


def answer_question(
    question: str,
    coordinator: AdsbStationDataUpdateCoordinator,
    aircraft: AircraftStats,
    language: str,
    units: UnitSystem,
    kind: str | None = None,
) -> str:
    """Return the spoken answer to one question, without an intent around it."""
    slots = {} if kind is None else {"kind": {"value": kind}}
    return QUESTIONS[question].answer(coordinator, aircraft, language, units, slots)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Register what can be asked out loud; the intent component calls this."""
    for handler in QUESTIONS.values():
        intent.async_register(hass, handler)
