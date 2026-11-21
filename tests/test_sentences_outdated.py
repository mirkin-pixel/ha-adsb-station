"""Tests for the repair that notices Assist sentences an update left behind."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN, ISSUE_SENTENCES
from custom_components.adsb_station.sentences import (
    SENTENCES_FILE,
    SHIPPED,
    async_check_sentences,
)

from .conftest import setup_integration


def _issues(hass: HomeAssistant) -> list[str]:
    return [
        issue_id
        for domain, issue_id in ir.async_get(hass).issues
        if domain == DOMAIN and issue_id.startswith(ISSUE_SENTENCES)
    ]


def _copy(tmp_path: Path, text: str) -> Path:
    """Put a copy of the English sentences where Home Assistant reads them."""
    copy = tmp_path / "custom_sentences" / "en" / SENTENCES_FILE
    copy.parent.mkdir(parents=True)
    copy.write_text(text, "utf-8")
    return copy


def _shipped() -> str:
    return (SHIPPED / "en" / SENTENCES_FILE).read_text("utf-8")


async def test_no_copy_is_nothing_to_update(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that a station without the files copied hears nothing about them."""
    hass.config.config_dir = str(tmp_path)

    await async_check_sentences(hass)

    assert _issues(hass) == []


async def test_a_current_copy_is_left_alone(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that a copy as shipped raises nothing."""
    hass.config.config_dir = str(tmp_path)
    _copy(tmp_path, _shipped())

    await async_check_sentences(hass)

    assert _issues(hass) == []


async def test_an_old_copy_is_copied_again_from_the_repair(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test the repair for an old copy: copied, read again by Assist, gone."""
    hass.config.config_dir = str(tmp_path)
    copy = _copy(tmp_path, "language: en\nintents: {}\n")
    reloads: list[ServiceCall] = []
    hass.services.async_register("conversation", "reload", reloads.append)

    # Loading the integration is what checks, at every start
    assert await async_setup_component(hass, DOMAIN, {})
    [issue_id] = _issues(hass)

    assert await async_setup_component(hass, "repairs", {})
    flows = hass.data["repairs"]["flow_manager"]
    result = await flows.async_init(DOMAIN, data={"issue_id": issue_id})
    assert result["type"] is FlowResultType.MENU
    result = await flows.async_configure(result["flow_id"], {"next_step_id": "update"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert copy.read_text("utf-8") == _shipped()
    assert len(reloads) == 1
    assert _issues(hass) == []


async def test_a_copy_kept_on_purpose_is_asked_about_once(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that keeping the copy ignores the issue, and leaves the copy be."""
    hass.config.config_dir = str(tmp_path)
    copy = _copy(tmp_path, "language: en\nintents: {}\n")
    # Loading the integration is what checks, at every start
    assert await async_setup_component(hass, DOMAIN, {})
    [issue_id] = _issues(hass)

    assert await async_setup_component(hass, "repairs", {})
    flows = hass.data["repairs"]["flow_manager"]
    result = await flows.async_init(DOMAIN, data={"issue_id": issue_id})
    result = await flows.async_configure(result["flow_id"], {"next_step_id": "keep"})

    assert result["type"] is FlowResultType.ABORT
    assert copy.read_text("utf-8") == "language: en\nintents: {}\n"
    # Still there, but ignored, and so it stays on the next start
    await async_check_sentences(hass)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.dismissed_version is not None


async def test_an_old_issue_goes_with_the_version(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that an issue about sentences since changed again is replaced."""
    hass.config.config_dir = str(tmp_path)
    _copy(tmp_path, "language: en\nintents: {}\n")
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_SENTENCES}_older",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_SENTENCES,
    )

    await async_check_sentences(hass)

    [issue_id] = _issues(hass)
    assert issue_id != f"{ISSUE_SENTENCES}_older"


async def test_the_last_station_takes_an_unchanged_copy_along(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that removing the last station deletes a copy as shipped."""
    hass.config.config_dir = str(tmp_path)
    copy = _copy(tmp_path, _shipped())
    assert await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)

    assert not copy.exists()
    assert not copy.parent.exists()


async def test_a_copy_changed_by_hand_stays(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that a copy changed by hand is the user's, and is left."""
    hass.config.config_dir = str(tmp_path)
    changed = _copy(tmp_path, "language: en\nintents: {}\n")
    assert await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)

    assert changed.exists()


async def test_a_copy_stays_while_a_station_is_left(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
) -> None:
    """Test that removing one of two stations leaves the sentences in place."""
    hass.config.config_dir = str(tmp_path)
    copy = _copy(tmp_path, _shipped())
    MockConfigEntry(domain=DOMAIN, title="Another", data={}).add_to_hass(hass)
    assert await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)

    assert copy.exists()
