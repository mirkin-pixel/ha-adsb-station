"""Tests for the ADS-B Station config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.api import build_candidate_urls
from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_PROXIMITY_RADIUS,
    CONF_RECEIVER_FEATURES,
    CONF_ROUTE_SOURCE,
    CONF_STATS_URL,
    DOMAIN,
    FEEDER_FR24,
    ROUTE_SOURCE_ADSBDB,
    ROUTE_SOURCE_NONE,
)
from custom_components.adsb_station.route import AdsbdbLookup

from .conftest import (
    AIRCRAFT_URL,
    DEFAULT_PORT,
    FEEDER_URL,
    MOCK_AIRCRAFT,
    MOCK_ALIAS,
    MOCK_HOST,
    MOCK_MONITOR,
    MOCK_STATS,
    RECEIVER_UNIQUE_ID,
    STATS_URL,
    mock_no_aircraft_endpoints,
    mock_unused_candidates,
    set_responses,
    setup_integration,
)

CUSTOM_AIRCRAFT_URL = f"http://{MOCK_HOST}:8080/custom/aircraft.json"


def _suggested(result: dict[str, Any], key: str) -> Any:
    """Return the value a form field is prefilled with."""
    for marker in result["data_schema"].schema:
        if marker == key:
            return marker.description["suggested_value"]
    raise AssertionError(f"{key} is not in the form")


async def _choose(hass: HomeAssistant, step: str) -> dict[str, Any]:
    """Open the flow and pick one of the two kinds of station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {
        "fr24feed",
        "piaware",
        "planefinder",
        "receiver",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result


async def _start_user_step(
    hass: HomeAssistant, host: str = MOCK_HOST
) -> dict[str, Any]:
    """Run the menu and the feeder step of the user flow."""
    result = await _choose(hass, "fr24feed")
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host, CONF_PORT: DEFAULT_PORT}
    )


async def _start_receiver_step(
    hass: HomeAssistant, host: str = MOCK_HOST
) -> dict[str, Any]:
    """Run the menu and the receiver step of the user flow."""
    result = await _choose(hass, "receiver")
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )


async def test_user_flow(hass: HomeAssistant, mock_api: AiohttpClientMocker) -> None:
    """Test a full flow, with the receiver detected automatically."""
    result = await _start_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "aircraft"
    assert _suggested(result, CONF_AIRCRAFT_URL) == AIRCRAFT_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ALIAS
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_FEEDER_TYPE: FEEDER_FR24,
        CONF_AIRCRAFT_URL: AIRCRAFT_URL,
        CONF_STATS_URL: STATS_URL,
        # This receiver reports no gain, so the feature is not recorded
        CONF_RECEIVER_FEATURES: [],
    }
    assert result["result"].unique_id == MOCK_ALIAS


async def test_user_flow_without_a_receiver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a flow where no aircraft.json is found and the field is left empty."""
    aioclient_mock.get(FEEDER_URL, json=MOCK_MONITOR)
    mock_no_aircraft_endpoints(aioclient_mock)

    result = await _start_user_step(hass)
    assert result["step_id"] == "aircraft"
    assert _suggested(result, CONF_AIRCRAFT_URL) == ""

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: "  "}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AIRCRAFT_URL] is None


async def test_user_flow_without_an_alias(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a feeder without an alias falls back to host and port."""
    aioclient_mock.get(FEEDER_URL, json={"rx_connected": 1})
    aioclient_mock.get(AIRCRAFT_URL, json=MOCK_AIRCRAFT)
    aioclient_mock.get(STATS_URL, json=MOCK_STATS)
    mock_unused_candidates(aioclient_mock)

    result = await _start_user_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"FR24 feeder ({MOCK_HOST})"
    assert result["result"].unique_id == f"{MOCK_HOST}:{DEFAULT_PORT}"


