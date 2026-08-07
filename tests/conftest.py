"""Fixtures for the ADS-B Station tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.api import build_candidate_urls
from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_RECEIVER_FEATURES,
    CONF_STATS_URL,
    DEFAULT_AIRCRAFT_PORT,
    DOMAIN,
    FEEDER_FR24,
    FEEDER_PIAWARE,
    FEEDER_PLANEFINDER,
    FEEDERS,
)

DEFAULT_PORT = FEEDERS[FEEDER_FR24].port
PIAWARE_PORT = FEEDERS[FEEDER_PIAWARE].port
PLANEFINDER_PORT = FEEDERS[FEEDER_PLANEFINDER].port

MOCK_HOST = "192.168.5.7"
MOCK_ALIAS = "T-EHXX23"
# What the config flow derives for a station without a feeder, and with it the
# prefix of every entity unique_id on such an entry.
RECEIVER_UNIQUE_ID = f"receiver:{MOCK_HOST}"
PIAWARE_UNIQUE_ID = f"piaware:{MOCK_HOST}:8080"
PLANEFINDER_UNIQUE_ID = f"planefinder:{MOCK_HOST}:30053"
FEEDER_URL = f"http://{MOCK_HOST}:{DEFAULT_PORT}/monitor.json"
PIAWARE_URL = f"http://{MOCK_HOST}:{PIAWARE_PORT}/status.json"
PLANEFINDER_URL = f"http://{MOCK_HOST}:{PLANEFINDER_PORT}/ajax/stats"
_DATA_URL = f"http://{MOCK_HOST}:{DEFAULT_AIRCRAFT_PORT}/dump1090/data"
AIRCRAFT_URL = f"{_DATA_URL}/aircraft.json"
STATS_URL = f"{_DATA_URL}/stats.json"
RECEIVER_URL = f"{_DATA_URL}/receiver.json"

# Home Assistant's home location for the tests; the first aircraft below sits
# right on top of it and the second one exactly one degree of latitude north.
HOME_LATITUDE = 52.0
HOME_LONGITUDE = 5.0
EXPECTED_MAX_RANGE_KM = 111.2

MOCK_MONITOR: dict[str, Any] = {
    "build_arch": "armhf",
    "build_os": "raspbian",
    "build_version": "1.0.34-4",
    "cpu": {"gpu_temp": 45.1, "sys": 0.34, "user": 1.2},
    "d11_map_size": 3247,
    "feed_alias": MOCK_ALIAS,
    "feed_current_mode": "MLAT",
    "feed_last_ac_sent_num": 21,
    "feed_last_connected_time": 1636387404,
    "feed_num_ac_adsb_tracked": 20,
    "feed_num_ac_tracked": 25,
    "feed_status": "connected",
    "mlat_ok": True,
    "num_resets": 3,
    "rx_connected": 1,
}

# An x86 feeder, taken from a real one. It quotes every value as a string and
# carries no cpu block at all, because there is no SoC to read a temperature
# from.
MOCK_MONITOR_X86: dict[str, Any] = {
    "build_arch": "static_amd64",
    "build_os": "Linux",
    "build_version": "1.0.57-1",
    "d11_map_size": "0",
    "feed_alias": MOCK_ALIAS,
    "feed_current_mode": "UDP",
    "feed_last_ac_sent_num": "0",
    "feed_last_connected_time": "1786084265",
    "feed_num_ac_adsb_tracked": "0",
    "feed_num_ac_tracked": "0",
    "feed_status": "connected",
    "num_resets": "0",
    "rx_connected": "1",
}

# The first aircraft uses the field names of the dump1090 fork that fr24feed
# ships ("altitude", "speed"), the second the names of dump1090-fa and readsb
# ("alt_baro", "gs"). Both have to work.
MOCK_AIRCRAFT: dict[str, Any] = {
    "now": 1636387404.0,
    "messages": 1000000,
    "aircraft": [
        {
            "hex": "484123",
            "flight": "KLM123",
            "lat": 52.01,
            "lon": 5.0,
            "altitude": 2000,
            "speed": 250,
            "track": 90,
            "rssi": -21.5,
            "seen": 1.2,
            "mlat": [],
            "tisb": [],
        },
        {
            "hex": "484124",
            "flight": "TRA45",
            "lat": 53.0,
            "lon": 5.0,
            "alt_baro": 35000,
            "gs": 450,
        },
        {"hex": "484125", "flight": "EZY22", "squawk": "3124"},
    ],
}
EXPECTED_CLOSEST_KM = 1.1

# Trimmed from a real fr24feed receiver. Its dump1090 fork reports no gain and
# no "adaptive" block, and "accepted" is a list with one entry per error
# correction level.
MOCK_STATS: dict[str, Any] = {
    "latest": {
        "start": 1786051469.0,
        "end": 1786051469.0,
        "local": {"samples_processed": 0, "samples_dropped": 0, "strong_signals": 0},
        "cpu": {"demod": 0, "reader": 0, "background": 0},
        "tracks": {"all": 0, "single_message": 0},
        "messages": 0,
    },
    "last1min": {
        "start": 1786051409.0,
        "end": 1786051469.0,
        "local": {
            "samples_processed": 143917056,
            "samples_dropped": 4,
            "modes": 357314,
            "bad": 188132,
            "unknown_icao": 169172,
            "accepted": [2032, 18],
            "signal": -32.1,
            "noise": -39.1,
            "peak_signal": -31.8,
            "strong_signals": 6,
        },
        "cpu": {"demod": 968, "reader": 123, "background": 6},
        "tracks": {"all": 42, "single_message": 7},
        "messages": 2050,
    },
    "last5min": {
        "start": 1786051169.0,
        "end": 1786051469.0,
        "local": {
            "samples_processed": 719978496,
            "samples_dropped": 0,
            "accepted": [10000],
            "signal": -27.8,
            "noise": -39.1,
            "peak_signal": -21.4,
            "strong_signals": 0,
        },
        "cpu": {"demod": 4800, "reader": 600, "background": 30},
        "tracks": {"all": 120, "single_message": 20},
        "messages": 10000,
    },
    "total": {"start": 1786040000.0, "end": 1786051469.0, "messages": 581066},
}
EXPECTED_DEMODULATOR_LOAD = (968 + 123 + 6) / 60_000 * 100

# What a modern decoder adds: a gain figure, here with adaptive gain running.
EXPECTED_GAIN = 32.8
MOCK_STATS_WITH_GAIN: dict[str, Any] = {
    **MOCK_STATS,
    "last1min": {
        **MOCK_STATS["last1min"],
        "local": {**MOCK_STATS["last1min"]["local"], "gain_db": 49.6},
        "adaptive": {"gain_db": EXPECTED_GAIN, "gain_changes": 3},
    },
}

# readsb puts a single gain_db at the root instead of inside a window, because
# the gain belongs to the dongle. Trimmed from a real wiedehopf readsb 3.16.15.
EXPECTED_READSB_GAIN = 49.6
EXPECTED_FREQUENCY_ERROR = 45.7
# 30 bad out of 200 Mode S messages
EXPECTED_ERROR_RATE = 15.0
MOCK_STATS_READSB: dict[str, Any] = {
    "now": 1786094145.0,
    "gain_db": EXPECTED_READSB_GAIN,
    "estimated_ppm": EXPECTED_FREQUENCY_ERROR,
    "aircraft_with_pos": 1,
    "aircraft_count_by_type": {
        "adsb_icao": 3,
        "adsb_icao_nt": 1,
        "adsb_other": 0,
        "mlat": 2,
        "mode_s": 4,
        "tisb_icao": 0,
        "unknown": 0,
    },
    "last1min": {
        "start": 1786094085.0,
        "end": 1786094145.0,
        "local": {
            "samples_processed": 143982592,
            "samples_dropped": 0,
            "modes": 200,
            "bad": 30,
            "unknown_icao": 0,
            "accepted": [0, 0],
            "noise": -45.1,
            "strong_signals": 0,
        },
        "cpu": {"demod": 65, "reader": 179, "background": 9, "aircraft_json": 5},
        "cpr": {
            "global_ok": 10,
            "local_ok": 4,
            "global_bad": 1,
            "global_range": 2,
            "global_speed": 0,
        },
        "position_count_total": 14,
        "tracks": {"all": 0, "single_message": 0},
        "messages": 0,
    },
    "total": {"start": 1786040000.0, "end": 1786094145.0, "messages": 0},
}

# Straight from a PiAware 11.0 on an x86 host. Note cpu_temp_celcius: a machine
# with nothing to read reports a flat zero rather than leaving the field out,
# and the key really is spelled that way.
MOCK_PIAWARE: dict[str, Any] = {
    "modes_enabled": True,
    "interval": 5000,
    "cpu_load_percent": 17,
    "time": 1786100414712,
    "site_url": "https://flightaware.com/adsb/stats/user/Someone#stats-280586",
    "system_uptime": 4595,
    "expiry": 1786100425712,
    "piaware": {"status": "green", "message": "PiAware 11.0 is running"},
    "uat_enabled": False,
    "cpu_temp_celcius": 0.0,
    "adept": {"status": "green", "message": "Connected to FlightAware and logged in"},
    "mlat": {"status": "amber", "message": "Local clock source is unstable"},
    "piaware_version": "11.0",
    "radio": {"status": "green", "message": "Received Mode S data recently"},
}

# Straight from a pfclient 5.4.211. mlat_bytes_out stays at zero on a station
# whose clock is too unstable to multilaterate.
MOCK_PLANEFINDER: dict[str, Any] = {
    "executable_start_time": 1786095828.3634164,
    "client_version": "5.4.211 amd64",
    "total_modes_packets": 58855,
    "total_modes_packets_ps": 59,
    "total_modeac_packets": 276,
    "total_modeac_packets_ps": 0,
    "total_uat_packets": 0,
    "master_server_bytes_out": 347983,
    "master_server_bytes_in": 95565,
    "local_server_bytes_out": 0,
    "local_server_bytes_in": 88,
    "mlat_bytes_out": 0,
    "mlat_bytes_in": 0,
    "receiver_bytes_out": 0,
    "receiver_bytes_in": 1089724,
    "receiver_bytes_out_ps": 0,
    "receiver_bytes_in_ps": 1092,
    "total_modes_crc_bad": 2,
    "total_modes_crc_corrected": 0,
    "total_modes_types": {"0": 7420, "11": 19036, "17": 7501, "21": 2301},
}

# The fr24feed fork serves this: no coordinates and an unexpanded placeholder
# where the version should be.
MOCK_RECEIVER: dict[str, Any] = {
    "version": "EB_VERSION",
    "refresh": 1000,
    "history": 120,
}

# What readsb serves: a real version and the position of the antenna.
MOCK_RECEIVER_VERSION = "readsb 3.14.1623"
ANTENNA_LATITUDE = 51.9
ANTENNA_LONGITUDE = 5.1
MOCK_RECEIVER_READSB: dict[str, Any] = {
    "version": MOCK_RECEIVER_VERSION,
    "refresh": 1000,
    "history": 120,
    "lat": ANTENNA_LATITUDE,
    "lon": ANTENNA_LONGITUDE,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture(autouse=True)
def home_location(hass: HomeAssistant) -> None:
    """Pin the home location so the range sensor is predictable."""
    hass.config.latitude = HOME_LATITUDE
    hass.config.longitude = HOME_LONGITUDE


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with both endpoints configured."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FR24 feeder",
        unique_id=MOCK_ALIAS,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_FEEDER_TYPE: FEEDER_FR24,
            CONF_AIRCRAFT_URL: AIRCRAFT_URL,
            CONF_STATS_URL: STATS_URL,
            CONF_RECEIVER_FEATURES: [],
        },
    )


@pytest.fixture
def mock_piaware_entry() -> MockConfigEntry:
    """Return an entry for a PiAware feeder with no receiver of its own."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="PiAware feeder",
        unique_id=PIAWARE_UNIQUE_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: PIAWARE_PORT,
            CONF_FEEDER_TYPE: FEEDER_PIAWARE,
            CONF_AIRCRAFT_URL: None,
            CONF_STATS_URL: None,
            CONF_RECEIVER_FEATURES: [],
        },
    )


