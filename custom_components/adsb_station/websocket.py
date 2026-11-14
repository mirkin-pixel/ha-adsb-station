"""The sky for the dashboard card, over a websocket subscription.

Only sent to an open card that asked, and never recorded; an entity would
push the whole sky to every browser every poll. Stations are named by device.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import DOMAIN
from .coordinator import AdsbStationDataUpdateCoordinator, aircraft_attributes
from .route import FlightPosition, RouteLookupError, route_points

SUBSCRIBE_AIRCRAFT = f"{DOMAIN}/subscribe_aircraft"
LOOK_UP_ROUTE = f"{DOMAIN}/look_up_route"


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the commands, once for the integration."""
    websocket_api.async_register_command(hass, _subscribe_aircraft)
    websocket_api.async_register_command(hass, _look_up_route)


def _receiver_entry(hass: HomeAssistant, device_id: str) -> ConfigEntry | None:
    """Return the loaded entry with a receiver that a device belongs to.

    Searched from the entries, which works on the oldest supported release.
    """
    registry = dr.async_get(hass)
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
        if not coordinator.client.aircraft_url:
            continue
        devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
        if any(device.id == device_id for device in devices):
            return entry
    return None


def sky(coordinator: AdsbStationDataUpdateCoordinator) -> dict[str, Any]:
    """Return where the station is and every aircraft with a position."""
    latitude, longitude = coordinator.origin
    aircraft = coordinator.data.aircraft
    heard = () if aircraft is None else aircraft.heard
    # Routes are looked up for the nearby ones only, and live on those.
    routes = (
        {}
        if aircraft is None
        else {summary.hex: summary.route for summary in aircraft.nearby}
    )
    distress = (
        {} if aircraft is None else {e.hex: e.reason for e in aircraft.emergencies}
    )
    watched = set() if aircraft is None else {m.summary.hex for m in aircraft.watched}
    planes = []
    for summary in heard:
        if summary.position is None:
            continue
        plane = {
            **aircraft_attributes(summary, include_distance=True),
            "latitude": summary.position[0],
            "longitude": summary.position[1],
        }
        # Only when so, to stand out on the radar.
        if (reason := distress.get(summary.hex)) is not None:
            plane["emergency"] = reason
        if summary.hex in watched:
            plane["watched"] = True
        if (points := route_points(routes.get(summary.hex))) is not None:
            plane["route_points"] = points
        planes.append(plane)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius": coordinator.proximity_radius / 1000,
        "aircraft": planes,
        # The shape the card draws, when the decoder keeps one.
        "outline": coordinator.outline,
    }


# Untyped: the decorator's type differs between old and new Home Assistant.
_SUBSCRIBE_SCHEMA: Any = {
    vol.Required("type"): SUBSCRIBE_AIRCRAFT,
    vol.Required("device_id"): str,
}


@websocket_api.websocket_command(_SUBSCRIBE_SCHEMA)
@callback
def _subscribe_aircraft(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the sky now, and again after every poll until unsubscribed."""
    if (entry := _receiver_entry(hass, msg["device_id"])) is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "No loaded ADS-B station with a receiver has this device",
        )
        return
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data

    @callback
    def _send() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], sky(coordinator))
        )

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_send)
    connection.send_result(msg["id"])
    # Trails go out once; the card extends them itself from then on.
    connection.send_message(
        websocket_api.event_message(
            msg["id"], {**sky(coordinator), "trails": coordinator.trails.as_dict()}
        )
    )


# Untyped for the same reason as the subscription's schema.
_LOOK_UP_ROUTE_SCHEMA: Any = {
    vol.Required("type"): LOOK_UP_ROUTE,
    vol.Required("device_id"): str,
    vol.Required("hex"): str,
}


@websocket_api.websocket_command(_LOOK_UP_ROUTE_SCHEMA)
@websocket_api.async_response
async def _look_up_route(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Answer where an aircraft tapped on the card is flying from and to.

    Through the shared lookup, so it can take up to thirty seconds. The
    status says why there are no points: "off", "unknown" or "failed".
    """
    if (entry := _receiver_entry(hass, msg["device_id"])) is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "No loaded ADS-B station with a receiver has this device",
        )
        return
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
    aircraft = coordinator.data.aircraft
    summary = next(
        (
            summary
            for summary in (() if aircraft is None else aircraft.heard)
            if summary.hex == msg["hex"]
        ),
        None,
    )
    if coordinator.route_lookup is None:
        connection.send_result(msg["id"], {"route_points": None, "status": "off"})
        return
    if summary is None or summary.flight is None:
        connection.send_result(msg["id"], {"route_points": None, "status": "unknown"})
        return
    flight = FlightPosition(
        callsign=summary.flight,
        latitude=None if summary.position is None else summary.position[0],
        longitude=None if summary.position is None else summary.position[1],
    )
    try:
        route = await coordinator.route_lookup.async_look_up(flight)
    except RouteLookupError:
        connection.send_result(msg["id"], {"route_points": None, "status": "failed"})
        return
    points = route_points(route)
    connection.send_result(
        msg["id"],
        {"route_points": points, "status": "unknown" if points is None else "found"},
    )
