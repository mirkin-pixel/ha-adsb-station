"""Tests for the ADS-B Station API client."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.api import (
    AdsbStationClient,
    AdsbStationInvalidResponseError,
    async_detect_aircraft_url,
    async_detect_statistics,
    build_candidate_urls,
    read_gain,
    sibling_url,
    web_root,
)
from custom_components.adsb_station.const import (
    DEFAULT_PORT,
    FEATURE_AIRCRAFT_TYPES,
    FEATURE_FREQUENCY_ERROR,
    FEATURE_GAIN,
    FEATURE_POSITIONS,
)

from .conftest import (
    AIRCRAFT_URL,
    MOCK_HOST,
    MOCK_STATS,
    MOCK_STATS_READSB,
    MOCK_STATS_WITH_GAIN,
    RECEIVER_URL,
    STATS_URL,
)


async def test_aircraft_without_a_url(hass: HomeAssistant) -> None:
    """Test that reading aircraft.json needs a URL."""
    client = AdsbStationClient(async_get_clientsession(hass), MOCK_HOST, DEFAULT_PORT)

    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_aircraft()


async def test_stats_without_a_url(hass: HomeAssistant) -> None:
    """Test that reading stats.json needs a URL."""
    client = AdsbStationClient(async_get_clientsession(hass), MOCK_HOST, DEFAULT_PORT)

    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_stats()


async def test_receiver_without_a_url(hass: HomeAssistant) -> None:
    """Test that reading receiver.json needs an aircraft.json to sit next to."""
    client = AdsbStationClient(async_get_clientsession(hass), MOCK_HOST, DEFAULT_PORT)

    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_receiver()


async def test_receiver_that_is_not_an_object(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a receiver.json that holds something unexpected."""
    aioclient_mock.get(RECEIVER_URL, json=["nope"])
    client = AdsbStationClient(
        async_get_clientsession(hass), MOCK_HOST, DEFAULT_PORT, AIRCRAFT_URL
    )

    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_receiver()