@pytest.fixture
def mock_planefinder_entry() -> MockConfigEntry:
    """Return an entry for a Plane Finder feeder with no receiver of its own."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Plane Finder feeder",
        unique_id=PLANEFINDER_UNIQUE_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: PLANEFINDER_PORT,
            CONF_FEEDER_TYPE: FEEDER_PLANEFINDER,
            CONF_AIRCRAFT_URL: None,
            CONF_STATS_URL: None,
            CONF_RECEIVER_FEATURES: [],
        },
    )


@pytest.fixture
def mock_receiver_entry() -> MockConfigEntry:
    """Return a mock config entry for a station that runs no fr24feed.

    This is what someone feeding FlightAware, Plane Finder or nothing at all
    ends up with: a decoder and no status page, so no port.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"ADS-B station ({MOCK_HOST})",
        unique_id=RECEIVER_UNIQUE_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: None,
            CONF_AIRCRAFT_URL: AIRCRAFT_URL,
            CONF_STATS_URL: STATS_URL,
            CONF_RECEIVER_FEATURES: [],
        },
    )


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a healthy feeder and receiver."""
    set_responses(aioclient_mock)
    return aioclient_mock


def set_responses(
    aioclient_mock: AiohttpClientMocker,
    *,
    monitor: dict[str, Any] | None = None,
    aircraft: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
    receiver: dict[str, Any] | None = None,
    monitor_kwargs: dict[str, Any] | None = None,
    aircraft_kwargs: dict[str, Any] | None = None,
    stats_kwargs: dict[str, Any] | None = None,
    receiver_kwargs: dict[str, Any] | None = None,
) -> None:
    """Replace the mocked responses of every endpoint."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        FEEDER_URL, **(monitor_kwargs or {"json": monitor or MOCK_MONITOR})
    )
    aioclient_mock.get(
        AIRCRAFT_URL, **(aircraft_kwargs or {"json": aircraft or MOCK_AIRCRAFT})
    )
    aioclient_mock.get(STATS_URL, **(stats_kwargs or {"json": stats or MOCK_STATS}))
    aioclient_mock.get(
        RECEIVER_URL, **(receiver_kwargs or {"json": receiver or MOCK_RECEIVER})
    )
    mock_unused_candidates(aioclient_mock)


def mock_unused_candidates(aioclient_mock: AiohttpClientMocker) -> None:
    """Answer 404 on every candidate URL except the fr24feed one.

    Detection probes all candidates at once, so they all need an answer. The
    mocker uses the first matching registration, which keeps AIRCRAFT_URL.
    """
    for url in build_candidate_urls(MOCK_HOST):
        if url != AIRCRAFT_URL:
            aioclient_mock.get(url, status=404)


def mock_no_aircraft_endpoints(aioclient_mock: AiohttpClientMocker) -> None:
    """Make every candidate aircraft.json URL fail, so detection finds nothing."""
    for url in build_candidate_urls(MOCK_HOST):
        aioclient_mock.get(url, status=404)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    """Set up the integration with a config entry."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return result
