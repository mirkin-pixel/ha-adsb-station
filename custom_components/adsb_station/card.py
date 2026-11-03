"""Serve the dashboard card and load it on every dashboard.

Shipping it inside the integration means it installs and updates with it,
with no dashboard resource to add by hand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_URL: Final = f"/{DOMAIN}/adsb-station-card.js"
CARD_FILE: Final = Path(__file__).parent / "frontend" / "adsb-station-card.js"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and have every dashboard load it, if there is a frontend."""
    if hass.http is None or "frontend" not in hass.config.components:
        return
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    # The version in the address makes browsers fetch the new card after an
    # update instead of using their cached copy.
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
