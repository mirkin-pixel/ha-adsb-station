"""Text platform for the ADS-B Station integration.

Two boxes on the station's device, one to put a line on the watchlist and one
to take it off again, so the list can be kept from a dashboard. They hold
nothing themselves: what was typed goes straight into the options, and the box
stays empty.
"""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdsbStationConfigEntry, AdsbStationDataUpdateCoordinator
from .entity import AdsbStationEntity
from .watchlist import add_line, remove_line

# Updates are centralized through the coordinator
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text platform, for a station that hears aircraft."""
    coordinator = entry.runtime_data
    if coordinator.client.aircraft_url:
        async_add_entities(
            [
                AdsbStationWatchText(coordinator),
                AdsbStationUnwatchText(coordinator),
            ]
        )


class AdsbStationWatchlistText(AdsbStationEntity, TextEntity):
    """A box to type one watchlist line into."""

    _attr_entity_category = EntityCategory.CONFIG
    # The longest line the watchlist takes is a registration or a callsign.
    _attr_native_max = 16
    _attr_native_value = ""


class AdsbStationWatchText(AdsbStationWatchlistText):
    """Puts what is typed on the watchlist."""

    _attr_translation_key = "watch"

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the box."""
        super().__init__(coordinator, "watch")

    async def async_set_value(self, value: str) -> None:
        """Put the line on the watchlist."""
        add_line(
            self.hass,
            self.coordinator.config_entry,
            value,
            self.coordinator.reference.models,
        )


class AdsbStationUnwatchText(AdsbStationWatchlistText):
    """Takes what is typed off the watchlist."""

    _attr_translation_key = "unwatch"

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the box."""
        super().__init__(coordinator, "unwatch")

    async def async_set_value(self, value: str) -> None:
        """Take the line off the watchlist."""
        remove_line(self.hass, self.coordinator.config_entry, value)
