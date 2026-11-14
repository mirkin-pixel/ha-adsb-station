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

from .const import DOMAIN, EVENT_AIRCRAFT_EMERGENCY, EVENT_WATCHLIST_MATCH
from .speech import language_of, rounded

TEXT = {
    "en": {
        EVENT_WATCHLIST_MATCH: "heard {aircraft} from the watchlist",
        EVENT_AIRCRAFT_EMERGENCY: "heard {aircraft} report {reason}",
        "away": ", {distance} km away",
        "emergency": "an emergency",
        "hijack": "a hijack",
        "radio_failure": "a radio failure",
        "downed": "being downed",
    },
    "nl": {
        EVENT_WATCHLIST_MATCH: "hoorde {aircraft} van de watchlist",
        EVENT_AIRCRAFT_EMERGENCY: "hoorde {aircraft} een {reason} melden",
        "away": ", op {distance} km",
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
    """Describe the watchlist and emergency events."""

    @callback
    def describe(event: Event) -> dict[str, str]:
        data = event.data
        language = language_of(hass.config.language)
        text = TEXT[language]
        message = text[str(event.event_type)].format(
            aircraft=data["flight"] or data.get("registration") or data["hex"].upper(),
            reason=text.get(data.get("reason") or "", text["emergency"]),
        )
        if event.event_type == EVENT_AIRCRAFT_EMERGENCY and data.get("squawk"):
            message += f", squawk {data['squawk']}"
        if data["distance"] is not None:
            message += text["away"].format(distance=rounded(data["distance"], language))
        return {LOGBOOK_ENTRY_NAME: data["station"], LOGBOOK_ENTRY_MESSAGE: message}

    for event_type in (EVENT_WATCHLIST_MATCH, EVENT_AIRCRAFT_EMERGENCY):
        async_describe_event(DOMAIN, event_type, describe)
