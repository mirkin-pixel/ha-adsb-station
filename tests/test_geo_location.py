"""Tests for the aircraft on the map."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_MAP_AIRCRAFT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import set_responses, setup_integration

# Just over a kilometre from the home location the fixtures pin.
NEARBY_LATITUDE = 52.01
NEARBY_LONGITUDE = 5.0


def _poll(*aircraft: dict[str, Any]) -> dict[str, Any]:
    """Return one aircraft.json holding the given aircraft."""
    return {"now": 1636387404.0, "messages": 10, "aircraft": list(aircraft)}


def _on_the_map(hass: HomeAssistant) -> list[str]:
    """Return the entity IDs currently drawn on the map."""
    return sorted(hass.states.async_entity_ids("geo_location"))


async def _refresh(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)
    )
    await hass.async_block_till_done()


async def test_aircraft_arrive_and_leave(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft is on the map only while it is in range."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True}
    )
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {
                "hex": "484123",
                "flight": "KLM123",
                "lat": NEARBY_LATITUDE,
                "lon": NEARBY_LONGITUDE,
                "alt_baro": 2000,
                "gs": 250,
            }
        ),
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _on_the_map(hass) == ["geo_location.klm123"]
    state = hass.states.get("geo_location.klm123")
    # The state is the distance in kilometres, and the position is where the
    # aircraft said it was
    assert float(state.state) == 1.1
    assert state.attributes["source"] == DOMAIN
    assert state.attributes["latitude"] == NEARBY_LATITUDE
    assert state.attributes["longitude"] == NEARBY_LONGITUDE
    # And everything the sensors carry rides along
    assert state.attributes["altitude"] == 2000
    assert state.attributes["country"] == "AW"

    # It moves on, out of the radius entirely
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {"hex": "484123", "flight": "KLM123", "lat": 53.0, "lon": 5.0, "gs": 250}
        ),
    )
    await _refresh(hass)

    # Gone rather than left behind as unavailable
    assert _on_the_map(hass) == []


async def test_nothing_on_the_map_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the map stays empty until the option is turned on."""
    assert await setup_integration(hass, mock_config_entry)

    assert _on_the_map(hass) == []


async def test_aircraft_without_a_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft with nowhere to draw it is left off the map."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True}
    )
    # Altitude and speed reach us from aircraft that never send a position,
    # and those count as nearby without being placeable
    set_responses(
        aioclient_mock,
        aircraft=_poll({"hex": "484125", "flight": "EZY22", "alt_baro": 3000}),
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _on_the_map(hass) == []


async def test_the_name_is_fixed_when_it_arrives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a callsign arriving late does not move the entity ID."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True}
    )
    # The first poll has no callsign, so the hex code is the only name it has
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {"hex": "484123", "lat": NEARBY_LATITUDE, "lon": NEARBY_LONGITUDE}
        ),
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _on_the_map(hass) == ["geo_location.484123"]

    # A poll later the callsign turns up, and the aircraft has moved
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {
                "hex": "484123",
                "flight": "KLM123",
                "lat": 52.005,
                "lon": NEARBY_LONGITUDE,
            }
        ),
    )
    await _refresh(hass)

    # Same entity, moved, and now carrying the callsign as an attribute
    assert _on_the_map(hass) == ["geo_location.484123"]
    state = hass.states.get("geo_location.484123")
    assert state.attributes["latitude"] == 52.005
    assert state.attributes["flight"] == "KLM123"


async def test_the_map_leaves_no_registry_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the whole point of these entities having no unique ID."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MAP_AIRCRAFT: True}
    )
    set_responses(
        aioclient_mock,
        aircraft=_poll(
            {
                "hex": "484123",
                "flight": "KLM123",
                "lat": NEARBY_LATITUDE,
                "lon": NEARBY_LONGITUDE,
            }
        ),
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _on_the_map(hass) == ["geo_location.klm123"]
    # An aircraft that passes leaves nothing behind to clean up later, which
    # is why it may not be renamed or hidden either
    registry = er.async_get(hass)
    assert [
        entry
        for entry in registry.entities.values()
        if entry.domain == "geo_location"
    ] == []
