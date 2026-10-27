"""The dashboard card, served by the integration and loaded on every dashboard.

A custom card is normally a file you download and add as a dashboard
resource by hand, and update by hand. This one ships inside the integration,
so it comes and updates with it through HACS, and Home Assistant is told to
load it on every dashboard. After an update and a restart it is in the card
picker as ADS-B Station; there is nothing else to do.

The version goes on the end of the address, so a browser holding the old one
in its cache asks for the new one after an update rather than showing it.
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
    """Serve the card and have every dashboard load it.

    Only where there is a frontend to load it into. Both are after
    dependencies, so they are set up first wherever they are set up at all,
    and a Home Assistant without them simply has no card.
    """
    if hass.http is None or "frontend" not in hass.config.components:
        return
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
