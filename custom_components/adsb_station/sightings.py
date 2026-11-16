"""Every aircraft a station has heard, kept in a file of its own.

Written at most every quarter of an hour, and when Home Assistant stops or
the station reloads: a Raspberry Pi's SD card should not take it every poll.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
import re
from typing import TYPE_CHECKING, Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import AircraftSummary

STORAGE_VERSION: Final = 1
SAVE_DELAY: Final = 15 * 60
# The first week nearly every aircraft is new; after that a new one is news.
SETTLING_DAYS: Final = 7
# One not heard for a year is forgotten, so the file does not grow for ever.
FORGOTTEN_AFTER_DAYS: Final = 365

# An ICAO address; readsb marks any other kind with a leading ~.
_ICAO: Final = re.compile(r"[0-9a-f]{6}")


def storage_key(entry_id: str) -> str:
    """Return the file the station's sightings are kept in."""
    return f"{DOMAIN}.{entry_id}.sightings"


@dataclass(frozen=True, kw_only=True)
class Sighting:
    """An aircraft heard for the first time."""

    hex: str
    first_of_type: bool
    first_of_airline: bool


class Sightings:
    """Which aircraft, types and airlines a station has heard, and when."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Start empty; async_load fills it from the file."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry_id)
        )
        # Days are date ordinals.
        self.since: int | None = None
        # hex → first day, last day, days heard.
        self.aircraft: dict[str, list[int]] = {}
        self.types: set[str] = set()
        self.airlines: set[str] = set()
        self._pruned: int | None = None

    async def async_load(self) -> None:
        """Read what earlier runs kept; a damaged entry is left out."""
        data = await self._store.async_load() or {}
        since = data.get("since")
        self.since = since if isinstance(since, int) else None
        aircraft = data.get("aircraft")
        if isinstance(aircraft, dict):
            self.aircraft = {
                hex_code: list(days)
                for hex_code, days in aircraft.items()
                if isinstance(days, list)
                and len(days) == 3
                and all(isinstance(day, int) for day in days)
            }
        self.types = {str(name) for name in data.get("types") or ()}
        self.airlines = {str(name) for name in data.get("airlines") or ()}

    async def async_save(self) -> None:
        """Write now, as the station unloads."""
        await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Delete the file, with the station."""
        await self._store.async_remove()

    def _data(self) -> dict[str, Any]:
        return {
            "since": self.since,
            "aircraft": self.aircraft,
            "types": sorted(self.types),
            "airlines": sorted(self.airlines),
        }

    def note(self, heard: Iterable[AircraftSummary], today: date) -> list[Sighting]:
        """Take in this poll's aircraft; return those heard for the first time.

        Nothing is returned in the first week, when nearly all are.
        """
        day = today.toordinal()
        if self.since is None:
            self.since = day
        settled = day - self.since >= SETTLING_DAYS
        changed = False
        new: list[Sighting] = []
        for summary in heard:
            hex_code = str(summary.hex).lower()
            if not _ICAO.fullmatch(hex_code):
                continue
            kind = summary.aircraft_type
            # Only a designator that names a known airline.
            airline = summary.airline_code if summary.airline else None
            known = self.aircraft.get(hex_code)
            if known is None:
                self.aircraft[hex_code] = [day, day, 1]
                changed = True
                if settled:
                    new.append(
                        Sighting(
                            hex=summary.hex,
                            first_of_type=kind is not None and kind not in self.types,
                            first_of_airline=airline is not None
                            and airline not in self.airlines,
                        )
                    )
            elif known[1] != day:
                known[1] = day
                known[2] += 1
                changed = True
            if kind is not None and kind not in self.types:
                self.types.add(kind)
                changed = True
            if airline is not None and airline not in self.airlines:
                self.airlines.add(airline)
                changed = True
        if self._pruned != day:
            self._pruned = day
            gone = [
                hex_code
                for hex_code, (_, last, _) in self.aircraft.items()
                if day - last > FORGOTTEN_AFTER_DAYS
            ]
            for hex_code in gone:
                del self.aircraft[hex_code]
            changed = changed or bool(gone)
        if changed:
            self._store.async_delay_save(self._data, SAVE_DELAY)
        return new

    def since_date(self) -> date | None:
        """Return the day the station started keeping them."""
        return None if self.since is None else date.fromordinal(self.since)
