"""Diagnostics support for the ADS-B Station integration."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_AIRCRAFT_URL, CONF_STATS_URL, CONF_WATCHLIST
from .coordinator import (
    AdsbStationConfigEntry,
    AdsbStationDataUpdateCoordinator,
    AircraftStats,
)

# Feed alias, site_url and URLs identify the user; fr24key is a credential.
TO_REDACT = {
    CONF_HOST,
    CONF_AIRCRAFT_URL,
    CONF_STATS_URL,
    "feed_alias",
    "fr24key",
    "site_url",
    "local_ips",
    "feed_legacy_id",
}


# A tenth of a degree is about 11 km: the region a station is in, not the
# house. Diagnostics end up pasted into public issues.
_DECIMALS = 1


# Where an aircraft is from the antenna. Its hex and the time give its
# position away on any public tracker, and from there the antenna's.
_GEOMETRY = {
    "distance",
    "bearing",
    "elevation",
    "closest_passing_distance",
    "seconds_to_closest",
}


def _coarse(value: Any) -> Any:
    """Leave out where every aircraft is, and where it is from the antenna."""
    if isinstance(value, dict):
        return {
            key: (item is not None if key == "position" else _coarse(item))
            for key, item in value.items()
            if key not in _GEOMETRY
        }
    if isinstance(value, (list, tuple)):
        return [_coarse(item) for item in value]
    return value


def _rounded(position: Any) -> Any:
    """Return a latitude and longitude to the region, or what came if not one."""
    if isinstance(position, (list, tuple)) and len(position) == 2:
        return [round(float(part), _DECIMALS) for part in position]
    return position


def _aircraft(stats: AircraftStats) -> dict[str, Any]:
    """Describe one poll, counting the heard aircraft rather than listing them.

    A watchlist match says which kind of line matched and on what, not the
    line or the aircraft: those say who is being watched for.
    """
    payload = asdict(stats)
    payload["heard"] = len(stats.heard)
    payload["watched"] = [
        {"kind": match.entry.kind, "matched_on": match.matched_on}
        for match in stats.watched
    ]
    return _coarse(payload)


def _watchlist(coordinator: AdsbStationDataUpdateCoordinator) -> dict[str, int]:
    """Return how many lines of each kind the watchlist holds, not the lines."""
    return dict(Counter(entry.kind for entry in coordinator.watchlist))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": {
            **{
                key: value
                for key, value in entry.options.items()
                if key != CONF_WATCHLIST
            },
            CONF_WATCHLIST: _watchlist(coordinator),
        },
        "has_feeder": coordinator.client.has_feeder,
        "feeder_type": coordinator.feeder_type,
        "receiver_version": coordinator.receiver_version,
        "feeder": (
            None if data.feeder is None else async_redact_data(data.feeder, TO_REDACT)
        ),
        "aircraft": None if data.aircraft is None else _aircraft(data.aircraft),
        "reception": None if data.stats is None else asdict(data.stats),
        "range_measured_from": _rounded(coordinator.origin),
        "range_measured_from_source": coordinator.origin_source,
    }
