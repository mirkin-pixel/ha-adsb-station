"""Tests for serving the dashboard card."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from custom_components.adsb_station.card import (
    CARD_FILE,
    CARD_URL,
    async_register_card,
)

MANIFEST = Path(CARD_FILE).parent.parent / "manifest.json"


async def test_the_card_is_served_and_loaded(hass: HomeAssistant) -> None:
    """Test that every dashboard is told to load the card, at this version."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.config.components.add("frontend")
    hass.data[DATA_EXTRA_MODULE_URL] = MagicMock()

    await async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once_with(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    # The version on the end, so an update is not answered from a cache.
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    hass.data[DATA_EXTRA_MODULE_URL].add.assert_called_once_with(
        f"{CARD_URL}?v={version}"
    )


async def test_no_card_without_a_frontend(hass: HomeAssistant) -> None:
    """Test that a Home Assistant without a frontend is simply left alone."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    await async_register_card(hass)

    hass.http.async_register_static_paths.assert_not_awaited()


def test_the_card_ships_inside_the_integration() -> None:
    """Test that the file is where the zip HACS installs is built from."""
    assert CARD_FILE.is_file()
    assert CARD_FILE.parent.parent.name == "adsb_station"
    # The element it defines, which is what a dashboard asks for by name.
    assert 'const CARD = "adsb-station-card"' in CARD_FILE.read_text(encoding="utf-8")
