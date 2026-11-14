"""Event entities for the rare events, to pick in the automation editor.

Passages and approaches stay bus events only: dozens a day would each write
a row with every aircraft field.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EMERGENCY_STATUSES,
    EVENT_AIRCRAFT_EMERGENCY,
    EVENT_WATCHLIST_LOST,
    EVENT_WATCHLIST_MATCH,
)
from .coordinator import (
    AdsbStationConfigEntry,
    AdsbStationDataUpdateCoordinator,
    watchlist_signal,
)
from .entity import AdsbStationAircraftEntity

# The station is the device the entity is on already.
_OWN_KEYS = {"entry_id", "station", "device_id"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdsbStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    coordinator = entry.runtime_data
    if not coordinator.client.aircraft_url:
        return
    async_add_entities([AdsbStationDistressEvent(coordinator)])

    # Only while there is a list, as the watchlist sensor.
    watching: list[AdsbStationWatchlistEvent] = []

    @callback
    def _follow_watchlist() -> None:
        if coordinator.watchlist and not watching:
            watching.append(AdsbStationWatchlistEvent(coordinator))
            async_add_entities(watching)
        elif not coordinator.watchlist:
            watching.clear()
            registry = er.async_get(hass)
            unique_id = f"{entry.unique_id or entry.entry_id}_watchlist_event"
            if entity_id := registry.async_get_entity_id("event", DOMAIN, unique_id):
                registry.async_remove(entity_id)

    _follow_watchlist()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, watchlist_signal(entry.entry_id), _follow_watchlist
        )
    )


class _AdsbStationEvent(AdsbStationAircraftEntity, EventEntity):
    """Repeats this station's bus events, as types of one entity."""

    # Bus event, and the event type it becomes; None takes the reason.
    _follows: ClassVar[dict[str, str | None]]

    async def async_added_to_hass(self) -> None:
        """Listen for this station's events."""
        await super().async_added_to_hass()
        for bus_event, event_type in self._follows.items():
            self.async_on_remove(
                self.hass.bus.async_listen(bus_event, self._make_handler(event_type))
            )

    def _make_handler(self, event_type: str | None) -> Callable[[Event], None]:
        entry_id = self.coordinator.config_entry.entry_id

        @callback
        def handle(event: Event) -> None:
            data = event.data
            # Another station's, or one fired by hand without one or a known reason.
            kind = event_type or data.get("reason")
            if data.get("entry_id") != entry_id or kind not in self.event_types:
                return
            self._trigger_event(
                kind,
                {key: value for key, value in data.items() if key not in _OWN_KEYS},
            )
            self.async_write_ha_state()

        return handle


class AdsbStationWatchlistEvent(_AdsbStationEvent):
    """A watched aircraft comes into range, or has left it."""

    _attr_translation_key = "watchlist"
    _attr_event_types = ["in_range", "left"]
    _follows = {EVENT_WATCHLIST_MATCH: "in_range", EVENT_WATCHLIST_LOST: "left"}

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "watchlist_event")


class AdsbStationDistressEvent(_AdsbStationEvent):
    """An aircraft in range declares an emergency, by its reason."""

    _attr_translation_key = "distress"
    _attr_event_types = list(dict.fromkeys(EMERGENCY_STATUSES.values()))
    _follows = {EVENT_AIRCRAFT_EMERGENCY: None}

    def __init__(self, coordinator: AdsbStationDataUpdateCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "distress")
