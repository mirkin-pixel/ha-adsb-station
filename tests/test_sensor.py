"""Tests for the ADS-B Station sensors."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import (
    CONF_PROXIMITY_RADIUS,
    CONF_RECEIVER_FEATURES,
    CONF_STATS_URL,
    DEFAULT_PROXIMITY_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEATURE_AIRCRAFT_TYPES,
    FEATURE_FREQUENCY_ERROR,
    FEATURE_GAIN,
    FEATURE_POSITIONS,
)
from custom_components.adsb_station.sensor import _as_float, _as_int, _as_timestamp

from .conftest import (
    EXPECTED_CLOSEST_KM,
    EXPECTED_DEMODULATOR_LOAD,
    EXPECTED_ERROR_RATE,
    EXPECTED_FREQUENCY_ERROR,
    EXPECTED_GAIN,
    EXPECTED_MAX_RANGE_KM,
    EXPECTED_READSB_GAIN,
    MOCK_AIRCRAFT,
    MOCK_ALIAS,
    MOCK_HOST,
    MOCK_MONITOR,
    MOCK_MONITOR_X86,
    MOCK_STATS,
    MOCK_STATS_READSB,
    MOCK_STATS_WITH_GAIN,
    set_responses,
    setup_integration,
)


def _attributes(hass: HomeAssistant, key: str) -> dict:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None
    return dict(hass.states.get(entity_id).attributes)


def entry_of(entry: MockConfigEntry) -> MockConfigEntry:
    """Return a fresh entry with the same configuration."""
    return MockConfigEntry(
        domain=DOMAIN, unique_id=entry.unique_id, data=dict(entry.data)
    )


def _state(hass: HomeAssistant, key: str) -> str | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def _refresh(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL + 5)
    )
    await hass.async_block_till_done()


async def test_feeder_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the values that come from monitor.json."""
    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "aircraft_tracked") == "25"
    assert _state(hass, "aircraft_tracked_adsb") == "20"
    assert _state(hass, "aircraft_uploaded") == "21"
    assert _state(hass, "feed_status") == "connected"
    assert _state(hass, "feed_mode") == "MLAT"
    assert _state(hass, "feed_alias") == MOCK_ALIAS
    assert _state(hass, "map_size") == "3247"
    assert _state(hass, "resets") == "3"
    assert _state(hass, "cpu_temperature") == "45.1"

    last_connected = dt_util.parse_datetime(_state(hass, "last_connected"))
    assert last_connected == dt_util.utc_from_timestamp(1636387404)


async def test_aircraft_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the values derived from aircraft.json."""
    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "aircraft_received") == "3"
    assert _state(hass, "aircraft_with_position") == "2"
    assert _state(hass, "messages") == "1000000"
    # The first poll has nothing to compare against
    assert _state(hass, "message_rate") == STATE_UNKNOWN
    assert float(_state(hass, "max_range")) == pytest.approx(
        EXPECTED_MAX_RANGE_KM, abs=0.5
    )

    updated = dt_util.parse_datetime(_state(hass, "receiver_updated"))
    assert updated == dt_util.utc_from_timestamp(MOCK_AIRCRAFT["now"])


async def test_message_rate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the message rate over consecutive polls."""
    assert await setup_integration(hass, mock_config_entry)

    set_responses(
        mock_api,
        aircraft={**MOCK_AIRCRAFT, "now": 1636387414.0, "messages": 1000500},
    )
    await _refresh(hass)
    assert float(_state(hass, "message_rate")) == pytest.approx(50.0)

    # A restarted receiver resets both its counter and its clock
    set_responses(
        mock_api, aircraft={**MOCK_AIRCRAFT, "now": 1636387424.0, "messages": 12}
    )
    await _refresh(hass)
    assert _state(hass, "message_rate") == STATE_UNKNOWN

    # Two samples with the same timestamp cannot produce a rate either
    set_responses(
        mock_api, aircraft={**MOCK_AIRCRAFT, "now": 1636387424.0, "messages": 99}
    )
    await _refresh(hass)
    assert _state(hass, "message_rate") == STATE_UNKNOWN


