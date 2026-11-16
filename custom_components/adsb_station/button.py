"""Button platform for the ADS-B Station integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdsbStationConfigEntry, AdsbStationDataUpdateCoordinator
from .entity import AdsbStationEntity

# Updates are centralized through the coordinator
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator = entry.runtime_data
    if coordinator.client.aircraft_url:
        async_add_entities([AdsbStationResetRangeButton(coordinator)])


class AdsbStationResetRangeButton(AdsbStationEntity, ButtonEntity):
    """Clears every record, for after a change to the antenna.

    Unique ID from when it cleared the sector ranges only.
    """

    _attr_translation_key = "reset_range"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "reset_range")

    async def async_press(self) -> None:
        """Forget every record: per sector, and the furthest, highest and fastest."""
        coordinator = self.coordinator
        for sensor in (*coordinator.sector_sensors, *coordinator.record_sensors):
            sensor.reset()
