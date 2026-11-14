"""Edit the watchlist option from actions and text entities.

The same check as the options form applies, and the new list is taken over
without a reload (see `async_set_watchlist`).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_WATCHLIST, DOMAIN
from .reference import kind_of, line_key


def watched_lines(entry: ConfigEntry) -> list[str]:
    """Return the lines on an entry's watchlist, as they were written."""
    text = str(entry.options.get(CONF_WATCHLIST) or "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _save(hass: HomeAssistant, entry: ConfigEntry, lines: list[str]) -> None:
    """Store the list, leaving the option out once empty, as the form does."""
    options = {
        key: value for key, value in entry.options.items() if key != CONF_WATCHLIST
    }
    if lines:
        options[CONF_WATCHLIST] = "\n".join(lines)
    hass.config_entries.async_update_entry(entry, options=options)


def add_line(
    hass: HomeAssistant, entry: ConfigEntry, line: str, models: dict[str, str]
) -> bool:
    """Put a line on the watchlist; return False if it was there in any spelling."""
    line = line.strip()
    if kind_of(line, models) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unreadable_watchlist_line",
            translation_placeholders={"line": line},
        )
    lines = watched_lines(entry)
    if any(line_key(existing) == line_key(line) for existing in lines):
        return False
    _save(hass, entry, [*lines, line])
    return True


def remove_line(hass: HomeAssistant, entry: ConfigEntry, line: str) -> None:
    """Take a line off the watchlist, however it is written.

    A line not on the list is an error, as it is most likely a typo.
    """
    lines = watched_lines(entry)
    kept = [existing for existing in lines if line_key(existing) != line_key(line)]
    if len(kept) == len(lines):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_on_watchlist",
            translation_placeholders={"line": line.strip(), "station": entry.title},
        )
    _save(hass, entry, kept)