async def test_empty_and_garbled_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that missing or unparsable values become unknown."""
    set_responses(
        aioclient_mock,
        monitor={
            "feed_status": "",
            "rx_connected": 1,
            "feed_num_ac_tracked": "not a number",
            "cpu": "not a mapping",
            "feed_last_connected_time": 0,
        },
        aircraft={"aircraft": [], "now": None},
    )

    assert await setup_integration(hass, mock_config_entry)

    for key in (
        "feed_status",
        "feed_mode",
        "feed_alias",
        "aircraft_tracked",
        "aircraft_tracked_adsb",
        "map_size",
        "resets",
        "last_connected",
        "cpu_temperature",
        "messages",
        "message_rate",
        "max_range",
        "receiver_updated",
    ):
        assert _state(hass, key) == STATE_UNKNOWN, key

    assert _state(hass, "aircraft_received") == "0"
    assert _state(hass, "aircraft_with_position") == "0"


async def test_aircraft_without_usable_positions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that malformed aircraft entries are skipped."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                "not a mapping",
                {"hex": "484123", "lat": "bad", "lon": 5.0},
                {"hex": "484124", "lat": 52.0},
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "aircraft_received") == "2"
    assert _state(hass, "aircraft_with_position") == "0"
    assert _state(hass, "max_range") == STATE_UNKNOWN


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the device registry entry for the feeder."""
    assert await setup_integration(hass, mock_config_entry)

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MOCK_ALIAS)})
    assert device is not None
    assert device.manufacturer == "Flightradar24"
    assert device.model == "fr24feed"
    assert device.name == MOCK_ALIAS
    assert device.sw_version == MOCK_MONITOR["build_version"]
    assert device.hw_version == MOCK_MONITOR["build_arch"]
    assert device.configuration_url == f"http://{MOCK_HOST}:8754/"


async def test_device_falls_back_to_a_generic_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a feeder that has not been given an alias yet."""
    set_responses(
        aioclient_mock, monitor={"rx_connected": 1, "feed_status": "connecting"}
    )

    assert await setup_integration(hass, mock_config_entry)

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MOCK_ALIAS)})
    assert device is not None
    assert device.name == "FR24 feeder"
    assert device.sw_version is None


async def test_no_cpu_sensor_on_a_feeder_without_a_soc(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an x86 feeder gets no temperature sensor it could never fill.

    Its monitor.json has no cpu block, so the sensor would sit on unknown for
    the life of the entry.
    """
    set_responses(aioclient_mock, monitor=MOCK_MONITOR_X86)

    assert await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_cpu_temperature")
        is None
    )
    # The rest of the feeder sensors are there, parsed out of quoted strings
    assert _state(hass, "aircraft_tracked") == "0"
    assert _state(hass, "map_size") == "0"
    assert _state(hass, "feed_mode") == "UDP"


async def test_cpu_sensor_survives_an_unreadable_cpu_block(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that garbled data keeps the sensor, unlike a build without one.

    A feeder that sends a cpu block has a temperature to report; one poll it
    could not be read from is worth showing as unknown rather than silently
    dropping the sensor for the life of the entry.
    """
    set_responses(aioclient_mock, monitor={**MOCK_MONITOR_X86, "cpu": "not a mapping"})

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "cpu_temperature") == STATE_UNKNOWN


def test_parse_helpers() -> None:
    """Test the value parsers directly for the cases the feeder rarely shows."""
    assert _as_float(None) is None
    assert _as_float(True) is None
    assert _as_float("nope") is None
    assert _as_float("3.5") == 3.5

    assert _as_int("42") == 42
    assert _as_int(None) is None

    assert _as_timestamp(0) is None
    assert _as_timestamp("nope") is None
    assert _as_timestamp(1636387404) == dt_util.utc_from_timestamp(1636387404)


async def test_reception_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the reception statistics from stats.json."""
    assert await setup_integration(hass, mock_config_entry)

    assert float(_state(hass, "signal")) == pytest.approx(-32.1)
    assert float(_state(hass, "noise")) == pytest.approx(-39.1)
    assert float(_state(hass, "signal_to_noise")) == pytest.approx(7.0)
    assert float(_state(hass, "peak_signal")) == pytest.approx(-31.8)
    assert _state(hass, "strong_signals") == "6"
    assert _state(hass, "samples_dropped") == "4"
    # "accepted" is a list with one entry per error correction level
    assert _state(hass, "messages_accepted") == "2050"
    assert _state(hass, "tracks") == "42"
    assert _state(hass, "single_message_tracks") == "7"
    assert float(_state(hass, "demodulator_load")) == pytest.approx(
        EXPECTED_DEMODULATOR_LOAD
    )

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_signal"
    )
    assert hass.states.get(entity_id).attributes["period"] == "last1min"


