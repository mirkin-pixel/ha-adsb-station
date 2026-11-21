"""What a station has already announced, kept over a restart.

Without it, every watched aircraft and every one in distress still in the air
is announced again after Home Assistant restarts or the station reloads.
Written when the station unloads or Home Assistant stops.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

STORAGE_VERSION: Final = 1
# Only at stop or unload in practice: every poll moves the write on again.
SAVE_DELAY: Final = 15 * 60


def storage_key(entry_id: str) -> str:
    """Return the file the station's announcements are kept in."""
    return f"{DOMAIN}.{entry_id}.announced"


def _when(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


class Announced:
    """The watched, distressed and approaching aircraft already announced."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Start empty; async_load fills it from the file."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry_id)
        )
        # Hex → first seen, last seen, and the event data to say it has gone.
        self.watched: dict[str, tuple[datetime, datetime, dict[str, Any]]] = {}
        # Hex → last seen in distress, and last warned of coming over.
        self.distressed: dict[str, datetime] = {}
        self.warned: dict[str, datetime] = {}

    async def async_load(self, remembered: timedelta) -> None:
        """Read what is recent enough to still be the same flight."""
        data = await self._store.async_load() or {}
        since = dt_util.utcnow() - remembered
        for hex_code, item in (data.get("watched") or {}).items():
            if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
                continue
            first, last = _when(item.get("first")), _when(item.get("last"))
            if first is not None and last is not None and last >= since:
                self.watched[hex_code] = (first, last, item["data"])
        for kept, stored in (
            (self.distressed, data.get("distressed")),
            (self.warned, data.get("warned")),
        ):
            for hex_code, value in (stored or {}).items():
                if (when := _when(value)) is not None and when >= since:
                    kept[hex_code] = when

    def note(self) -> None:
        """Have it written once Home Assistant stops, whatever happens first."""
        self._store.async_delay_save(self._data, SAVE_DELAY)

    async def async_save(self) -> None:
        """Write now, as the station unloads."""
        await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Delete the file, with the station."""
        await self._store.async_remove()

    def _data(self) -> dict[str, Any]:
        return {
            "watched": {
                hex_code: {
                    "first": first.isoformat(),
                    "last": last.isoformat(),
                    "data": data,
                }
                for hex_code, (first, last, data) in self.watched.items()
            },
            "distressed": {
                hex_code: when.isoformat() for hex_code, when in self.distressed.items()
            },
            "warned": {
                hex_code: when.isoformat() for hex_code, when in self.warned.items()
            },
        }
