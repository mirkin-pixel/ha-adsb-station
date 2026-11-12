"""The spoken answers, in English and Dutch.

Spoken text differs from entity text: callsigns, sectors and heights must be
written to be heard. English is the fallback for any phrase or language that
is missing.
"""

from __future__ import annotations

from typing import Final

from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM, UnitSystem

from .const import FEET_TO_METRES
from .coordinator import AircraftSummary
from .reference import designator_of

DEFAULT_LANGUAGE: Final = "en"

# Which way to look, in words rather than in the letters an entity uses.
SECTORS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "n": "north",
        "ne": "north-east",
        "e": "east",
        "se": "south-east",
        "s": "south",
        "sw": "south-west",
        "w": "west",
        "nw": "north-west",
    },
    "nl": {
        "n": "noorden",
        "ne": "noordoosten",
        "e": "oosten",
        "se": "zuidoosten",
        "s": "zuiden",
        "sw": "zuidwesten",
        "w": "westen",
        "nw": "noordwesten",
    },
}

PHRASES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "no_station": "I cannot reach your ADS-B station.",
        "nothing_overhead": "Nothing is overhead right now.",
        "overhead": "{aircraft} is overhead, {altitude}.",
        "nothing_nearby": "Nothing is nearby, and the station is hearing {heard}.",
        "count": "{nearby} nearby, and the station is hearing {heard} in all.",
        "closest": "{aircraft} is {distance} to the {sector}, {altitude}.",
        "nothing_matching": "I hear nothing like that.",
        "matching": "{aircraft}, {distance} to the {sector}.",
        "and_more": "{first} And {count} more.",
        "no_route": "I have no route for {aircraft}.",
        "route": "{aircraft} is flying from {origin} to {destination}.",
        "routes_off": (
            "Route lookups are switched off, so I only know what is up there, "
            "not where it is going."
        ),
        "came_over": "{aircraft} came over {ago}, {altitude}.",
        # Said of the station, not the sky: after a restart it has simply
        # not been listening that long.
        "nothing_came_over": (
            "I have heard nothing come over in the last {minutes} minutes."
        ),
        "just_now": "just now",
        "a_minute_ago": "a minute ago",
        "minutes_ago": "{count} minutes ago",
        "one_aircraft": "one aircraft",
        "n_aircraft": "{count} aircraft",
        "no_aircraft": "no aircraft",
        "flight_of": "{airline} {number}",
        "unknown_aircraft": "an aircraft",
        "metres": "{value} metres up",
        "feet": "{value} feet up",
        "kilometres": "{value} kilometres",
        "miles": "{value} miles",
        "no_altitude": "at a height it does not report",
    },
    "nl": {
        "no_station": "Ik kan je ADS-B-station niet bereiken.",
        "nothing_overhead": "Er hangt nu niets boven je.",
        "overhead": "{aircraft} vliegt over, {altitude}.",
        "nothing_nearby": "Er is niets dichtbij, en het station hoort {heard}.",
        "count": "{nearby} dichtbij, en het station hoort er {heard} in totaal.",
        "closest": "{aircraft} zit {distance} naar het {sector}, {altitude}.",
        "nothing_matching": "Ik hoor niets van dat soort.",
        "matching": "{aircraft}, {distance} naar het {sector}.",
        "and_more": "{first} En nog {count}.",
        "no_route": "Ik heb geen route voor {aircraft}.",
        "route": "{aircraft} vliegt van {origin} naar {destination}.",
        "routes_off": (
            "Het opzoeken van routes staat uit, dus ik weet alleen wat er "
            "hangt, niet waar het heen gaat."
        ),
        "came_over": "{aircraft} vloog {ago} over, {altitude}.",
        "nothing_came_over": (
            "Ik heb de afgelopen {minutes} minuten niets horen overvliegen."
        ),
        "just_now": "net",
        "a_minute_ago": "een minuut geleden",
        "minutes_ago": "{count} minuten geleden",
        "one_aircraft": "één vliegtuig",
        "n_aircraft": "{count} vliegtuigen",
        "no_aircraft": "geen vliegtuigen",
        "flight_of": "{airline} {number}",
        "unknown_aircraft": "een vliegtuig",
        "metres": "{value} meter hoog",
        "feet": "{value} voet hoog",
        "kilometres": "{value} kilometer",
        "miles": "{value} mijl",
        "no_altitude": "op een hoogte die hij niet meldt",
    },
}

