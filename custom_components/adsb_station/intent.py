"""Six spoken questions for Assist, answered from the last poll.

The sentences ship as files and must be copied into the configuration
directory, by hand or with `adsb_station.install_sentences`.
"""

from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util import dt as dt_util

from .const import CLIMB_RATE_SHOWN, PASSAGE_GAP
from .coordinator import (
    AdsbStationDataUpdateCoordinator,
    AircraftStats,
    AircraftSummary,
    receivers,
    sector_from,
)
from .speech import (
    ago_of,
    altitude_of,
    counted,
    distance_of,
    language_of,
    name_of,
    say,
    sector_word,
    speed_of,
)
from .units import Units

INTENT_OVERHEAD: Final = "AdsbStationOverhead"
INTENT_COUNT: Final = "AdsbStationCount"
INTENT_CLOSEST: Final = "AdsbStationClosest"
INTENT_TRAFFIC: Final = "AdsbStationTraffic"
INTENT_ROUTE: Final = "AdsbStationRoute"
INTENT_LAST_PASSAGE: Final = "AdsbStationLastPassage"
INTENT_HIGHEST: Final = "AdsbStationHighest"
INTENT_FASTEST: Final = "AdsbStationFastest"
INTENT_FURTHEST: Final = "AdsbStationFurthest"
INTENT_EMERGENCY: Final = "AdsbStationEmergency"

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
                coordinator.units,
                intent_obj.slots,
            )
        )
        return response

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: Units,
        slots: dict[str, Any],
    ) -> str:
        """Return the sentence to speak."""
        raise NotImplementedError

    def placed(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        summary: AircraftSummary,
        language: str,
        units: Units,
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
        units: Units,
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
        units: Units,
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
        units: Units,
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
        units: Units,
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
        units: Units,
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


class LastPassageIntent(_AdsbStationIntent):
    """What just came over, asked once it has gone."""

    intent_type = INTENT_LAST_PASSAGE
    description = "Says which aircraft came over last, and how long ago"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: Units,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the last aircraft past its closest approach.

        One still on its way in has not come over yet: that is what is
        overhead now, in the present tense.
        """
        now = dt_util.utcnow()
        if (found := coordinator.last_passed(now)) is None:
            if coordinator.overhead is not None and coordinator.in_view(now):
                return QUESTIONS["overhead"].answer(
                    coordinator, aircraft, language, units, slots
                )
            return say(
                language,
                "nothing_came_over",
                minutes=round(PASSAGE_GAP.total_seconds() / 60),
            )

        passage, when = found
        return say(
            language,
            "came_over",
            aircraft=name_of(passage.closest, language),
            ago=ago_of((now - when).total_seconds(), language),
            altitude=altitude_of(passage.closest, language, units),
        )


def _where(spoken: dict[str, str], language: str) -> str:
    """Return ", 12 kilometres to the north", or nothing without a position."""
    if not spoken["distance"] or not spoken["sector"]:
        return ""
    return say(language, "where", distance=spoken["distance"], sector=spoken["sector"])


class _Superlative(_AdsbStationIntent):
    """The one aircraft that stands out by one figure the poll already has."""

    phrase: str

    def pick(self, aircraft: AircraftStats) -> AircraftSummary | None:
        """Return the aircraft to speak of."""
        raise NotImplementedError

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: Units,
        slots: dict[str, Any],
    ) -> str:
        """Answer with that aircraft, or that nothing is heard."""
        if (found := self.pick(aircraft)) is None:
            return say(language, "nothing_overhead")
        spoken = self.placed(coordinator, found, language, units)
        return say(
            language,
            self.phrase,
            aircraft=spoken["aircraft"],
            altitude=spoken["altitude"],
            speed="" if found.speed is None else speed_of(found.speed, language, units),
            where=_where(spoken, language),
        )


class HighestIntent(_Superlative):
    """What flies highest."""

    intent_type = INTENT_HIGHEST
    description = "Says which aircraft flies highest, and where"
    phrase = "highest"

    def pick(self, aircraft: AircraftStats) -> AircraftSummary | None:
        """Return the highest."""
        return aircraft.highest


class FastestIntent(_Superlative):
    """What flies fastest."""

    intent_type = INTENT_FASTEST
    description = "Says which aircraft flies fastest, and where"
    phrase = "fastest"

    def pick(self, aircraft: AircraftStats) -> AircraftSummary | None:
        """Return the fastest."""
        return aircraft.fastest


class FurthestIntent(_Superlative):
    """What is furthest away: how far the antenna reaches right now."""

    intent_type = INTENT_FURTHEST
    description = (
        "Says which aircraft is furthest away, which is how far the station hears"
    )
    phrase = "furthest"

    def pick(self, aircraft: AircraftStats) -> AircraftSummary | None:
        """Return the furthest."""
        return aircraft.furthest


class EmergencyIntent(_AdsbStationIntent):
    """Whether anything up there reports an emergency."""

    intent_type = INTENT_EMERGENCY
    description = "Says whether any aircraft reports an emergency, and which"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: Units,
        slots: dict[str, Any],
    ) -> str:
        """Answer with the nearest in distress, and how many others."""
        if not aircraft.emergencies:
            return say(language, "no_emergency")
        nearest = sorted(
            aircraft.emergencies,
            key=lambda item: (
                item.summary.distance is None,
                item.summary.distance or 0,
            ),
        )
        first = nearest[0]
        spoken = self.placed(coordinator, first.summary, language, units)
        sentence = say(
            language,
            "emergency",
            aircraft=spoken["aircraft"],
            reason=say(language, f"reason_{first.reason}"),
            altitude=spoken["altitude"],
            where=_where(spoken, language),
        )
        if len(nearest) <= _SPOKEN_MATCHES:
            return sentence
        return say(
            language, "and_more", first=sentence, count=len(nearest) - _SPOKEN_MATCHES
        )


class AircraftQuestion(_AdsbStationIntent):
    """One aircraft, named by hex code, callsign or registration."""

    intent_type = "AdsbStationAircraft"
    description = "Says what one named aircraft is, where it is and where it is going"

    def answer(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        aircraft: AircraftStats,
        language: str,
        units: Units,
        slots: dict[str, Any],
    ) -> str:
        """Answer with what it is, where, how high, and its route if known."""
        wanted = str(slots.get("aircraft", {}).get("value", "")).strip().upper()
        # The nearby ones last, so they win: only they carry a route.
        known = {summary.hex: summary for summary in aircraft.heard}
        known.update({summary.hex: summary for summary in aircraft.nearby})
        found = next(
            (
                summary
                for summary in known.values()
                if wanted
                and wanted
                in (
                    summary.hex.upper(),
                    (summary.flight or "").strip().upper(),
                    (summary.registration or "").strip().upper(),
                )
            ),
            None,
        )
        if found is None:
            return say(language, "not_heard", aircraft=wanted or "?")

        spoken = self.placed(coordinator, found, language, units)
        rate = found.vertical_rate
        if found.altitude is not None and rate is not None and not found.on_ground:
            if rate >= CLIMB_RATE_SHOWN:
                spoken["altitude"] = say(
                    language, "climbing", altitude=spoken["altitude"]
                )
            elif rate <= -CLIMB_RATE_SHOWN:
                spoken["altitude"] = say(
                    language, "descending", altitude=spoken["altitude"]
                )

        what = found.description or found.aircraft_type
        if not spoken["distance"] or not spoken["sector"]:
            sentence = say(
                language,
                "unplaced",
                aircraft=spoken["aircraft"],
                altitude=spoken["altitude"],
            )
        elif what:
            sentence = say(language, "typed", type=what, **spoken)
        else:
            sentence = say(language, "closest", **spoken)

        route = found.route
        origin = _place(route.origin) if route is not None else None
        destination = _place(route.destination) if route is not None else None
        if origin and destination:
            sentence += " " + say(
                language, "flying_from", origin=origin, destination=destination
            )
        return sentence


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
    "last_passage": LastPassageIntent(),
    "highest": HighestIntent(),
    "fastest": FastestIntent(),
    "furthest": FurthestIntent(),
    "emergency": EmergencyIntent(),
}


# Asked through `adsb_station.speak` only: a callsign is no slot Assist hears
# reliably, so it has no sentences.
SPEAK_ONLY: Final[dict[str, _AdsbStationIntent]] = {"aircraft": AircraftQuestion()}


def answer_question(
    question: str,
    coordinator: AdsbStationDataUpdateCoordinator,
    aircraft: AircraftStats,
    language: str,
    units: Units,
    kind: str | None = None,
    named: str | None = None,
) -> str:
    """Return the spoken answer to one question, without an intent around it."""
    slots: dict[str, Any] = {}
    if kind is not None:
        slots["kind"] = {"value": kind}
    if named is not None:
        slots["aircraft"] = {"value": named}
    handler = QUESTIONS.get(question) or SPEAK_ONLY[question]
    return handler.answer(coordinator, aircraft, language, units, slots)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Register what can be asked out loud; the intent component calls this."""
    for handler in QUESTIONS.values():
        intent.async_register(hass, handler)