@pytest.mark.parametrize(
    ("monitor_kwargs", "expected_error"),
    [
        ({"exc": aiohttp.ClientError("boom")}, "cannot_connect"),
        ({"exc": TimeoutError}, "cannot_connect"),
        ({"status": 500}, "cannot_connect"),
        ({"text": "not json"}, "invalid_response"),
        ({"json": {"something": "else"}}, "invalid_response"),
    ],
)
async def test_user_flow_feeder_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monitor_kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    """Test the errors of the first step, then recovery."""
    aioclient_mock.get(FEEDER_URL, **monitor_kwargs)

    result = await _start_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    set_responses(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST, CONF_PORT: DEFAULT_PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "aircraft"


async def test_user_flow_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an unexpected error while reading monitor.json."""
    with patch(
        "custom_components.adsb_station.config_flow.AdsbStationClient.async_get_feeder",
        side_effect=ValueError,
    ):
        result = await _start_user_step(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("aircraft_kwargs", "expected_error"),
    [
        ({"exc": aiohttp.ClientError("boom")}, "cannot_connect_aircraft"),
        ({"status": 404}, "cannot_connect_aircraft"),
        ({"json": {"no": "aircraft"}}, "invalid_aircraft_response"),
    ],
)
async def test_user_flow_receiver_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    aircraft_kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    """Test the errors of the second step, then recovery."""
    aioclient_mock.get(FEEDER_URL, json=MOCK_MONITOR)
    mock_no_aircraft_endpoints(aioclient_mock)
    aioclient_mock.get(CUSTOM_AIRCRAFT_URL, **aircraft_kwargs)

    result = await _start_user_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: CUSTOM_AIRCRAFT_URL}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    # The rejected URL is offered again so it can be corrected
    assert _suggested(result, CONF_AIRCRAFT_URL) == CUSTOM_AIRCRAFT_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: ""}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_receiver_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an unexpected error while reading aircraft.json."""
    aioclient_mock.get(FEEDER_URL, json=MOCK_MONITOR)
    mock_no_aircraft_endpoints(aioclient_mock)

    result = await _start_user_step(hass)
    with patch(
        "custom_components.adsb_station.config_flow.AdsbStationClient.async_get_aircraft",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AIRCRAFT_URL: CUSTOM_AIRCRAFT_URL}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the same feeder cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_step(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test moving a configured feeder to a new address."""
    assert await setup_integration(hass, mock_config_entry)
    new_host = "192.168.5.8"
    mock_api.get(f"http://{new_host}:{DEFAULT_PORT}/monitor.json", json=MOCK_MONITOR)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    # Reconfigure skips the menu: the kind of station is already known
    assert result["step_id"] == "fr24feed"
    assert _suggested(result, CONF_HOST) == MOCK_HOST

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host, CONF_PORT: DEFAULT_PORT}
    )
    assert result["step_id"] == "aircraft"
    # The configured URL is kept instead of probing for a new one
    assert _suggested(result, CONF_AIRCRAFT_URL) == AIRCRAFT_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host


async def test_reconfigure_to_another_feeder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that pointing an entry at a different feeder is refused."""
    assert await setup_integration(hass, mock_config_entry)
    other_host = "192.168.5.9"
    mock_api.get(
        f"http://{other_host}:{DEFAULT_PORT}/monitor.json",
        json={**MOCK_MONITOR, "feed_alias": "T-OTHER1"},
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: other_host, CONF_PORT: DEFAULT_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_feeder"
    assert mock_config_entry.data[CONF_HOST] == MOCK_HOST


async def test_receiver_only_flow(
    hass: HomeAssistant, mock_api: AiohttpClientMocker
) -> None:
    """Test setting up a station that runs no fr24feed at all."""
    result = await _start_receiver_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "receiver_url"
    assert _suggested(result, CONF_AIRCRAFT_URL) == AIRCRAFT_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ADS-B station ({MOCK_HOST})"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        # No feeder, so no status page port and no kind of feeder
        CONF_PORT: None,
        CONF_FEEDER_TYPE: None,
        CONF_AIRCRAFT_URL: AIRCRAFT_URL,
        CONF_STATS_URL: STATS_URL,
        CONF_RECEIVER_FEATURES: [],
    }
    assert result["result"].unique_id == RECEIVER_UNIQUE_ID
    # The feeder is never contacted on this path
    assert not [
        request for request in mock_api.mock_calls if str(request[1]) == FEEDER_URL
    ]


async def test_receiver_only_flow_needs_a_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the receiver URL cannot be skipped when it is the only source."""
    mock_no_aircraft_endpoints(aioclient_mock)
    aioclient_mock.get(CUSTOM_AIRCRAFT_URL, json=MOCK_AIRCRAFT)
    aioclient_mock.get(f"http://{MOCK_HOST}:8080/custom/stats.json", json=MOCK_STATS)

    result = await _start_receiver_step(hass)
    assert result["step_id"] == "receiver_url"
    # Nothing was detected, so nothing is prefilled
    assert _suggested(result, CONF_AIRCRAFT_URL) == ""

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: "   "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "aircraft_url_required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: CUSTOM_AIRCRAFT_URL}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AIRCRAFT_URL] == CUSTOM_AIRCRAFT_URL


async def test_receiver_only_flow_rejects_a_bad_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the error of the receiver step, then recovery."""
    mock_no_aircraft_endpoints(aioclient_mock)
    aioclient_mock.get(CUSTOM_AIRCRAFT_URL, json={"no": "aircraft"})

    result = await _start_receiver_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: CUSTOM_AIRCRAFT_URL}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_aircraft_response"}
    assert _suggested(result, CONF_AIRCRAFT_URL) == CUSTOM_AIRCRAFT_URL


def _resolves_to(address: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return what getaddrinfo says about a host on one address."""
    return [(2, 1, 6, "", (address, 0))]


async def test_one_machine_under_two_names_is_read_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a decoder is not offered again under a different name.

    The existing entry was set up on an address and this one is being set up
    on a name, so the strings differ and only resolving them tells you it is
    the same machine.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.adsb_station.config_flow.socket.getaddrinfo",
        return_value=_resolves_to(MOCK_HOST),
    ):
        result = await _start_receiver_step(hass, "adsb.local")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "receiver_url"
    assert _suggested(result, CONF_AIRCRAFT_URL) == ""


async def test_a_second_machine_is_offered_its_own_decoder(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a station somewhere else keeps its own receiver offered."""
    mock_config_entry.add_to_hass(hass)
    elsewhere = "other.local"
    candidates = build_candidate_urls(elsewhere)
    aioclient_mock.get(candidates[0], json=MOCK_AIRCRAFT)
    for url in candidates[1:]:
        aioclient_mock.get(url, status=404)

    with patch(
        "custom_components.adsb_station.config_flow.socket.getaddrinfo",
        side_effect=lambda host, _port: _resolves_to(
            MOCK_HOST if host == MOCK_HOST else "192.168.5.99"
        ),
    ):
        result = await _start_receiver_step(hass, elsewhere)

    assert result["step_id"] == "receiver_url"
    assert _suggested(result, CONF_AIRCRAFT_URL) == candidates[0]


async def test_receiver_only_already_configured(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that the same bare receiver cannot be added twice."""
    mock_receiver_entry.add_to_hass(hass)

    result = await _choose(hass, "receiver")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_a_receiver_only_station(
    hass: HomeAssistant,
    mock_receiver_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test moving a bare receiver to a new address.

    A decoder has no identity of its own to check a new address against, so
    unlike a feeder it is simply allowed to move.
    """
    assert await setup_integration(hass, mock_receiver_entry)

    result = await mock_receiver_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "receiver"
    assert _suggested(result, CONF_HOST) == MOCK_HOST

    new_host = "192.168.5.8"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )
    assert result["step_id"] == "receiver_url"
    # The configured URL is kept instead of probing the new address
    assert _suggested(result, CONF_AIRCRAFT_URL) == AIRCRAFT_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: AIRCRAFT_URL}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_receiver_entry.data[CONF_HOST] == new_host
    assert mock_receiver_entry.data[CONF_PORT] is None
    # The device keeps the identity it was created with
    assert mock_receiver_entry.unique_id == RECEIVER_UNIQUE_ID


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test changing the update interval and the nearby radius."""
    assert await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 45, CONF_PROXIMITY_RADIUS: 25}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_SCAN_INTERVAL: 45,
        CONF_PROXIMITY_RADIUS: 25,
        # Nothing asked for a route, so nothing looks one up.
        CONF_ROUTE_SOURCE: ROUTE_SOURCE_NONE,
    }
    # The coordinator works in metres
    assert mock_config_entry.runtime_data.proximity_radius == 25_000
    assert mock_config_entry.runtime_data.route_lookup is None


async def test_options_flow_turns_route_lookups_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that picking a source gives the coordinator one to ask."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.route_lookup is None

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 15,
            CONF_PROXIMITY_RADIUS: 10,
            CONF_ROUTE_SOURCE: ROUTE_SOURCE_ADSBDB,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    lookup = mock_config_entry.runtime_data.route_lookup
    assert isinstance(lookup, AdsbdbLookup)