async def test_reception_falls_back_to_a_longer_window(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a receiver that has not measured a signal in the last minute yet."""
    set_responses(
        aioclient_mock,
        stats={
            **MOCK_STATS,
            "last1min": {
                **MOCK_STATS["last1min"],
                "local": {"samples_processed": 0, "samples_dropped": 0},
            },
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert float(_state(hass, "signal")) == pytest.approx(-27.8)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_signal"
    )
    assert hass.states.get(entity_id).attributes["period"] == "last5min"


async def test_reception_without_any_usable_window(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a stats.json that only carries lifetime totals."""
    set_responses(aioclient_mock, stats={"total": {"messages": 581066}})

    assert await setup_integration(hass, mock_config_entry)

    for key in (
        "signal",
        "noise",
        "signal_to_noise",
        "peak_signal",
        "strong_signals",
        "samples_dropped",
        "tracks",
        "single_message_tracks",
        "demodulator_load",
    ):
        assert _state(hass, key) == STATE_UNKNOWN, key
    # An absent "accepted" list sums to nothing rather than to zero
    assert _state(hass, "messages_accepted") == STATE_UNKNOWN


async def test_closest_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the nearest aircraft and its details."""
    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    state = hass.states.get(entity_id)
    assert float(state.state) == pytest.approx(EXPECTED_CLOSEST_KM, abs=0.2)

    # This aircraft uses the field names of the fr24feed dump1090 fork
    assert state.attributes["hex"] == "484123"
    assert state.attributes["flight"] == "KLM123"
    assert state.attributes["altitude"] == 2000
    assert state.attributes["speed"] == 250
    assert state.attributes["track"] == 90
    assert state.attributes["rssi"] == -21.5
    assert state.attributes["seen"] == 1.2


async def test_closest_aircraft_reads_dump1090_fa_field_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that alt_baro and gs are understood as well."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "484124",
                    "lat": 52.01,
                    "lon": 5.0,
                    "alt_baro": 35000,
                    "gs": 450,
                }
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["altitude"] == 35000
    assert state.attributes["speed"] == 450
    assert state.attributes["flight"] is None


async def test_closest_aircraft_without_positions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a quiet moment where nothing reports a position."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [{"hex": "3c6521", "seen": 96.0, "rssi": -31.9}],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("hex") is None


async def test_range_is_measured_from_the_receiver_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a receiver.json with coordinates wins over the home location."""
    set_responses(aioclient_mock, receiver={"lat": 52.5, "lon": 5.0, "history": 120})

    assert await setup_integration(hass, mock_config_entry)

    # Half a degree of latitude to the aircraft at 53.0, instead of a full one
    assert float(_state(hass, "max_range")) == pytest.approx(55.6, abs=0.5)


async def test_reception_sensors_need_a_stats_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a receiver without stats.json gets no statistics entities."""
    set_responses(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_STATS_URL: None},
    )

    assert await setup_integration(hass, entry)

    assert (
        er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_signal")
        is None
    )
    assert _state(hass, "aircraft_received") == "3"


async def test_range_survives_a_missing_receiver_json(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a receiver that does not serve receiver.json."""
    set_responses(aioclient_mock, receiver_kwargs={"status": 404})

    assert await setup_integration(hass, mock_config_entry)

    # Falls back to the Home Assistant home location
    assert float(_state(hass, "max_range")) == pytest.approx(
        EXPECTED_MAX_RANGE_KM, abs=0.5
    )


async def test_gain_sensor_needs_a_decoder_that_reports_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the fr24feed fork gets no gain sensor it could never fill."""
    assert await setup_integration(hass, mock_config_entry)

    assert (
        er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_gain")
        is None
    )


async def test_gain_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the gain sensor on a decoder that reports one."""
    set_responses(aioclient_mock, stats=MOCK_STATS_WITH_GAIN)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_RECEIVER_FEATURES: [FEATURE_GAIN]},
    )

    assert await setup_integration(hass, entry)

    # The adaptive value, not the configured one
    assert float(_state(hass, "gain")) == pytest.approx(EXPECTED_GAIN)


