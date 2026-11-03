"""Geolocation platform: one entity per aircraft inside the nearby radius.

No unique ID on purpose, so passing aircraft leave nothing in the entity
registry; the cost is that they cannot be renamed or hidden in the UI.
"""

from __future__ import annotations

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import MATCH_ALL, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CATEGORY_ROTORCRAFT,
    CLIMB_RATE_SHOWN,
    CONF_MAP_AIRCRAFT,
    DEFAULT_MAP_AIRCRAFT,
    DOMAIN,
)
from .coordinator import (
    AdsbStationConfigEntry,
    AdsbStationDataUpdateCoordinator,
    AircraftSummary,
    aircraft_attributes,
)

# Updates are centralized through the coordinator
PARALLEL_UPDATES = 0


def aircraft_icon(summary: AircraftSummary) -> str:
    """Return the icon for what an aircraft is, then what it is doing."""
    if summary.category == CATEGORY_ROTORCRAFT:
        return "mdi:helicopter"
    if summary.military:
        return "mdi:shield-airplane"
    rate = summary.vertical_rate
    if rate is not None and rate >= CLIMB_RATE_SHOWN:
        return "mdi:airplane-takeoff"
    if rate is not None and rate <= -CLIMB_RATE_SHOWN:
        return "mdi:airplane-landing"
    return "mdi:airplane"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the aircraft on the map, if this station was asked for them."""
    if not entry.options.get(CONF_MAP_AIRCRAFT, DEFAULT_MAP_AIRCRAFT):
        # Turning the option on reloads the entry, so this runs again.
        return

    coordinator = entry.runtime_data
    shown: dict[str, AdsbStationAircraftLocation] = {}

    @callback
    def _follow() -> None:
        """Put every aircraft in range on the map, and take the rest off."""
        aircraft = coordinator.data.aircraft
        nearby = () if aircraft is None else aircraft.nearby

        arrived: list[AdsbStationAircraftLocation] = []
        in_range: set[str] = set()
        for summary in nearby:
            # Always set for nearby aircraft; this is for the type checker.
            if (position := summary.position) is None:
                continue
            in_range.add(summary.hex)
            if (entity := shown.get(summary.hex)) is None:
                entity = AdsbStationAircraftLocation(coordinator, summary, position)
                shown[summary.hex] = entity
                arrived.append(entity)
            else:
                entity.follow(summary, position)

        if arrived:
            async_add_entities(arrived)

        for hex_code in shown.keys() - in_range:
            shown.pop(hex_code).leave()

    _follow()
    entry.async_on_unload(coordinator.async_add_listener(_follow))


class AdsbStationAircraftLocation(GeolocationEvent):
    """One aircraft on the map, for as long as it is in range."""

    _attr_should_poll = False
    _attr_source = DOMAIN
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS
    # The map reads the live state; recording every position is not worth it.
    _attr_unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        coordinator: AdsbStationDataUpdateCoordinator,
        summary: AircraftSummary,
        position: tuple[float, float],
    ) -> None:
        """Initialize the aircraft at the position it arrived on."""
        # Fixed at arrival, so a late callsign does not change the entity ID.
        self._attr_name = summary.flight or summary.hex
        self._apply(summary, position)

    def _apply(self, summary: AircraftSummary, position: tuple[float, float]) -> None:
        """Take over the position and distance of one poll."""
        self._summary = summary
        self._attr_latitude, self._attr_longitude = position
        self._attr_distance = (
            None if summary.distance is None else summary.distance / 1000
        )

    @callback
    def follow(self, summary: AircraftSummary, position: tuple[float, float]) -> None:
        """Move the aircraft to where the latest poll saw it."""
        self._apply(summary, position)
        self.async_write_ha_state()

    @callback
    def leave(self) -> None:
        """Take the aircraft off the map now that it has flown on.

        Forced, or an entity without a unique ID stays behind as unavailable.
        """
        if self.hass is not None:
            self.hass.async_create_task(self.async_remove(force_remove=True))

    @property
    def icon(self) -> str:
        """Return what the aircraft is, or what it is doing."""
        return aircraft_icon(self._summary)

    @property
    def extra_state_attributes(self) -> dict[str, str | float | None]:
        """Return everything else known; the distance is the state."""
        return aircraft_attributes(self._summary)
