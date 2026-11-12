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
    FEEDER_URL,
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    assert result["step_id"] == "search"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f" {MOCK_HOST} "}
    )


def _offered(result: dict[str, Any]) -> list[str]:
    [field] = result["data_schema"].schema.values()
    return [option["label"] for option in field.config["options"]]


async def test_search_then_pick_one(
    hass: HomeAssistant, serving: dict[str, Any]
) -> None:
    """Test the whole flow, ending in the feeder that was picked."""
    serving[FEEDER_URL] = MOCK_MONITOR
    serving[PIAWARE_ON_80] = MOCK_PIAWARE

    result = await _search(hass)
    assert result["step_id"] == "found"
    assert _offered(result) == [
        f"fr24feed ({MOCK_HOST}:8754)",
        f"PiAware ({MOCK_HOST}:80)",
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"feeder": f"{FEEDER_PIAWARE}:80"}
    )
    assert result["step_id"] == "aircraft"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AIRCRAFT_URL: ""}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == 80
    assert result["data"][CONF_FEEDER_TYPE] == FEEDER_PIAWARE
    assert result["result"].unique_id == f"{FEEDER_PIAWARE}:{MOCK_HOST}:80"


async def test_a_feeder_already_set_up_is_not_offered(
    hass: HomeAssistant,
    serving: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the fr24feed entry, known by its alias, is left out."""
    assert mock_config_entry.unique_id == MOCK_ALIAS
    mock_config_entry.add_to_hass(hass)
    serving[FEEDER_URL] = MOCK_MONITOR
    serving[PIAWARE_URL] = MOCK_PIAWARE

    result = await _search(hass)
    assert _offered(result) == [f"PiAware ({MOCK_HOST}:8080)"]


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
