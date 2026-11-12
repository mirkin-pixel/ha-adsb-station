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
        monitor={
            "feed_alias": MOCK_ALIAS,
            "feed_status": "reconnecting",
            # Present, so the sensor exists, but not something we can read
            "mlat_ok": "maybe",
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "receiver") == STATE_UNKNOWN
    assert _state(hass, "feed") == STATE_UNKNOWN
    assert _state(hass, "mlat") == STATE_UNKNOWN


@pytest.mark.parametrize(("value", "expected"), [("YES", STATE_ON), ("NO", STATE_OFF)])
async def test_mlat_as_fr24feed_writes_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    value: str,
    expected: str,
) -> None:
    """Test the key fr24feed itself writes: "mlat-ok", YES or NO.

    The 1.0.57 binary and its status script know no other; "mlat_ok" was
    never seen on a real feeder.
    """
    monitor = {key: item for key, item in MOCK_MONITOR.items() if key != "mlat_ok"}
    set_responses(aioclient_mock, monitor={**monitor, "mlat-ok": value})

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "mlat") == expected


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
        # readsb and dump1090-fa state it outright, under the same reasons as
        # the squawk, so one word means one thing whichever decoder it is
        ({"hex": "484126", "emergency": "general"}, "emergency"),
        ({"hex": "484126", "emergency": "unlawful"}, "hijack"),
        ({"hex": "484126", "emergency": "NORDO"}, "radio_failure"),
        ({"hex": "484126", "emergency": "downed"}, "downed"),
        # A status that is no distress does not hide a squawk that is
        ({"hex": "484126", "emergency": "lifeguard", "squawk": "7700"}, "emergency"),
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
            "distance": None,
            "altitude": None,
            "aircraft_type": None,
        }
    ]


async def test_emergency_tells_how_far_and_how_high(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the distance, height and type next to the reason."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "484126",
                    "squawk": "7700",
                    "lat": 52.1,
                    "lon": 5.0,
                    "alt_baro": 12000,
                    "t": "B738",
                }
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MOCK_ALIAS}_emergency"
    )
    [aircraft] = hass.states.get(entity_id).attributes["aircraft"]
    assert aircraft["distance"] == 11.1
    assert aircraft["altitude"] == 12000
    assert aircraft["aircraft_type"] == "B738"


@pytest.mark.parametrize(
    "status",
    # Priority for a medical flight, a warning before any emergency, and unused
    ["none", "lifeguard", "minfuel", "reserved"],
)
async def test_emergency_field_saying_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: str,
) -> None:
    """Test that a status that is no distress is not an emergency."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [{"hex": "484126", "emergency": status, "squawk": "1000"}],
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
