"""The ADS-B Station integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdsbStationClient
from .const import CONF_AIRCRAFT_URL, CONF_STATS_URL
from .coordinator import AdsbStationConfigEntry, AdsbStationDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AdsbStationConfigEntry) -> bool:
    """Set up an ADS-B station from a config entry."""
    client = AdsbStationClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        # A station without fr24feed has no status page to read.
        entry.data.get(CONF_PORT),
        entry.data.get(CONF_AIRCRAFT_URL),
        entry.data.get(CONF_STATS_URL),
    )
    coordinator = AdsbStationDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> None:
    """Reload the entry after the options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
