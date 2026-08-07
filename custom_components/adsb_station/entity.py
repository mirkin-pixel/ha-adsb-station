"""Base entity for the ADS-B Station integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import web_root
from .const import (
    DEFAULT_FEEDER_NAME,
    DEFAULT_STATION_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL_FEEDER,
    MODEL_RECEIVER,
)
from .coordinator import AdsbStationDataUpdateCoordinator, AircraftStats, ReceiverStats


def _text(value: Any) -> str | None:
    """Return a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _device_info(
    coordinator: AdsbStationDataUpdateCoordinator, device_id: str
) -> DeviceInfo:
    """Describe the station this entity belongs to.

    With fr24feed the feeder identifies the device, down to the alias it feeds
    under. Without it there is only the decoder, which is not a Flightradar24
    product and gets no manufacturer.
    """
    client = coordinator.client
    if not client.has_feeder:
        aircraft_url = client.aircraft_url
        return DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            model=MODEL_RECEIVER,
            name=DEFAULT_STATION_NAME,
            sw_version=coordinator.receiver_version,
            configuration_url=None if aircraft_url is None else web_root(aircraft_url),
        )

    monitor = coordinator.data.monitor or {}
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        manufacturer=MANUFACTURER,
        model=MODEL_FEEDER,
        name=_text(monitor.get("feed_alias")) or DEFAULT_FEEDER_NAME,
        sw_version=_text(monitor.get("build_version")),
        hw_version=_text(monitor.get("build_arch")),
        configuration_url=f"http://{client.host}:{client.port}/",
    )


class AdsbStationEntity(CoordinatorEntity[AdsbStationDataUpdateCoordinator]):
    """Base entity for an ADS-B station."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = _device_info(coordinator, device_id)

    @property
    def monitor(self) -> dict[str, Any]:
        """Return the last monitor.json payload.

        Only entities that exist alongside a feeder read this, so an empty
        payload means the feeder has not answered yet rather than that there
        is none.
        """
        return self.coordinator.data.monitor or {}


class AdsbStationAircraftEntity(AdsbStationEntity):
    """Base entity for values that come from aircraft.json."""

    @property
    def aircraft(self) -> AircraftStats | None:
        """Return the last derived aircraft figures."""
        return self.coordinator.data.aircraft

    @property
    def available(self) -> bool:
        """Return True only while the receiver is answering."""
        return super().available and self.aircraft is not None


class AdsbStationReceptionEntity(AdsbStationEntity):
    """Base entity for values that come from stats.json."""

    @property
    def reception(self) -> ReceiverStats | None:
        """Return the last derived reception statistics."""
        return self.coordinator.data.stats

    @property
    def available(self) -> bool:
        """Return True only while the receiver is answering."""
        return super().available and self.reception is not None