async def test_gain_sensor_reads_the_readsb_layout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the gain sensor on readsb, which reports it at the document root."""
    set_responses(aioclient_mock, stats=MOCK_STATS_READSB)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_RECEIVER_FEATURES: [FEATURE_GAIN]},
    )

    assert await setup_integration(hass, entry)

    assert float(_state(hass, "gain")) == pytest.approx(EXPECTED_READSB_GAIN)
    # This station hears nothing, so there is a noise floor but no signal
    assert _state(hass, "noise") == "-45.1"
    assert _state(hass, "signal") == STATE_UNKNOWN
    assert _state(hass, "signal_to_noise") == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        # readsb and dump1090-fa, which prefer the barometric rate
        ({"baro_rate": -1088, "geom_rate": -1024}, -1088),
        # A climb the aircraft only reported against GNSS
        ({"geom_rate": 1216}, 1216),
        # The dump1090 fork that fr24feed ships
        ({"vert_rate": 640}, 640),
        # An aircraft on the ground reports none of the three
        ({}, None),
    ],
)
async def test_closest_aircraft_vertical_rate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    fields: dict[str, int],
    expected: int | None,
) -> None:
    """Test the rate of climb, under each of the names a decoder gives it."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {"hex": "484123", "lat": 52.01, "lon": 5.0, "alt_baro": 2000, **fields}
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    assert hass.states.get(entity_id).attributes["vertical_rate"] == expected


async def test_closest_aircraft_names_from_the_shipped_tables(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the two names no decoder sends and no request is made for.

    A database that fills in the type code without describing it is what a
    readsb with the usual aircraft.csv.gz does, and the airline is not in
    aircraft.json under any decoder.
    """
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "3c65cd",
                    "flight": "DLH6CH",
                    "lat": 52.01,
                    "lon": 5.0,
                    "alt_baro": 37375,
                    "r": "D-AINM",
                    "t": "A20N",
                }
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    attributes = hass.states.get(entity_id).attributes
    assert attributes["airline"] == "Lufthansa"
    assert attributes["description"] == "Airbus A-320neo"


async def test_closest_aircraft_keeps_the_decoders_own_description(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a decoder that describes the type itself is not overruled."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "3c65cd",
                    "flight": "PHABC",
                    "lat": 52.01,
                    "lon": 5.0,
                    "alt_baro": 2000,
                    "t": "A20N",
                    "desc": "AIRBUS A-320neo",
                }
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    attributes = hass.states.get(entity_id).attributes
    assert attributes["description"] == "AIRBUS A-320neo"
    # A registration flown as a callsign names no airline
    assert "airline" not in attributes


async def test_closest_aircraft_database_fields(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the registration and type that readsb adds from its database."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "484123",
                    "flight": "KLM123",
                    "lat": 52.01,
                    "lon": 5.0,
                    "alt_baro": 2000,
                    "r": "PH-BXA",
                    "t": "B738",
                    "desc": "Boeing 737-800",
                    "dbFlags": 0,
                }
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    attributes = hass.states.get(entity_id).attributes
    assert attributes["registration"] == "PH-BXA"
    assert attributes["aircraft_type"] == "B738"
    assert attributes["description"] == "Boeing 737-800"
    # dbFlags without the military bit does not add the marker
    assert "military" not in attributes


async def test_closest_aircraft_military_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test bit 0 of dbFlags, which readsb sets for military aircraft."""
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {"hex": "43c6e1", "lat": 52.01, "lon": 5.0, "r": "ZZ333", "dbFlags": 1}
            ],
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    assert hass.states.get(entity_id).attributes["military"] is True