# Letters are spaced so they are spelled, not read as a word.
_SPELL: Final = " "

# In Dutch "3,700" reads as three point seven.
_THOUSANDS: Final[dict[str, str]] = {"en": ",", "nl": "."}
# Both languages write a decimal point the other way round as well.
_DECIMAL: Final[dict[str, str]] = {"en": ".", "nl": ","}


def language_of(language: str | None) -> str:
    """Return which of our languages to answer in, by the part before the dash."""
    if language is None:
        return DEFAULT_LANGUAGE
    code = language.replace("_", "-").split("-", 1)[0].lower()
    return code if code in PHRASES else DEFAULT_LANGUAGE


def say(language: str, key: str, **values: object) -> str:
    """Return one phrase, filled in, in English where the language lacks it."""
    phrase = PHRASES[language].get(key) or PHRASES[DEFAULT_LANGUAGE][key]
    return phrase.format(**values)


def whole(value: float, language: str) -> str:
    """Return a whole number written the way the language writes it."""
    return f"{round(value):,}".replace(",", _THOUSANDS[language])


def rounded(value: float, language: str) -> str:
    """Return a number with one decimal, without a trailing nought."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", _DECIMAL[language])


def name_of(summary: AircraftSummary, language: str) -> str:
    """Return what to call this aircraft out loud.

    An airline flight by airline and number; anything else spelled out.
    """
    flight = None if summary.flight is None else summary.flight.strip().upper()
    if flight:
        designator = designator_of(flight)
        if designator is not None and summary.airline is not None:
            return say(
                language,
                "flight_of",
                airline=summary.airline,
                number=flight[len(designator) :].lstrip("0") or flight,
            )
        return _SPELL.join(flight)
    if summary.registration is not None:
        return _SPELL.join(summary.registration.upper().replace("-", ""))
    if summary.hex:
        return _SPELL.join(summary.hex.upper())
    return say(language, "unknown_aircraft")


def altitude_of(summary: AircraftSummary, language: str, units: UnitSystem) -> str:
    """Return how high an aircraft is, in whole units of the right kind."""
    if summary.altitude is None:
        return say(language, "no_altitude")
    if units is US_CUSTOMARY_SYSTEM:
        # To the nearest five hundred feet and hundred metres. Nobody asking
        # out loud wants to hear that something is at 30,175 feet.
        return say(
            language, "feet", value=whole(round(summary.altitude / 500) * 500, language)
        )
    metres = summary.altitude * FEET_TO_METRES
    return say(language, "metres", value=whole(round(metres / 100) * 100, language))


def distance_of(metres: float, language: str, units: UnitSystem) -> str:
    """Return how far away something is, rounded to something sayable."""
    if units is US_CUSTOMARY_SYSTEM:
        return say(language, "miles", value=rounded(metres / 1609.344, language))
    return say(language, "kilometres", value=rounded(metres / 1000, language))


def sector_word(sector: str | None, language: str) -> str | None:
    """Return a compass sector as the word for it."""
    if sector is None:
        return None
    words = SECTORS.get(language, {})
    return words.get(sector) or SECTORS[DEFAULT_LANGUAGE].get(sector)


def ago_of(seconds: float, language: str) -> str:
    """Return how long ago something was, in whole minutes once it is one."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return say(language, "just_now")
    if minutes == 1:
        return say(language, "a_minute_ago")
    return say(language, "minutes_ago", count=minutes)


def counted(count: int, language: str) -> str:
    """Return an aircraft count, with the words a count needs around it."""
    if count == 0:
        return say(language, "no_aircraft")
    if count == 1:
        return say(language, "one_aircraft")
    return say(language, "n_aircraft", count=count)
