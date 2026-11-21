"""The ADS-B Station integration."""

from __future__ import annotations

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .aircraft_db import database_of
from .announced import Announced
from .api import AdsbStationClient
from .card import async_register_card
from .const import (
    CONF_AIRCRAFT_DATABASE,
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_LOOK_UP_ROUTES,
    CONF_STATS_URL,
    CONF_UNITS,
    CONF_WATCHLIST,
    DOMAIN,
    FEEDER_FR24,
    ISSUE_BAD_TUNER,
    ISSUE_SET_BY_HAND,
    ISSUE_UNITS,
)
from .coordinator import (
    AdsbStationConfigEntry,
    AdsbStationDataUpdateCoordinator,
    sky_signal,
)
from .passage_log import PassageLog
from .reference import async_load_reference
from .repairs import (
    set_by_hand_issue_id,
    set_by_hand_placeholders,
    units_issue_id,
    units_placeholders,
)
from .sentences import async_check_sentences
from .services import async_setup_services
from .sightings import Sightings
from .units import set_by_hand
from .websocket import async_setup_websocket

# What the option was called while it named a source rather than a yes or no.
LEGACY_ROUTE_SOURCE = "route_source"
# The sensor that counted PiAware's uptime, before it became a start time.
LEGACY_PIAWARE_UPTIME = "piaware_uptime"
# The moment aircraft.json was last read, on by default until 0.8.5.
RECEIVER_UPDATED = "receiver_updated"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.GEO_LOCATION,
    Platform.SENSOR,
    Platform.TEXT,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services, websocket commands and card once, not per entry.

    Per entry, removing one feeder would unregister them for the others.
    """
    async_setup_services(hass)
    async_setup_websocket(hass)
    await async_register_card(hass)
    await async_check_sentences(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdsbStationConfigEntry) -> bool:
    """Set up an ADS-B station from a config entry."""
    client = AdsbStationClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        # A station without fr24feed has no status page to read.
        entry.data.get(CONF_PORT),
        entry.data.get(CONF_AIRCRAFT_URL),
        entry.data.get(CONF_STATS_URL),
        feeder_type=entry.data.get(CONF_FEEDER_TYPE),
    )
    coordinator = AdsbStationDataUpdateCoordinator(
        hass, entry, client, await async_load_reference(hass)
    )
    if client.aircraft_url:
        await coordinator.sightings.async_load()
        await coordinator.passage_log.async_load()
        await coordinator.announced.async_load(coordinator.remembered())
        # Written now, or a reload would read them before the delayed write.
        entry.async_on_unload(coordinator.sightings.async_save)
        entry.async_on_unload(coordinator.passage_log.async_save)
        entry.async_on_unload(coordinator.announced.async_save)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    # The downloaded table goes once no station uses it any more.
    if not any(
        other.options.get(CONF_AIRCRAFT_DATABASE)
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        await hass.async_add_executor_job(database_of(hass).remove)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: async_dispatcher_send(hass, sky_signal(entry.entry_id))
        )
    )

    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> bool:
    """Bring an entry made by an older version up to date."""
    data = {**entry.data}
    options = {**entry.options}

    # Entries from before other feeders can only be fr24feed.
    if entry.version < 2 and CONF_FEEDER_TYPE not in data:
        data[CONF_FEEDER_TYPE] = (
            FEEDER_FR24 if data.get(CONF_PORT) is not None else None
        )

    # Picking either old route source becomes routes switched on.
    if entry.version < 3 and LEGACY_ROUTE_SOURCE in options:
        options[CONF_LOOK_UP_ROUTES] = options.pop(LEGACY_ROUTE_SOURCE) not in (
            None,
            "none",
        )

    # PiAware's uptime sensor became a start time; the old one is removed.
    if entry.version < 4:
        registry = er.async_get(hass)
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registered.unique_id.endswith(f"_{LEGACY_PIAWARE_UPTIME}"):
                registry.async_remove(registered.entity_id)

    # "Last read" is now off by default, and switched off once for old entries.
    if entry.version < 5:
        registry = er.async_get(hass)
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                registered.unique_id.endswith(f"_{RECEIVER_UPDATED}")
                and registered.disabled_by is None
            ):
                registry.async_update_entity(
                    registered.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )

    # Sensors took the units fixed before 1.4; they look again once, as they
    # do when the setting changes.
    if entry.version < 5 or entry.minor_version < 2:
        _refresh_sensor_units(hass, entry)
        if data.get(CONF_AIRCRAFT_URL):
            _ask_for_units(hass, entry)

    # A unit set by hand back then was likely a way round the mixed units, and
    # Home Assistant has no way back from one; offered once, under Repairs.
    # 1.4.0b3 went out without this, hence its own step.
    if entry.version < 5 or entry.minor_version < 3:
        _ask_about_units_set_by_hand(hass, entry)

    hass.config_entries.async_update_entry(
        entry, data=data, options=options, version=5, minor_version=3
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> bool:
    """Unload a config entry."""
    # A silent receiver is noticed again by the next coordinator, and an entry
    # that is being removed should not leave a repair behind that names it.
    ir.async_delete_issue(hass, DOMAIN, f"receiver_silent_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_BAD_TUNER}_{entry.entry_id}")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_options_updated(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> None:
    """Apply a change: the watchlist in place, anything else by reload.

    Reconfiguring changes the data, and comes through here as well.
    """
    coordinator = entry.runtime_data
    if dict(entry.data) != coordinator.started_with_data:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    before, after = coordinator.started_with, dict(entry.options)
    changed = {
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    }
    if changed <= {CONF_WATCHLIST}:
        await coordinator.async_set_watchlist()
        return
    if CONF_UNITS in changed:
        _refresh_sensor_units(hass, entry)
        # Chosen, so there is nothing left to ask.
        ir.async_delete_issue(hass, DOMAIN, units_issue_id(entry.entry_id))
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> None:
    """Take the questions about units and the kept files away with it."""
    ir.async_delete_issue(hass, DOMAIN, units_issue_id(entry.entry_id))
    ir.async_delete_issue(hass, DOMAIN, set_by_hand_issue_id(entry.entry_id))
    await Sightings(hass, entry.entry_id).async_remove()
    await PassageLog(hass, entry.entry_id, 0).async_remove()
    await Announced(hass, entry.entry_id).async_remove()


def _ask_about_units_set_by_hand(
    hass: HomeAssistant, entry: AdsbStationConfigEntry
) -> None:
    """Offer to let the sensors with a unit of their own follow the setting."""
    if not (sensors := set_by_hand(hass, entry.entry_id)):
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        set_by_hand_issue_id(entry.entry_id),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_SET_BY_HAND,
        translation_placeholders=set_by_hand_placeholders(entry, sensors),
        data={"entry_id": entry.entry_id},
    )


def _ask_for_units(hass: HomeAssistant, entry: AdsbStationConfigEntry) -> None:
    """Tell an upgraded station that its figures changed unit, and let it pick.

    Automations and dashboards hold numbers of their own, which nothing here
    can convert; Aviation keeps heights in feet and speeds in knots.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        units_issue_id(entry.entry_id),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_UNITS,
        translation_placeholders=units_placeholders(hass, entry),
        data={"entry_id": entry.entry_id},
    )


def _refresh_sensor_units(hass: HomeAssistant, entry: AdsbStationConfigEntry) -> None:
    """Have this station's sensors take their unit from the setting again.

    Home Assistant keeps the unit a sensor first had, and asks again the same
    way when its own unit system changes. A unit chosen on the sensor itself
    is kept apart and still wins.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != SENSOR_DOMAIN:
            continue
        private = dict(entity.options.get(f"{SENSOR_DOMAIN}.private", {}))
        private["refresh_initial_entity_options"] = True
        registry.async_update_entity_options(
            entity.entity_id, f"{SENSOR_DOMAIN}.private", private
        )