async def test_closest_aircraft_without_a_database(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a decoder without a database adds no empty attributes."""
    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_closest_aircraft"
    )
    attributes = hass.states.get(entity_id).attributes
    for key in ("registration", "aircraft_type", "description", "military"):
        assert key not in attributes


async def test_nearby_highest_and_fastest(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test the proximity sensors against the default ten kilometre radius."""
    assert await setup_integration(hass, mock_config_entry)

    # Only KLM123, at 1.1 km, is inside the radius; TRA45 sits 111 km out
    assert _state(hass, "aircraft_nearby") == "1"
    attributes = _attributes(hass, "aircraft_nearby")
    assert attributes["radius"] == DEFAULT_PROXIMITY_RADIUS
    assert [item["flight"] for item in attributes["aircraft"]] == ["KLM123"]
    assert attributes["aircraft"][0]["distance"] == pytest.approx(
        EXPECTED_CLOSEST_KM, abs=0.1
    )

    # The highest and the fastest are both TRA45, reported in readsb's names
    assert float(_state(hass, "highest_aircraft")) == pytest.approx(35000)
    assert _attributes(hass, "highest_aircraft")["flight"] == "TRA45"
    assert float(_state(hass, "fastest_aircraft")) == pytest.approx(450)
    assert _attributes(hass, "fastest_aircraft")["flight"] == "TRA45"


async def test_nearby_radius_is_configurable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that widening the radius brings the far aircraft in."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_config_entry.unique_id,
        data=dict(mock_config_entry.data),
        options={CONF_PROXIMITY_RADIUS: 200},
    )

    assert await setup_integration(hass, entry)

    assert _state(hass, "aircraft_nearby") == "2"
    attributes = _attributes(hass, "aircraft_nearby")
    assert attributes["radius"] == 200
    # Nearest first
    assert [item["flight"] for item in attributes["aircraft"]] == ["KLM123", "TRA45"]


async def test_highest_counts_aircraft_without_a_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a Mode S aircraft still counts for highest and fastest.

    Altitude and speed reach us from aircraft that never send a position, and
    leaving those out would understate both figures.
    """
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "484123",
                    "flight": "KLM123",
                    "lat": 52.01,
                    "lon": 5.0,
                    "altitude": 2000,
                    "speed": 250,
                },
                {"hex": "484199", "flight": "NOPOS1", "alt_baro": 41000, "gs": 500},
            ],
        },
    )

    assert await setup_integration(hass, entry_of(mock_config_entry))

    assert float(_state(hass, "highest_aircraft")) == pytest.approx(41000)
    assert _attributes(hass, "highest_aircraft")["flight"] == "NOPOS1"
    # It has no position, so it cannot be nearby and has no distance
    assert _attributes(hass, "highest_aircraft")["distance"] is None
    assert _state(hass, "aircraft_nearby") == "1"


async def test_station_health_on_readsb(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the health figures a readsb station reports."""
    set_responses(aioclient_mock, stats=MOCK_STATS_READSB)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mock_config_entry.unique_id,
        data={
            **mock_config_entry.data,
            CONF_RECEIVER_FEATURES: [
                FEATURE_GAIN,
                FEATURE_AIRCRAFT_TYPES,
                FEATURE_FREQUENCY_ERROR,
                FEATURE_POSITIONS,
            ],
        },
    )

    assert await setup_integration(hass, entry)

    # adsb_icao 3 + adsb_icao_nt 1 + adsb_other 0
    assert _state(hass, "aircraft_adsb") == "4"
    assert _state(hass, "aircraft_mlat") == "2"
    assert _state(hass, "aircraft_mode_s") == "4"
    assert float(_state(hass, "frequency_error")) == pytest.approx(
        EXPECTED_FREQUENCY_ERROR
    )
    # global_ok 10 + local_ok 4, against global_bad 1 + range 2 + speed 0
    assert _state(hass, "positions_decoded") == "14"
    assert _state(hass, "positions_rejected") == "3"
    assert float(_state(hass, "error_rate")) == pytest.approx(EXPECTED_ERROR_RATE)


