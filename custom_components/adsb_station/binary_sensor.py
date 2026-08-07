"""Binary sensor platform for the ADS-B Station integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AdsbStationConfigEntry, AdsbStationDataUpdateCoordinator
from .entity import AdsbStationAircraftEntity, AdsbStationEntity

_LOGGER = logging.getLogger(__name__)

# Updates are centralized through the coordinator
PARALLEL_UPDATES = 0

TRUE_VALUES = frozenset({"1", "true", "yes", "on", "connected"})
FALSE_VALUES = frozenset({"0", "false", "no", "off", "disconnected"})


def _as_bool(value: Any) -> bool | None:
    """Parse a flag that monitor.json reports as bool, number or string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_VALUES:
            return True
        if text in FALSE_VALUES:
            return False
    if value is not None:
        _LOGGER.debug("Could not parse %r as a boolean", value)
    return None


@dataclass(frozen=True, kw_only=True)
class AdsbStationBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a binary sensor that reads monitor.json."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[AdsbStationBinarySensorEntityDescription, ...] = (
    AdsbStationBinarySensorEntityDescription(
        key="receiver",
        translation_key="receiver",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda monitor: _as_bool(monitor.get("rx_connected")),
    ),
    AdsbStationBinarySensorEntityDescription(
        key="feed",
        translation_key="feed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda monitor: _as_bool(monitor.get("feed_status")),
    ),
    AdsbStationBinarySensorEntityDescription(
        key="mlat",
        translation_key="mlat",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda monitor: _as_bool(monitor.get("mlat_ok")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    if coordinator.client.has_feeder:
        entities.extend(
            AdsbStationBinarySensor(coordinator, description)
            for description in BINARY_SENSORS
        )
    if coordinator.client.aircraft_url:
        entities.append(AdsbStationEmergencyBinarySensor(coordinator))

    async_add_entities(entities)


class AdsbStationBinarySensor(AdsbStationEntity, BinarySensorEntity):
    """Binary sensor backed by monitor.json."""

    entity_description: AdsbStationBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        description: AdsbStationBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return True when the monitored part is connected."""
        return self.entity_description.value_fn(self.monitor)


class AdsbStationEmergencyBinarySensor(AdsbStationAircraftEntity, BinarySensorEntity):
    """On while an aircraft in range is squawking an emergency code."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "emergency"

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, "emergency")

    @property
    def is_on(self) -> bool | None:
        """Return True when at least one aircraft is in distress."""
        if (aircraft := self.aircraft) is None:
            return None
        return bool(aircraft.emergencies)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return which aircraft are in distress."""
        if (aircraft := self.aircraft) is None:
            return None
        return {
            "aircraft": [
                {
                    "hex": entry.hex,
                    "flight": entry.flight,
                    "squawk": entry.squawk,
                    "reason": entry.reason,
                }
                for entry in aircraft.emergencies
            ]
        }
