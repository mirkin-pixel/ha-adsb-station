"""Sensor platform for the ADS-B Station integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_RECEIVER_FEATURES, FEATURE_GAIN
from .coordinator import (
    AdsbStationConfigEntry,
    AdsbStationDataUpdateCoordinator,
    AircraftStats,
    ReceiverStats,
)
from .entity import (
    AdsbStationAircraftEntity,
    AdsbStationEntity,
    AdsbStationReceptionEntity,
)

_LOGGER = logging.getLogger(__name__)

# Updates are centralized through the coordinator
PARALLEL_UPDATES = 0

UNIT_MESSAGES_PER_SECOND = "msg/s"
# dump1090 measures against the full scale of the dongle, not against a
# reference power, so these are not dBm and carry no device class.
UNIT_DBFS = "dBFS"
UNIT_DECIBEL = "dB"


def _as_float(value: Any) -> float | None:
    """Parse a value that the feeder may report as a string."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        _LOGGER.debug("Could not parse %r as a number", value)
        return None


def _as_int(value: Any) -> int | None:
    """Parse a counter, which monitor.json sometimes quotes as a string."""
    number = _as_float(value)
    return None if number is None else int(number)


def _as_timestamp(value: Any) -> datetime | None:
    """Parse a Unix timestamp; the feeder uses 0 for 'never'."""
    seconds = _as_float(value)
    if not seconds:
        return None
    return dt_util.utc_from_timestamp(seconds)


def _as_text(value: Any) -> str | None:
    """Return a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cpu_temperature(monitor: dict[str, Any]) -> float | None:
    """Return the SoC temperature that fr24feed reports for the host."""
    cpu = monitor.get("cpu")
    if not isinstance(cpu, dict):
        return None
    return _as_float(cpu.get("gpu_temp"))


def _reports_cpu_temperature(monitor: dict[str, Any]) -> bool:
    """Return True if this feeder reports a host temperature.

    Only the builds for single board computers read one out. On x86 there is
    no SoC to measure, and monitor.json carries no cpu block at all.
    """
    return _cpu_temperature(monitor) is not None


@dataclass(frozen=True, kw_only=True)
class AdsbStationSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor that reads monitor.json."""

    value_fn: Callable[[dict[str, Any]], Any]
    # What monitor.json holds differs per build. When set, this decides from
    # the first poll whether the feeder reports the field at all, so a build
    # that never sends it does not get a sensor stuck on unknown.
    supported_fn: Callable[[dict[str, Any]], bool] | None = None


@dataclass(frozen=True, kw_only=True)
class AdsbStationAircraftSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor that reads aircraft.json."""

    value_fn: Callable[[AircraftStats], Any]


@dataclass(frozen=True, kw_only=True)
class AdsbStationReceptionSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor that reads stats.json."""

    value_fn: Callable[[ReceiverStats], Any]
    # Only create this sensor when the receiver was found to report the
    # optional data it needs.
    feature: str | None = None


FEEDER_SENSORS: tuple[AdsbStationSensorEntityDescription, ...] = (
    AdsbStationSensorEntityDescription(
        key="aircraft_tracked",
        translation_key="aircraft_tracked",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda monitor: _as_int(monitor.get("feed_num_ac_tracked")),
    ),
    AdsbStationSensorEntityDescription(
        key="aircraft_tracked_adsb",
        translation_key="aircraft_tracked_adsb",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda monitor: _as_int(monitor.get("feed_num_ac_adsb_tracked")),
    ),
    AdsbStationSensorEntityDescription(
        key="aircraft_uploaded",
        translation_key="aircraft_uploaded",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda monitor: _as_int(monitor.get("feed_last_ac_sent_num")),
    ),
    AdsbStationSensorEntityDescription(
        key="feed_status",
        translation_key="feed_status",
        value_fn=lambda monitor: _as_text(monitor.get("feed_status")),
    ),
    AdsbStationSensorEntityDescription(
        key="feed_mode",
        translation_key="feed_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda monitor: _as_text(monitor.get("feed_current_mode")),
    ),
    AdsbStationSensorEntityDescription(
        key="feed_alias",
        translation_key="feed_alias",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda monitor: _as_text(monitor.get("feed_alias")),
    ),
    AdsbStationSensorEntityDescription(
        key="map_size",
        translation_key="map_size",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda monitor: _as_int(monitor.get("d11_map_size")),
    ),
    AdsbStationSensorEntityDescription(
        key="resets",
        translation_key="resets",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda monitor: _as_int(monitor.get("num_resets")),
    ),
    AdsbStationSensorEntityDescription(
        key="last_connected",
        translation_key="last_connected",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda monitor: _as_timestamp(monitor.get("feed_last_connected_time")),
    ),
    AdsbStationSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_cpu_temperature,
        supported_fn=_reports_cpu_temperature,
    ),
)

