"""Tests for the feeders other than fr24feed."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN

from .conftest import (
    MOCK_PIAWARE,
    MOCK_PLANEFINDER,
    PIAWARE_UNIQUE_ID,
    PIAWARE_URL,
    PLANEFINDER_UNIQUE_ID,
    PLANEFINDER_URL,
    setup_integration,
)


def _state(hass: HomeAssistant, device_id: str, platform: str, key: str) -> str | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{device_id}_{key}"
    )
    if entity_id is None:
        return None
    return hass.states.get(entity_id).state


def _attributes(hass: HomeAssistant, device_id: str, key: str) -> dict:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{device_id}_{key}"
    )
    assert entity_id is not None, key
    return dict(hass.states.get(entity_id).attributes)


async def test_piaware(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the entities of a FlightAware feeder."""
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)

    assert await setup_integration(hass, mock_piaware_entry)

    # Three colours, not two states, so an amber MLAT keeps its meaning
    assert _state(hass, PIAWARE_UNIQUE_ID, "sensor", "piaware_radio") == "green"
    assert _state(hass, PIAWARE_UNIQUE_ID, "sensor", "piaware_feed") == "green"
    assert _state(hass, PIAWARE_UNIQUE_ID, "sensor", "piaware_mlat") == "amber"
    assert (
        _attributes(hass, PIAWARE_UNIQUE_ID, "piaware_mlat")["message"]
        == "Local clock source is unstable"
    )
    assert _state(hass, PIAWARE_UNIQUE_ID, "sensor", "piaware_cpu_load") == "17"

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, PIAWARE_UNIQUE_ID)}
    )
    assert device is not None
    assert device.manufacturer == "FlightAware"
    assert device.model == "PiAware"
    assert device.sw_version == "11.0"


async def test_piaware_without_a_temperature_sensor(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a flat zero temperature does not become a sensor.

    A host with nothing to read reports 0.0 rather than leaving the field out,
    which would otherwise be an entity stuck at freezing forever.
    """
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)

    assert await setup_integration(hass, mock_piaware_entry)

    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{PIAWARE_UNIQUE_ID}_piaware_cpu_temperature"
        )
        is None
    )


async def test_piaware_with_a_temperature_sensor(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a host that does read one gets the sensor."""
    aioclient_mock.get(PIAWARE_URL, json={**MOCK_PIAWARE, "cpu_temp_celcius": 42.5})

    assert await setup_integration(hass, mock_piaware_entry)

    assert (
        _state(hass, PIAWARE_UNIQUE_ID, "sensor", "piaware_cpu_temperature") == "42.5"
    )


async def test_planefinder(
    hass: HomeAssistant,
    mock_planefinder_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the entities of a Plane Finder feeder."""
    aioclient_mock.get(PLANEFINDER_URL, json=MOCK_PLANEFINDER)

    assert await setup_integration(hass, mock_planefinder_entry)

    assert _state(hass, PLANEFINDER_UNIQUE_ID, "sensor", "pf_message_rate") == "59"
    assert _state(hass, PLANEFINDER_UNIQUE_ID, "sensor", "pf_messages") == "58855"
    assert _state(hass, PLANEFINDER_UNIQUE_ID, "sensor", "pf_crc_errors") == "2"
    # Bytes natively, megabytes suggested
    assert float(
        _state(hass, PLANEFINDER_UNIQUE_ID, "sensor", "pf_uploaded")
    ) == pytest.approx(0.347983)

    # Nothing multilaterated is nothing sent
    assert _state(hass, PLANEFINDER_UNIQUE_ID, "binary_sensor", "pf_mlat") == "off"

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, PLANEFINDER_UNIQUE_ID)}
    )
    assert device is not None
    assert device.manufacturer == "Plane Finder"
    assert device.model == "pfclient"
    assert device.sw_version == "5.4.211 amd64"


async def test_planefinder_mlat_when_it_is_sending(
    hass: HomeAssistant,
    mock_planefinder_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that bytes on the wire turn the multilateration sensor on."""
    aioclient_mock.get(
        PLANEFINDER_URL, json={**MOCK_PLANEFINDER, "mlat_bytes_out": 4096}
    )

    assert await setup_integration(hass, mock_planefinder_entry)

    assert _state(hass, PLANEFINDER_UNIQUE_ID, "binary_sensor", "pf_mlat") == "on"


async def test_a_feeder_without_a_receiver_has_no_aircraft_entities(
    hass: HomeAssistant,
    mock_planefinder_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a second feeder on one station does not duplicate the decoder.

    A station commonly runs several feeders off one decoder. Only the entry
    that was given the aircraft.json reports on it; the others stay feeds.
    """
    aioclient_mock.get(PLANEFINDER_URL, json=MOCK_PLANEFINDER)

    assert await setup_integration(hass, mock_planefinder_entry)

    registry = er.async_get(hass)
    for key in ("aircraft_received", "max_range", "closest_aircraft", "max_range_n"):
        assert (
            registry.async_get_entity_id(
                "sensor", DOMAIN, f"{PLANEFINDER_UNIQUE_ID}_{key}"
            )
            is None
        ), key