async def test_stats_detection_rejects_other_documents(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that only a real stats.json is accepted."""
    aioclient_mock.get(STATS_URL, json={"something": "else"})

    assert await async_detect_statistics(
        async_get_clientsession(hass), AIRCRAFT_URL
    ) == (None, [])


def test_sibling_url() -> None:
    """Test deriving the neighbours of aircraft.json."""
    assert sibling_url(AIRCRAFT_URL, "stats.json") == STATS_URL
    assert sibling_url(AIRCRAFT_URL, "receiver.json") == RECEIVER_URL


def test_web_root() -> None:
    """Test deriving the page a human opens from an aircraft.json URL."""
    assert web_root(AIRCRAFT_URL) == f"http://{MOCK_HOST}:8080/dump1090/"
    assert (
        web_root(f"http://{MOCK_HOST}/tar1090/data/aircraft.json")
        == f"http://{MOCK_HOST}/tar1090/"
    )
    # dump1090 straight on the web root has no interface directory above it
    assert web_root(f"http://{MOCK_HOST}:8080/data/aircraft.json") == (
        f"http://{MOCK_HOST}:8080/"
    )
    # A layout we do not know falls back to the root of the server
    assert web_root(f"http://{MOCK_HOST}:8080/odd/aircraft.json") == (
        f"http://{MOCK_HOST}:8080/"
    )


async def test_monitor_without_a_port(hass: HomeAssistant) -> None:
    """Test that a station without a feeder has no status page to read."""
    client = AdsbStationClient(async_get_clientsession(hass), MOCK_HOST)

    assert not client.has_feeder
    assert client.monitor_url is None
    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_monitor()


async def test_stats_detection_without_an_endpoint(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an older dump1090 that serves no statistics at all."""
    aioclient_mock.get(STATS_URL, status=404)

    assert await async_detect_statistics(
        async_get_clientsession(hass), AIRCRAFT_URL
    ) == (None, [])


async def test_stats_that_are_not_statistics(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a stats.json holding something else entirely."""
    aioclient_mock.get(STATS_URL, json={"something": "else"})
    client = AdsbStationClient(
        async_get_clientsession(hass), MOCK_HOST, DEFAULT_PORT, AIRCRAFT_URL, STATS_URL
    )

    with pytest.raises(AdsbStationInvalidResponseError):
        await client.async_get_stats()


def test_candidate_urls_cover_port_80() -> None:
    """Test the URLs we probe, including where readsb and tar1090 put theirs.

    This is checked directly rather than through a detection test, because the
    aiohttp mocker matches on scheme, host and path and ignores the port, so it
    cannot tell a port 80 candidate from its 8080 twin.
    """
    urls = build_candidate_urls(MOCK_HOST)

    assert f"http://{MOCK_HOST}/tar1090/data/aircraft.json" in urls
    assert f"http://{MOCK_HOST}/data/aircraft.json" in urls
    # Port 80 is the http default and must not be written out, or the URL is
    # no longer equal to the one a user would type
    assert not any(":80/" in url for url in urls)
    # The fr24feed path stays the first thing we try
    assert urls[0] == AIRCRAFT_URL


async def test_detection_walks_past_candidates_that_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a receiver serving only a later path is still found."""
    skyaware_url = f"http://{MOCK_HOST}:8080/skyaware/data/aircraft.json"
    for url in build_candidate_urls(MOCK_HOST):
        if url == skyaware_url:
            aioclient_mock.get(url, json={"now": 1.0, "aircraft": []})
        else:
            aioclient_mock.get(url, status=404)

    detected = await async_detect_aircraft_url(async_get_clientsession(hass), MOCK_HOST)

    assert detected == skyaware_url


async def test_detection_prefers_the_first_candidate(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that candidate order decides, not whichever answers first."""
    for url in build_candidate_urls(MOCK_HOST):
        aioclient_mock.get(url, json={"now": 1.0, "aircraft": []})

    detected = await async_detect_aircraft_url(async_get_clientsession(hass), MOCK_HOST)

    assert detected == AIRCRAFT_URL


async def test_detects_gain_support(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a decoder reporting gain gets the feature recorded."""
    aioclient_mock.get(STATS_URL, json=MOCK_STATS_WITH_GAIN)

    assert await async_detect_statistics(
        async_get_clientsession(hass), AIRCRAFT_URL
    ) == (STATS_URL, [FEATURE_GAIN])


async def test_no_gain_support_on_the_fr24feed_fork(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the bundled fork, which reports no gain, records no feature."""
    aioclient_mock.get(STATS_URL, json=MOCK_STATS)

    assert await async_detect_statistics(
        async_get_clientsession(hass), AIRCRAFT_URL
    ) == (STATS_URL, [])


def test_read_gain() -> None:
    """Test every place a decoder may report its gain, and bad values."""
    assert read_gain({"local": {"gain_db": 49.6}}) == 49.6
    # Adaptive gain wins, because that is the value actually in use
    both = {"local": {"gain_db": 49.6}, "adaptive": {"gain_db": 32.8}}
    assert read_gain(both) == 32.8
    assert read_gain({"local": {"signal": -30}}) is None
    assert read_gain({"local": {"gain_db": "loud"}}) is None
    assert read_gain({"local": "not a mapping"}) is None

    # readsb reports it once for the whole document
    assert read_gain({"local": {"noise": -45.1}}, {"gain_db": 49.6}) == 49.6
    assert read_gain({}, {"estimated_ppm": 45.7}) is None
    assert read_gain({}, {"gain_db": "loud"}) is None
    # A window that carries one of its own still wins over the root
    assert read_gain({"local": {"gain_db": 32.8}}, {"gain_db": 49.6}) == 32.8


async def test_detects_everything_readsb_reports(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the features of readsb, which reports the most of any decoder.

    Its gain and the two counters beside it sit at the root of the document,
    where only readsb puts them.
    """
    aioclient_mock.get(STATS_URL, json=MOCK_STATS_READSB)

    url, features = await async_detect_statistics(
        async_get_clientsession(hass), AIRCRAFT_URL
    )

    assert url == STATS_URL
    assert set(features) == {
        FEATURE_GAIN,
        FEATURE_AIRCRAFT_TYPES,
        FEATURE_FREQUENCY_ERROR,
        FEATURE_POSITIONS,
    }
