"""Changing the watchlist without opening the options.

The list lives in the options of the entry that carries the receiver, one line
to an aircraft, and the options form is where it was always edited. That is a
long way round for "tell me when PH-BXA is up", so the actions and the two text
entities edit the same option directly. They go through the same check the
form does, so a line the form would refuse is refused here too, and saving the
options reloads the entry exactly as saving the form does.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_WATCHLIST, DOMAIN
from .reference import kind_of, normalise


def watched_lines(entry: ConfigEntry) -> list[str]:
    """Return the lines on an entry's watchlist, as they were written."""
    text = str(entry.options.get(CONF_WATCHLIST) or "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _save(hass: HomeAssistant, entry: ConfigEntry, lines: list[str]) -> None:
    """Store the list, leaving the option out altogether once it is empty.

    Absent rather than blank, as the options form leaves it, because an empty
    list is what decides that there is no watchlist sensor at all.
    """
    options = {
        key: value for key, value in entry.options.items() if key != CONF_WATCHLIST
    }
    if lines:
        options[CONF_WATCHLIST] = "\n".join(lines)
    hass.config_entries.async_update_entry(entry, options=options)


def add_line(
    hass: HomeAssistant, entry: ConfigEntry, line: str, models: dict[str, str]
) -> bool:
    """Put a line on the watchlist, and return whether it was not there yet.

    A line already on the list, written however it was written, is left alone:
    adding PHBXA beside PH-BXA would only announce the same aircraft twice.
    """
    line = line.strip()
    if kind_of(line, models) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unreadable_watchlist_line",
            translation_placeholders={"line": line},
        )
    lines = watched_lines(entry)
    if any(normalise(existing) == normalise(line) for existing in lines):
        return False
    _save(hass, entry, [*lines, line])
    return True


def remove_line(hass: HomeAssistant, entry: ConfigEntry, line: str) -> None:
    """Take a line off the watchlist, however it is written.

    A line that is not on the list is an error rather than nothing to do,
    because the likeliest reason is a typo, and saying nothing would leave
    the aircraft on the list while it looks as though it came off.
    """
    lines = watched_lines(entry)
    kept = [existing for existing in lines if normalise(existing) != normalise(line)]
    if len(kept) == len(lines):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_on_watchlist",
            translation_placeholders={"line": line.strip(), "station": entry.title},
        )
    _save(hass, entry, kept)