async def test_health_sensors_absent_on_the_fr24feed_fork(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a decoder reporting none of this gets none of the sensors."""
    assert await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    for key in (
        "aircraft_adsb",
        "aircraft_mlat",
        "aircraft_mode_s",
        "frequency_error",
        "positions_decoded",
        "positions_rejected",
    ):
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_{key}")
            is None
        ), key

    # The error rate needs nothing optional, so it is there either way
    assert float(_state(hass, "error_rate")) == pytest.approx(188132 / 357314 * 100)


async def test_feeder_health_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the clock and feed figures an x86 feeder reports."""
    set_responses(
        aioclient_mock,
        monitor={
            **MOCK_MONITOR_X86,
            "timing_last_drift": "-0.169",
            "timing_source": "NTP",
            "feed_current_server": "blender.prod.fr24.io",
            "num_resyncs": "0",
        },
    )

    assert await setup_integration(hass, mock_config_entry)

    assert float(_state(hass, "clock_drift")) == pytest.approx(-0.169)
    assert _state(hass, "timing_source") == "NTP"
    assert _state(hass, "feed_server") == "blender.prod.fr24.io"
    assert _state(hass, "resyncs") == "0"


async def test_feeder_health_sensors_absent_on_an_older_build(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a feeder reporting no timing gets no timing sensors."""
    assert await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    for key in ("clock_drift", "timing_source", "feed_server", "resyncs"):
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_ALIAS}_{key}")
            is None
        ), key


async def test_error_rate_is_unknown_without_traffic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a quiet minute has no error rate rather than a perfect zero."""
    quiet = {
        **MOCK_STATS_READSB,
        "last1min": {
            **MOCK_STATS_READSB["last1min"],
            "local": {**MOCK_STATS_READSB["last1min"]["local"], "modes": 0, "bad": 0},
        },
    }
    set_responses(aioclient_mock, stats=quiet)

    assert await setup_integration(hass, mock_config_entry)

    assert _state(hass, "error_rate") == STATE_UNKNOWN


async def test_no_mlat_sensor_on_a_build_that_never_reports_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a feeder with no mlat_ok gets no sensor stuck on unknown.

    The x86 builds leave the field out entirely rather than saying it is off,
    which is the same trap the CPU temperature fell into.
    """
    set_responses(aioclient_mock, monitor=MOCK_MONITOR_X86)

    assert await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("binary_sensor", DOMAIN, f"{MOCK_ALIAS}_mlat")
        is None
    )
    # The two it does report are still there
    for key in ("receiver", "feed"):
        assert (
            registry.async_get_entity_id("binary_sensor", DOMAIN, f"{MOCK_ALIAS}_{key}")
            is not None
        ), key


async def test_highest_and_fastest_outlive_the_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that an empty sky does not blank what was last heard.

    A station hearing a couple of aircraft an hour would otherwise report
    nothing most of the time.
    """
    assert await setup_integration(hass, mock_config_entry)
    assert float(_state(hass, "highest_aircraft")) == pytest.approx(35000)

    set_responses(mock_api, aircraft={"now": 2.0, "messages": 2, "aircraft": []})
    await _refresh(hass)

    assert float(_state(hass, "highest_aircraft")) == pytest.approx(35000)
    assert float(_state(hass, "fastest_aircraft")) == pytest.approx(450)
    assert float(_state(hass, "max_range")) == pytest.approx(
        EXPECTED_MAX_RANGE_KM, abs=0.5
    )
    assert _attributes(hass, "highest_aircraft")["flight"] == "TRA45"
    assert _attributes(hass, "max_range")["flight"] == "TRA45"
    assert _attributes(hass, "highest_aircraft")["seen_at"] is not None
    # And the live figures do go blank, because those are about right now
    assert _state(hass, "aircraft_received") == "0"


async def test_a_higher_aircraft_replaces_the_reading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the reading follows the sky rather than only ever growing.

    Unlike the sector records this is the last one heard, not the best ever,
    so a lower aircraft afterwards is what it reports.
    """
    assert await setup_integration(hass, mock_config_entry)

    set_responses(
        mock_api,
        aircraft={
            "now": 3.0,
            "messages": 3,
            "aircraft": [{"hex": "aa1", "flight": "LOW1", "alt_baro": 900, "gs": 120}],
        },
    )
    await _refresh(hass)

    assert float(_state(hass, "highest_aircraft")) == pytest.approx(900)
    assert _attributes(hass, "highest_aircraft")["flight"] == "LOW1"



@pytest.mark.parametrize(
    ("key", "attribute"),
    [("aircraft_nearby", "aircraft"), ("passages_today", "passages")],
)
async def test_the_long_lists_are_kept_out_of_the_database(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    key: str,
    attribute: str,
) -> None:
    """Test that the lists are readable but not recorded.

    Both of these carry a list of aircraft beside a state that is only a
    number, and both are rewritten far more often than the number changes, so
    recording them writes the whole list again for every arrival. Telling the
    recorder to leave the attribute alone keeps the history and the statistics
    of the number itself, which is what excluding the entity outright costs.
    """
    assert await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_ALIAS}_{key}"
    )
    state = hass.states.get(entity_id)

    # Still there for a template, a card or an automation to read
    assert attribute in state.attributes
    # Beside the ones every sensor leaves out of the database already
    assert attribute in state.state_info["unrecorded_attributes"]
