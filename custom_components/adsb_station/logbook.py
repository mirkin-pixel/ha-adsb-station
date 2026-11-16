"""Readable lines in the activity log for the rare events.

Passages and approaches are left out: dozens a day would bury the rest.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    DEFAULT_STATION_NAME,
    DOMAIN,
    EVENT_AIRCRAFT_EMERGENCY,
    EVENT_RECORD_BROKEN,
    EVENT_WATCHLIST_LOST,
    EVENT_WATCHLIST_MATCH,
    RECORD_ALTITUDE,
    RECORD_RANGE,
    RECORD_SPEED,
)
from .speech import language_of, rounded

# The field of a record event its figure is in, and the field naming its unit.
RECORD_FIGURES = {
    RECORD_RANGE: ("distance", "distance_unit"),
    RECORD_ALTITUDE: ("altitude", "altitude_unit"),
    RECORD_SPEED: ("speed", "speed_unit"),
}

TEXT = {
    "en": {
        EVENT_RECORD_BROKEN: "heard {aircraft} set a {record} record",
        RECORD_RANGE: "range",
        RECORD_ALTITUDE: "altitude",
        RECORD_SPEED: "speed",
        EVENT_WATCHLIST_MATCH: "heard {aircraft} from the watchlist",
        EVENT_WATCHLIST_LOST: "lost {aircraft} from the watchlist",
        "after": " after {minutes} min",
        EVENT_AIRCRAFT_EMERGENCY: "heard {aircraft} report {reason}",
        "away": ", {distance} {unit} away",
        "nmi": "NM",
        "mi": "mi",
        "emergency": "an emergency",
        "hijack": "a hijack",
        "radio_failure": "a radio failure",
        "downed": "being downed",
    },
    "nl": {
        EVENT_RECORD_BROKEN: "hoorde {aircraft} een {record}record zetten",
        RECORD_RANGE: "bereik",
        RECORD_ALTITUDE: "hoogte",
        RECORD_SPEED: "snelheids",
        EVENT_WATCHLIST_MATCH: "hoorde {aircraft} van de watchlist",
        EVENT_WATCHLIST_LOST: "hoort {aircraft} van de watchlist niet meer",
        "after": " na {minutes} min",
        EVENT_AIRCRAFT_EMERGENCY: "hoorde {aircraft} een {reason} melden",
        "away": ", op {distance} {unit}",
        "nmi": "NM",
        "mi": "mijl",
        "emergency": "noodgeval",
        "hijack": "kaping",
        "radio_failure": "radiostoring",
        "downed": "neergestort toestel",
    },
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe the watchlist, emergency and record events."""

    @callback
    def describe(event: Event) -> dict[str, str]:
        data = event.data
        language = language_of(hass.config.language)
        text = TEXT[language]
        message = text[str(event.event_type)].format(
            aircraft=data.get("flight")
            or data.get("registration")
            or str(data.get("hex") or "?").upper(),
            reason=text.get(data.get("reason") or "", text["emergency"]),
            record=text.get(record := str(data.get("record")), record),
        )
        if event.event_type == EVENT_AIRCRAFT_EMERGENCY and data.get("squawk"):
            message += f", squawk {data['squawk']}"
        # A test event fired by hand may leave anything out.
        if event.event_type == EVENT_RECORD_BROKEN:
            figure, unit_field = RECORD_FIGURES.get(record, ("", ""))
            if isinstance(value := data.get(figure), int | float):
                unit = str(data.get(unit_field) or "")
                message += f": {rounded(value, language)} {text.get(unit, unit)}"
        elif event.event_type == EVENT_WATCHLIST_LOST:
            if isinstance(seconds := data.get("duration"), int | float):
                message += text["after"].format(minutes=round(seconds / 60))
        elif isinstance(distance := data.get("distance"), int | float):
            # In the units the event was fired in; before 1.4 always km.
            unit = str(data.get("distance_unit") or "km")
            message += text["away"].format(
                distance=rounded(distance, language), unit=text.get(unit, unit)
            )
        name = data.get("station") or DEFAULT_STATION_NAME
        return {LOGBOOK_ENTRY_NAME: name, LOGBOOK_ENTRY_MESSAGE: message}

    for event_type in (
        EVENT_WATCHLIST_MATCH,
        EVENT_WATCHLIST_LOST,
        EVENT_AIRCRAFT_EMERGENCY,
        EVENT_RECORD_BROKEN,
    ):
        async_describe_event(DOMAIN, event_type, describe)
