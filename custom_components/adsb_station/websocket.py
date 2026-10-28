"""The sky as the dashboard card draws it, over the websocket.

The card's radar shows every aircraft with a position, not only the ones
inside the nearby radius, and no entity carries that list. Putting it in one
would send the whole sky to every open browser on every poll, whether a radar
is on screen or not, and every attribute change is written to the state
machine. A subscription sends it only to a card that asked for it, only while
that card is open, and nothing of it is ever recorded.

The station is named by its device, which is what the card already knows: it
finds its entities by device and translation key.
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

SUBSCRIBE_AIRCRAFT = f"{DOMAIN}/subscribe_aircraft"


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the commands, once for the integration."""
    websocket_api.async_register_command(hass, _subscribe_aircraft)


def _receiver_entry(hass: HomeAssistant, device_id: str) -> ConfigEntry | None:
    """Return the loaded entry with a receiver that a device belongs to.

    Asked the other way round, entry to devices, because the device's own
    list of entries is on its way out and the single entry that replaces it
    is newer than the oldest Home Assistant this supports.
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
    """Return where the station is and every aircraft it can place.

    The aircraft without a position are left out: there is nowhere to draw
    them. The ones with one carry the same attributes the nearby list does,
    plus where they are.
    """
    latitude, longitude = coordinator.origin
    aircraft = coordinator.data.aircraft
    heard = () if aircraft is None else aircraft.heard
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius": coordinator.proximity_radius / 1000,
        "aircraft": [
            {
                **aircraft_attributes(summary, include_distance=True),
                "latitude": summary.position[0],
                "longitude": summary.position[1],
            }
            for summary in heard
            if summary.position is not None
        ],
    }


# Left untyped on purpose. Newer Home Assistant types this decorator against
# probatio's markers, the oldest one supported against voluptuous's, and the
# voluptuous markers written here are accepted by both when it runs.
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
    # The trails so far go out once, with the first sky: after that the card
    # extends them itself from every position it is sent, which keeps what
    # goes over the websocket on every poll small.
    connection.send_message(
        websocket_api.event_message(
            msg["id"], {**sky(coordinator), "trails": coordinator.trails.as_dict()}
        )
    )
