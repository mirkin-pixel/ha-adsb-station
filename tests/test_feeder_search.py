"""Tests for searching a host for every kind of feeder at once."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adsb_station.api import (
    AdsbStationConnectionError,
    async_detect_feeders,
)
from custom_components.adsb_station.const import (
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    DOMAIN,
    FEEDER_FR24,
    FEEDER_PIAWARE,
)

from .conftest import (
    AIRCRAFT_URL,
    FEEDER_URL,
    MOCK_AIRCRAFT,
    MOCK_ALIAS,
    MOCK_HOST,
    MOCK_MONITOR,
    MOCK_PIAWARE,
    PIAWARE_URL,
)

# The aiohttp mocker ignores the port, so these are served by URL instead.
PIAWARE_ON_80 = f"http://{MOCK_HOST}:80/status.json"
PIAWARE_ON_8082 = f"http://{MOCK_HOST}:8082/status.json"


@pytest.fixture
def serving() -> Iterator[dict[str, Any]]:
    """Answer exactly the URLs put in the returned dict, and nothing else."""
    documents: dict[str, Any] = {}

    async def fetch(session: Any, url: str, timeout: int = 0) -> Any:
        if url not in documents:
            raise AdsbStationConnectionError(url)
        return documents[url]

    with patch("custom_components.adsb_station.api.async_fetch_json", fetch):
        yield documents


@pytest.fixture
def no_setup() -> Iterator[None]:
    """Create the entries without starting them; only the flow is tested here."""
    with patch("custom_components.adsb_station.async_setup_entry", return_value=True):
        yield


async def _detect(hass: HomeAssistant) -> list[tuple[str, int]]:
    found = await async_detect_feeders(async_get_clientsession(hass), MOCK_HOST)
    return [(key, port) for key, port, _ in found]


async def test_each_feeder_on_its_own_port(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test fr24feed on its port and PiAware where docker-piaware puts it."""
    serving[FEEDER_URL] = MOCK_MONITOR
    serving[PIAWARE_ON_80] = MOCK_PIAWARE

    assert await _detect(hass) == [(FEEDER_FR24, 8754), (FEEDER_PIAWARE, 80)]


async def test_the_usual_port_wins(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test one PiAware reachable on two ports: found once, on its own."""
    serving[PIAWARE_URL] = MOCK_PIAWARE
    serving[PIAWARE_ON_8082] = MOCK_PIAWARE

    assert await _detect(hass) == [(FEEDER_PIAWARE, 8080)]


async def test_another_document_is_no_feeder(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test a status.json that is not PiAware's, and a page that is no JSON."""
    serving[PIAWARE_URL] = {"now": 1.0, "aircraft": []}
    serving[PIAWARE_ON_80] = MOCK_MONITOR
    serving[PIAWARE_ON_8082] = ["not", "a", "status"]

    assert await _detect(hass) == []


async def _search(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f" {MOCK_HOST} "}
    )


async def test_one_address_adds_the_first_and_offers_the_rest(
    no_setup: None, hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test the whole flow: one entry with the decoder, the next one discovered."""
    serving[FEEDER_URL] = MOCK_MONITOR
    serving[PIAWARE_ON_80] = MOCK_PIAWARE
    serving[AIRCRAFT_URL] = MOCK_AIRCRAFT

    result = await _search(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "found"
    assert result["description_placeholders"]["found"] == "\n".join(
        [
            f"- aircraft.json ({AIRCRAFT_URL})",
            f"- fr24feed ({MOCK_HOST}:8754)",
            f"- PiAware ({MOCK_HOST}:80)",
        ]
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FEEDER_TYPE] == FEEDER_FR24
    assert result["data"][CONF_AIRCRAFT_URL] == AIRCRAFT_URL
    assert result["options"] == {}

    # PiAware waits under Discovered, and takes one click, without the decoder
    [offered] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert offered["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    assert offered["context"]["title_placeholders"] == {
        "name": f"PiAware ({MOCK_HOST})"
    }
    result = await hass.config_entries.flow.async_configure(offered["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == 80
    assert result["data"][CONF_FEEDER_TYPE] == FEEDER_PIAWARE
    assert result["data"][CONF_AIRCRAFT_URL] is None
    assert result["result"].unique_id == f"{FEEDER_PIAWARE}:{MOCK_HOST}:80"


async def test_a_decoder_without_feeders_is_added_on_its_own(
    no_setup: None, hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test a station that feeds nowhere: one receiver-only entry."""
    serving[AIRCRAFT_URL] = MOCK_AIRCRAFT

    result = await _search(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FEEDER_TYPE] is None
    assert result["result"].unique_id == f"receiver:{MOCK_HOST}"


async def test_a_feeder_already_set_up_is_not_offered(
    no_setup: None,
    hass: HomeAssistant,
    serving: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the fr24feed entry, and the decoder it reads, are left out."""
    assert mock_config_entry.unique_id == MOCK_ALIAS
    mock_config_entry.add_to_hass(hass)
    serving[FEEDER_URL] = MOCK_MONITOR
    serving[PIAWARE_URL] = MOCK_PIAWARE
    serving[AIRCRAFT_URL] = MOCK_AIRCRAFT

    result = await _search(hass)
    assert result["description_placeholders"]["found"] == (
        f"- PiAware ({MOCK_HOST}:8080)"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add"}
    )
    assert result["data"][CONF_FEEDER_TYPE] == FEEDER_PIAWARE
    assert result["data"][CONF_AIRCRAFT_URL] is None


async def test_choosing_by_hand_after_all(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test the way to the manual steps when something was found."""
    serving[FEEDER_URL] = MOCK_MONITOR

    result = await _search(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"
    assert set(result["menu_options"]) == {
        "fr24feed",
        "piaware",
        "planefinder",
        "receiver",
    }


@pytest.mark.parametrize(
    ("step", "prefilled"),
    [
        (FEEDER_PIAWARE, {CONF_HOST: MOCK_HOST, CONF_PORT: 8080}),
        ("receiver", {CONF_HOST: MOCK_HOST}),
    ],
)
async def test_nothing_found_leaves_the_choice_to_the_user(
    hass: HomeAssistant,
    serving: dict[str, Any],
    step: str,
    prefilled: dict[str, Any],
) -> None:
    """Test the way back to choosing by hand, with the host filled in."""
    result = await _search(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "nothing_found"
    assert result["description_placeholders"] == {"host": MOCK_HOST}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["step_id"] == step
    suggested = {
        str(marker): marker.description["suggested_value"]
        for marker in result["data_schema"].schema
    }
    assert suggested == prefilled


async def test_a_discovered_feeder_gone_since_is_not_offered(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test that a feeder no longer answering is dropped rather than offered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: 8080, CONF_FEEDER_TYPE: FEEDER_PIAWARE},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_a_feeder_gone_before_adding_is_said_so(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test an abort that names the reason when the feeder stops answering."""
    serving[FEEDER_URL] = MOCK_MONITOR
    result = await _search(hass)
    del serving[FEEDER_URL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_a_decoder_gone_before_adding_is_said_so(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test the same for the decoder."""
    serving[AIRCRAFT_URL] = MOCK_AIRCRAFT
    result = await _search(hass)
    del serving[AIRCRAFT_URL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect_aircraft"