AIRCRAFT_SENSORS: tuple[AdsbStationAircraftSensorEntityDescription, ...] = (
    AdsbStationAircraftSensorEntityDescription(
        key="aircraft_received",
        translation_key="aircraft_received",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.total,
    ),
    AdsbStationAircraftSensorEntityDescription(
        key="aircraft_with_position",
        translation_key="aircraft_with_position",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.with_position,
    ),
    AdsbStationAircraftSensorEntityDescription(
        key="messages",
        translation_key="messages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda stats: stats.messages,
    ),
    AdsbStationAircraftSensorEntityDescription(
        key="message_rate",
        translation_key="message_rate",
        native_unit_of_measurement=UNIT_MESSAGES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.message_rate,
    ),
    AdsbStationAircraftSensorEntityDescription(
        key="max_range",
        translation_key="max_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.max_range,
    ),
    AdsbStationAircraftSensorEntityDescription(
        key="receiver_updated",
        translation_key="receiver_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda stats: stats.updated,
    ),
)

RECEPTION_SENSORS: tuple[AdsbStationReceptionSensorEntityDescription, ...] = (
    AdsbStationReceptionSensorEntityDescription(
        key="signal",
        translation_key="signal",
        native_unit_of_measurement=UNIT_DBFS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.signal,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="noise",
        translation_key="noise",
        native_unit_of_measurement=UNIT_DBFS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.noise,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="signal_to_noise",
        translation_key="signal_to_noise",
        native_unit_of_measurement=UNIT_DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.signal_to_noise,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="peak_signal",
        translation_key="peak_signal",
        native_unit_of_measurement=UNIT_DBFS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.peak_signal,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="strong_signals",
        translation_key="strong_signals",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.strong_signals,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="samples_dropped",
        translation_key="samples_dropped",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.samples_dropped,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="messages_accepted",
        translation_key="messages_accepted",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.accepted,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="tracks",
        translation_key="tracks",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.tracks,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="single_message_tracks",
        translation_key="single_message_tracks",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.single_message_tracks,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="gain",
        translation_key="gain",
        feature=FEATURE_GAIN,
        native_unit_of_measurement=UNIT_DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.gain,
    ),
    AdsbStationReceptionSensorEntityDescription(
        key="demodulator_load",
        translation_key="demodulator_load",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda stats: stats.demodulator_load,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    if coordinator.client.has_feeder:
        monitor = coordinator.data.monitor or {}
        entities.extend(
            AdsbStationSensor(coordinator, description)
            for description in FEEDER_SENSORS
            if description.supported_fn is None or description.supported_fn(monitor)
        )
    if coordinator.client.aircraft_url:
        entities.extend(
            AdsbStationAircraftSensor(coordinator, description)
            for description in AIRCRAFT_SENSORS
        )
        entities.append(AdsbStationClosestAircraftSensor(coordinator))
    if coordinator.client.stats_url:
        features = set(entry.data.get(CONF_RECEIVER_FEATURES) or ())
        entities.extend(
            AdsbStationReceptionSensor(coordinator, description)
            for description in RECEPTION_SENSORS
            if description.feature is None or description.feature in features
        )

    async_add_entities(entities)


class AdsbStationSensor(AdsbStationEntity, SensorEntity):
    """Sensor backed by monitor.json."""

    entity_description: AdsbStationSensorEntityDescription

    def __init__(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        description: AdsbStationSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.monitor)


class AdsbStationAircraftSensor(AdsbStationAircraftEntity, SensorEntity):
    """Sensor backed by aircraft.json."""

    entity_description: AdsbStationAircraftSensorEntityDescription

    def __init__(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        description: AdsbStationAircraftSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if (aircraft := self.aircraft) is None:
            return None
        return self.entity_description.value_fn(aircraft)


class AdsbStationReceptionSensor(AdsbStationReceptionEntity, SensorEntity):
    """Sensor backed by stats.json."""

    entity_description: AdsbStationReceptionSensorEntityDescription

    def __init__(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        description: AdsbStationReceptionSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if (reception := self.reception) is None:
            return None
        return self.entity_description.value_fn(reception)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return which measurement window the value came from."""
        if (reception := self.reception) is None:
            return None
        return {"period": reception.period}


class AdsbStationClosestAircraftSensor(AdsbStationAircraftEntity, SensorEntity):
    """Distance to the nearest aircraft, with its details as attributes."""

    _attr_translation_key = "closest_aircraft"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_suggested_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 1
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "closest_aircraft")

    @property
    def native_value(self) -> float | None:
        """Return the distance to the nearest aircraft."""
        if (aircraft := self.aircraft) is None or aircraft.closest is None:
            return None
        return aircraft.closest.distance

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return who is flying there."""
        if (aircraft := self.aircraft) is None or (closest := aircraft.closest) is None:
            return None
        attributes: dict[str, Any] = {
            "hex": closest.hex,
            "flight": closest.flight,
            "altitude": closest.altitude,
            "speed": closest.speed,
            "track": closest.track,
            "rssi": closest.rssi,
            "seen": closest.seen,
        }
        # Decoders without an aircraft database send none of this, and empty
        # attributes are worse than absent ones on a dashboard.
        if closest.registration is not None:
            attributes["registration"] = closest.registration
        if closest.aircraft_type is not None:
            attributes["aircraft_type"] = closest.aircraft_type
        if closest.description is not None:
            attributes["description"] = closest.description
        if closest.military:
            attributes["military"] = True
        return attributes
