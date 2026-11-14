"""Tests for the downloaded aircraft database."""

from __future__ import annotations

import gzip
import os
import time
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.aircraft_db import (
    DATABASE_URL,
    REFRESH,
    _flags,
    database_of,
)
from custom_components.adsb_station.const import CONF_AIRCRAFT_DATABASE

from .conftest import set_responses, setup_integration
from .test_passages import next_poll as _next_poll, poll
from .test_sensor import _attributes

TABLE = gzip.compress(
    b"484123;PH-BXA;B738;0000;BOEING 737-800;2000;KLM ROYAL DUTCH AIRLINES;\n"
    b"43c123;ZZ123;A400;1000;AIRBUS A-400M;;A Person;\n"
    b"000001;;;0000;;;Miscode;\n"
)


async def next_poll(hass: HomeAssistant, freezer: Any) -> None:
    """Poll, and wait for the lookup on disk the poll waits for."""
    await _next_poll(hass, freezer)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture(autouse=True)
def own_config_dir(hass: HomeAssistant, tmp_path: Any) -> None:
    """Keep the downloaded file out of the shared test configuration."""
    hass.config.config_dir = str(tmp_path)


UNNAMED = {
    "hex": "484123",
    "flight": "KLM123",
    "lat": 52.01,
    "lon": 5.0,
    "alt_baro": 2000,
}


@pytest.mark.parametrize(
    ("text", "flags"), [("0000", 0), ("1000", 1), ("0100", 2), ("0011", 12), ("10", 1)]
)
def test_flags(text: str, flags: int) -> None:
    """Test the flags column, a character per bit as readsb reads it."""
    assert _flags(text) == flags


async def _with_table(
    hass: HomeAssistant, entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={CONF_AIRCRAFT_DATABASE: True}
    )
    # After: set_responses starts the mocks over.
    set_responses(aioclient_mock, aircraft=poll(UNNAMED))
    aioclient_mock.get(DATABASE_URL, content=TABLE)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_an_unnamed_aircraft_is_named(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the download, and the next poll naming the aircraft from it."""
    await _with_table(hass, mock_config_entry, aioclient_mock)
    database = database_of(hass)
    assert database.path.exists()

    await next_poll(hass, freezer)
    closest = _attributes(hass, "closest_aircraft")
    assert closest["registration"] == "PH-BXA"
    assert closest["aircraft_type"] == "B738"
    assert closest["description"] == "BOEING 737-800"
    # Only what the decoder would give: the owner is left out of the table.
    found = await hass.async_add_executor_job(database.lookup, ["484123", "43c123"])
    assert found["43c123"]["dbFlags"] == 1
    assert "A Person" not in str(found)


async def test_the_decoder_wins(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an aircraft the decoder names keeps the decoder's name."""
    await _with_table(hass, mock_config_entry, aioclient_mock)
    set_responses(aioclient_mock, aircraft=poll({**UNNAMED, "r": "PH-XXX"}))
    await next_poll(hass, freezer)

    assert _attributes(hass, "closest_aircraft")["registration"] == "PH-XXX"
    assert mock_config_entry.runtime_data.decoder_has_database


async def test_once_a_week_and_a_failure_keeps_the_last(
    hass: HomeAssistant,
    freezer: Any,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a fresh file is not fetched again, nor a stale one lost."""
    await _with_table(hass, mock_config_entry, aioclient_mock)
    database = database_of(hass)

    def downloads() -> int:
        return sum(
            1 for _, url, _, _ in aioclient_mock.mock_calls if str(url) == DATABASE_URL
        )

    await next_poll(hass, freezer)
    assert downloads() == 1

    # A week on, GitHub is down: the old file stays and is still read.
    old = time.time() - REFRESH.total_seconds() - 60
    os.utime(database.path, (old, old))
    database._fresh_until = 0.0
    set_responses(aioclient_mock, aircraft=poll(UNNAMED))
    aioclient_mock.get(DATABASE_URL, exc=ClientError())
    await next_poll(hass, freezer)
    assert downloads() == 1  # the failed one, counted afresh
    assert database.path.exists()
    await next_poll(hass, freezer)
    assert _attributes(hass, "closest_aircraft")["registration"] == "PH-BXA"
    # Nor asked again every poll after failing, only the next day.
    assert downloads() == 1


async def test_offered_only_where_it_helps_and_deleted_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the option in the form, and the file going with the option."""
    set_responses(aioclient_mock, aircraft=poll(UNNAMED))
    assert await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert CONF_AIRCRAFT_DATABASE in result["data_schema"].schema

    mock_config_entry.runtime_data.decoder_has_database = True
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert CONF_AIRCRAFT_DATABASE not in result["data_schema"].schema

    database = database_of(hass)
    await hass.async_add_executor_job(database.path.parent.mkdir)
    await hass.async_add_executor_job(database.path.write_bytes, b"")
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not database.path.exists()
