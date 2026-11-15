"""An aircraft database to download, for decoders without one of their own.

tar1090-db, Mictronics' data as tar1090 and readsb use it: fetched by each
Home Assistant itself at most once a week, kept on disk and looked up there,
so it costs no memory. Registration, type, description and flags only; the
owner column names private people and is left out.
"""

from __future__ import annotations

from datetime import timedelta
import gzip
import io
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Final

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATABASE_URL: Final = (
    "https://github.com/wiedehopf/tar1090-db/raw/refs/heads/csv/aircraft.csv.gz"
)
REFRESH: Final = timedelta(days=7)
# After a failed download, so a dead link is not asked every poll.
RETRY: Final = timedelta(days=1)
_TIMEOUT: Final = ClientTimeout(total=300)
# readsb's dbFlags bits, in the order of the flags column's characters.
_FLAG_BITS: Final = 4


@callback
def database_of(hass: HomeAssistant) -> AircraftDatabase:
    """Return the one database of this Home Assistant, shared by its stations."""
    key = f"{DOMAIN}_aircraft_database"
    if key not in hass.data:
        hass.data[key] = AircraftDatabase(hass)
    database: AircraftDatabase = hass.data[key]
    return database


def _flags(text: str) -> int:
    """Return the flags column, '1000' style, as readsb's dbFlags."""
    return sum(1 << bit for bit, char in enumerate(text[:_FLAG_BITS]) if char == "1")


def _rows(compressed: bytes) -> Any:
    """Yield hex, registration, type, flags and description per aircraft."""
    with gzip.open(io.BytesIO(compressed), "rt", encoding="utf-8") as lines:
        for line in lines:
            fields = line.rstrip("\n").split(";")
            if len(fields) < 5 or len(fields[0]) != 6:
                continue
            hex_code, registration, kind, flags, description = fields[:5]
            if registration or kind or "1" in flags:
                yield (hex_code.lower(), registration, kind, _flags(flags), description)


class AircraftDatabase:
    """The downloaded table, its refresh, and lookups in it."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the database."""
        self.hass = hass
        self.path = Path(hass.config.path(".storage", f"{DOMAIN}.aircraft.db"))
        self._busy = False
        self._tried: float | None = None
        # Until when the file on disk is known to be fresh enough.
        self._fresh_until = 0.0

    def _age(self) -> float | None:
        """Return the file's age in seconds, or None without one."""
        try:
            return time.time() - self.path.stat().st_mtime
        except OSError:
            return None

    @callback
    def async_refresh_if_due(self) -> None:
        """Start a download in the background when the file is old or missing."""
        now = time.time()
        if (
            self._busy
            or now < self._fresh_until
            or (self._tried is not None and now - self._tried < RETRY.total_seconds())
        ):
            return
        self._busy = True
        self.hass.async_create_background_task(
            self._async_refresh(), f"{DOMAIN} database"
        )

    async def _async_refresh(self) -> None:
        """Download the table and build the file, when it is due."""
        try:
            age = await self.hass.async_add_executor_job(self._age)
            if age is not None and age < REFRESH.total_seconds():
                self._fresh_until = time.time() + REFRESH.total_seconds() - age
                return
            self._tried = time.time()
            session = async_get_clientsession(self.hass)
            async with session.get(DATABASE_URL, timeout=_TIMEOUT) as response:
                response.raise_for_status()
                compressed = await response.read()
            count = await self.hass.async_add_executor_job(self._build, compressed)
            self._fresh_until = time.time() + REFRESH.total_seconds()
            self._tried = None
            _LOGGER.info("Aircraft database updated: %s aircraft", count)
        except (ClientError, TimeoutError, OSError, sqlite3.Error, EOFError) as err:
            # The last good file, if any, stays in use.
            _LOGGER.warning("Could not update the aircraft database: %s", err)
        finally:
            self._busy = False

    def _build(self, compressed: bytes) -> int:
        """Write the table to a new file and put it in place of the old one."""
        building = self.path.with_suffix(".building")
        building.parent.mkdir(parents=True, exist_ok=True)
        building.unlink(missing_ok=True)
        with sqlite3.connect(building) as connection:
            connection.execute(
                "CREATE TABLE aircraft (hex TEXT PRIMARY KEY, r TEXT, t TEXT,"
                " flags INTEGER, d TEXT) WITHOUT ROWID"
            )
            connection.executemany(
                "INSERT OR REPLACE INTO aircraft VALUES (?, ?, ?, ?, ?)",
                _rows(compressed),
            )
            count = connection.execute("SELECT COUNT(*) FROM aircraft").fetchone()[0]
        connection.close()
        building.replace(self.path)
        return int(count)

    def lookup(self, hexes: list[str]) -> dict[str, dict[str, Any]]:
        """Return what the table says of each aircraft, as aircraft.json keys."""
        if not hexes or not self.path.exists():
            return {}
        found: dict[str, dict[str, Any]] = {}
        uri = f"{self.path.as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            marks = ",".join("?" * len(hexes))
            for hex_code, registration, kind, flags, description in connection.execute(
                f"SELECT hex, r, t, flags, d FROM aircraft WHERE hex IN ({marks})",  # noqa: S608
                hexes,
            ):
                row = {"r": registration, "t": kind, "desc": description}
                found[hex_code] = {key: value for key, value in row.items() if value}
                found[hex_code]["dbFlags"] = flags
        connection.close()
        return found

    def remove(self) -> None:
        """Delete the file, when the last station stops using it."""
        self.path.unlink(missing_ok=True)
        self.path.with_suffix(".building").unlink(missing_ok=True)
