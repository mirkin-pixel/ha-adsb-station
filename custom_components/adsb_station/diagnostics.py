"""Diagnostics support for the ADS-B Station integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_AIRCRAFT_URL, CONF_STATS_URL
from .coordinator import AdsbStationConfigEntry, AircraftStats

# Feed alias, site_url and URLs identify the user; fr24key is a credential.
TO_REDACT = {
    CONF_HOST,
    CONF_AIRCRAFT_URL,
    CONF_STATS_URL,
    "feed_alias",
    "fr24key",
    "site_url",
    "local_ips",
}


def _aircraft(stats: AircraftStats) -> dict[str, Any]:
    """Describe one poll, counting the heard aircraft rather than listing them."""
    payload = asdict(stats)
    payload["heard"] = len(stats.heard)
    return payload


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "has_feeder": coordinator.client.has_feeder,
        "feeder_type": coordinator.feeder_type,
        "receiver_version": coordinator.receiver_version,
        "feeder": (
            None if data.feeder is None else async_redact_data(data.feeder, TO_REDACT)
        ),
        "aircraft": None if data.aircraft is None else _aircraft(data.aircraft),
        "reception": None if data.stats is None else asdict(data.stats),
        "range_measured_from": coordinator.origin,
        "range_measured_from_source": coordinator.origin_source,
    }
