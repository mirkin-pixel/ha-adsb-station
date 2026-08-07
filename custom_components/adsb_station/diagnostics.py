"""Diagnostics support for the ADS-B Station integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_AIRCRAFT_URL, CONF_STATS_URL
from .coordinator import AdsbStationConfigEntry

# The feed alias identifies the user's public Flightradar24 feed, and the URLs
# carry the address of their receiver.
TO_REDACT = {CONF_HOST, CONF_AIRCRAFT_URL, CONF_STATS_URL, "feed_alias"}


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
        "receiver_version": coordinator.receiver_version,
        "monitor": (
            None if data.monitor is None else async_redact_data(data.monitor, TO_REDACT)
        ),
        "aircraft": None if data.aircraft is None else asdict(data.aircraft),
        "reception": None if data.stats is None else asdict(data.stats),
        "range_measured_from": coordinator.origin,
    }
