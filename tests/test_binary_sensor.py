"""Tests for the ADS-B Station binary sensors."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.binary_sensor import _as_bool
from custom_components.adsb_station.const import DOMAIN

from .conftest import MOCK_ALIAS, MOCK_MONITOR, set_responses, setup_integration


def _state(hass: HomeAssistant, key: str) -> str | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def test_healthy_feeder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the binary sensors of a feeder that is fully connected."""
    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "receiver") == STATE_ON
    assert _state(hass, "feed") == STATE_ON
    assert _state(hass, "mlat") == STATE_ON


async def test_disconnected_feeder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a feeder that lost both its receiver and its uplink."""
    set_responses(
        aioclient_mock,
        monitor={
            **MOCK_MONITOR,
            "rx_connected": 0,
            "feed_status": "disconnected",
            "mlat_ok": False,
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "receiver") == STATE_OFF
    assert _state(hass, "feed") == STATE_OFF
    assert _state(hass, "mlat") == STATE_OFF


async def test_unknown_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test values that the integration cannot interpret."""
    set_responses(
        aioclient_mock,
        monitor={"feed_alias": MOCK_ALIAS, "feed_status": "reconnecting"},
    )

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "receiver") == STATE_UNKNOWN
    assert _state(hass, "feed") == STATE_UNKNOWN
    assert _state(hass, "mlat") == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("1", True),
        ("0", False),
        (" Connected ", True),
        ("DISCONNECTED", False),
        ("yes", True),
        ("maybe", None),
        (None, None),
        ([], None),
    ],
)
def test_as_bool(value: object, expected: bool | None) -> None:
    """Test the flag parser against everything monitor.json may contain."""
    assert _as_bool(value) is expected


async def test_no_emergency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that ordinary traffic does not raise the emergency flag."""
    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_emergency"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["aircraft"] == []


@pytest.mark.parametrize(
    ("entry", "expected_reason"),
    [
        ({"hex": "484126", "flight": "KLM99", "squawk": "7700"}, "emergency"),
        ({"hex": "484126", "squawk": "7600"}, "radio_failure"),
        ({"hex": "484126", "squawk": " 7500 "}, "hijack"),
        # dump1090-fa states it outright instead of leaving it to the squawk
        ({"hex": "484126", "emergency": "lifeguard"}, "lifeguard"),
    ],
)
async def test_emergency_detected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entry: dict,
    expected_reason: str,
) -> None:
    """Test the emergency codes and the explicit emergency field."""
    set_responses(
        aioclient_mock,
        aircraft={"now": 1636387404.0, "messages": 10, "aircraft": [entry]},
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_emergency"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["aircraft"] == [
        {
            "hex": "484126",
            "flight": entry.get("flight"),
            "squawk": (entry.get("squawk") or "").strip() or None,
            "reason": expected_reason,
        }
    ]


async def test_emergency_field_saying_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an explicit 'none' is not treated as an emergency."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [{"hex": "484126", "emergency": "none", "squawk": "1000"}],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_emergency"
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_aircraft_overhead(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the binary sensor for something inside the radius."""
    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "nearby") == STATE_ON
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_nearby"
    )
    attributes = hass.states.get(entity_id).attributes
    assert [item["flight"] for item in attributes["aircraft"]] == ["KLM123"]


async def test_nothing_overhead(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a far away aircraft leaves the sensor off."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            # One degree of latitude out, well past the default radius
            "aircraft": [{"hex": "484124", "flight": "TRA45", "lat": 53.0, "lon": 5.0}],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "nearby") == STATE_OFF
