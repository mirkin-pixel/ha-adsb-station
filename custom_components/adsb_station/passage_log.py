"""The passages of the last days, kept in a file of their own.

The board on Passages today starts over at midnight; this keeps them for as
many days as the station is set to. Written at most every quarter of an
hour, and when the station unloads or Home Assistant stops.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

STORAGE_VERSION: Final = 1
SAVE_DELAY: Final = 15 * 60
# However long they are kept, so a station by a busy airport stays a few MB.
MAX_KEPT: Final = 50_000


def storage_key(entry_id: str) -> str:
    """Return the file the station's passages are kept in."""
    return f"{DOMAIN}.{entry_id}.passages"


def _key(entry: dict[str, Any]) -> str:
    return f"{entry.get('at')}|{entry.get('hex')}"


def _plain(text: Any) -> str:
    """Return a callsign or registration as compared: capitals, no dashes."""
    return str(text or "").upper().replace("-", "").replace(" ", "")


class PassageLog:
    """The passages a station kept, oldest first."""

    def __init__(self, hass: HomeAssistant, entry_id: str, days: int) -> None:
        """Start empty; async_load fills it from the file."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry_id)
        )
        self.days = days
        # By start and hex, in the order they started.
        self._passages: dict[str, dict[str, Any]] = {}
        self._pruned: str | None = None

    async def async_load(self) -> None:
        """Read what earlier runs kept, or drop the file when none are kept."""
        if not self.days:
            await self._store.async_remove()
            return
        data = await self._store.async_load() or {}
        passages = data.get("passages")
        if isinstance(passages, list):
            for entry in passages:
                if isinstance(entry, dict) and isinstance(entry.get("at"), str):
                    self._passages[_key(entry)] = entry
        self._prune()

    async def async_save(self) -> None:
        """Write now, as the station unloads."""
        if self.days:
            await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Delete the file, with the station."""
        await self._store.async_remove()

    def _data(self) -> dict[str, Any]:
        return {"passages": list(self._passages.values())}

    def _prune(self) -> None:
        """Drop passages past the days kept, once a day, and any over the limit."""
        if (today := dt_util.now().date().isoformat()) != self._pruned:
            self._pruned = today
            cutoff = (dt_util.utcnow() - timedelta(days=self.days)).isoformat()
            for key in [
                key for key, entry in self._passages.items() if entry["at"] < cutoff
            ]:
                del self._passages[key]
        while len(self._passages) > MAX_KEPT:
            del self._passages[next(iter(self._passages))]

    def note(self, entries: Iterable[dict[str, Any]]) -> None:
        """Take in this poll's passages, new ones and those still under way."""
        if not self.days:
            return
        changed = False
        for entry in entries:
            key = _key(entry)
            if self._passages.get(key) != entry:
                self._passages[key] = entry
                changed = True
        if changed:
            self._prune()
            self._store.async_delay_save(self._data, SAVE_DELAY)

    def find(
        self,
        aircraft: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return the passages that match, most recent first.

        The aircraft by hex code, callsign or registration.
        """
        wanted = None if aircraft is None else _plain(aircraft)
        found = []
        for entry in reversed(self._passages.values()):
            at = dt_util.parse_datetime(entry["at"])
            if at is None:
                continue
            if start is not None and at < start:
                continue
            if end is not None and at > end:
                continue
            if wanted is not None and wanted not in {
                _plain(entry.get("hex")),
                _plain(entry.get("flight")),
                _plain(entry.get("registration")),
            }:
                continue
            found.append(entry)
        return found
