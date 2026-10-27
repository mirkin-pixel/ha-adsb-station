"""What an aircraft looks like.

Nothing an aircraft broadcasts says this either, so like a route it is
something to be asked for, and it stays off until you switch it on. The source
is Planespotters.net, which keeps a photo of most airframes that fly and
answers by the ICAO address every aircraft broadcasts, so it works whether or
not your decoder has an aircraft database.

The photos are someone's work, and Planespotters lends them out on terms:
whoever shows one names the photographer next to it and makes the photo lead
back to its page. That is why this hands a dashboard the photo, the link and
the name as three attributes and never sets one as an entity picture. Home
Assistant shows an entity picture as a small round avatar with neither, and
there is no way to put them back.

The image itself is never fetched here. The terms ask for it to be loaded by
whatever shows it, straight from the address the API gave, so all this keeps
is that address.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import logging
import re
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .const import (
    PHOTO_CACHE_MAX_ENTRIES,
    PHOTO_CACHE_TTL,
    PHOTO_MAX_LOOKUPS_PER_POLL,
    PHOTO_URL,
    PHOTO_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

# A photo is a courtesy from someone else's server and never worth holding up
# a poll for, so it gets as little patience as a route does.
TIMEOUT = 8

# An ICAO address, as the database is keyed on. readsb marks an address that is
# not one, such as a TIS-B track, with a leading tilde, and a photo looked up by
# one of those would be of whichever airframe the number happens to belong to.
_ICAO_ADDRESS = re.compile(r"[0-9a-f]{6}")


@dataclass(frozen=True, kw_only=True)
class AircraftPhoto:
    """A photo of one airframe, and who to thank for it."""

    # The address of the image, to be loaded by whatever shows it.
    src: str
    # The page of the photo on Planespotters.net, which is where it must lead.
    link: str
    photographer: str


@dataclass(frozen=True, kw_only=True)
class _CachedPhoto:
    """What we last learned about an address, and until when to believe it."""

    photo: AircraftPhoto | None
    expires: datetime


def _text(value: Any) -> str | None:
    """Return a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def photographable(hex_code: str) -> bool:
    """Return whether an address is one a photo can be looked up by."""
    return _ICAO_ADDRESS.fullmatch(hex_code.lower()) is not None


class PhotoLookup:
    """Resolves ICAO addresses to photos, remembering what it has been told."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the lookup."""
        self._session = session
        self._cache: dict[str, _CachedPhoto] = {}

    async def async_resolve(self, hex_codes: Iterable[str]) -> dict[str, AircraftPhoto]:
        """Return the photo of every address we know, asking about a few more.

        Never raises: a photo is a nicety, and losing it must not cost you the
        aircraft entities that do come off your own receiver.
        """
        now = dt_util.utcnow()
        self._drop_expired(now)

        known: dict[str, AircraftPhoto] = {}
        pending: list[str] = []
        for hex_code in dict.fromkeys(code.lower() for code in hex_codes):
            if not photographable(hex_code):
                continue
            if (cached := self._cache.get(hex_code)) is not None:
                if cached.photo is not None:
                    known[hex_code] = cached.photo
            else:
                pending.append(hex_code)

        # One request per aircraft, unlike a route, so the ceiling is lower:
        # the rest are still unknown on the next poll, a few seconds later.
        for hex_code in pending[:PHOTO_MAX_LOOKUPS_PER_POLL]:
            try:
                photo = await self._async_fetch(hex_code)
            except (TimeoutError, aiohttp.ClientError, ValueError) as err:
                # Nothing is cached on a failure, so a later poll tries again.
                # The rest wait too: a source that just failed one request is
                # not one to send the next to straight away.
                _LOGGER.debug("Could not reach Planespotters for a photo: %s", err)
                break
            self._remember(hex_code, photo, now)
            if photo is not None:
                known[hex_code] = photo
        return known

    def _drop_expired(self, now: datetime) -> None:
        """Forget what we are no longer entitled to believe."""
        for hex_code in [
            hex_code
            for hex_code, cached in self._cache.items()
            if cached.expires <= now
        ]:
            del self._cache[hex_code]

    def _remember(
        self, hex_code: str, photo: AircraftPhoto | None, now: datetime
    ) -> None:
        """Hold on to an answer, including the answer that there is none."""
        while len(self._cache) >= PHOTO_CACHE_MAX_ENTRIES:
            # Insertion order, so this is the answer we have held longest.
            del self._cache[next(iter(self._cache))]
        self._cache[hex_code] = _CachedPhoto(photo=photo, expires=now + PHOTO_CACHE_TTL)

    async def _async_fetch(self, hex_code: str) -> AircraftPhoto | None:
        """Ask about one address."""
        async with asyncio.timeout(TIMEOUT):
            response = await self._session.get(
                PHOTO_URL.format(hex=hex_code),
                headers={"User-Agent": PHOTO_USER_AGENT},
            )
            response.raise_for_status()
            payload = await response.json(content_type=None)

        if not isinstance(payload, dict):
            _LOGGER.debug(
                "Planespotters answered with %s rather than an object", type(payload)
            )
            return None
        photos = payload.get("photos")
        if not isinstance(photos, list) or not photos:
            return None
        return _planespotters_photo(photos[0])


def _planespotters_photo(item: Any) -> AircraftPhoto | None:
    """Read the photo out of an answer, or None if it cannot be shown properly.

    A photo with no page to lead back to, or no name to put beside it, is one
    the terms do not let us show, so it is as good as none.
    """
    if not isinstance(item, dict):
        return None
    src = None
    # The larger of the two is 280 pixels high, which is what a card wants; the
    # small one is for a list.
    for size in ("thumbnail_large", "thumbnail"):
        thumbnail = item.get(size)
        if isinstance(thumbnail, dict) and (src := _text(thumbnail.get("src"))):
            break
    link = _text(item.get("link"))
    photographer = _text(item.get("photographer"))
    if src is None or link is None or photographer is None:
        return None
    return AircraftPhoto(src=src, link=link, photographer=photographer)


def build_photo_lookup(
    session: aiohttp.ClientSession, enabled: bool
) -> PhotoLookup | None:
    """Return a lookup, or None when photos are switched off."""
    return PhotoLookup(session) if enabled else None


def photo_attributes(photo: AircraftPhoto | None) -> dict[str, Any]:
    """Describe a photo for the attributes of an aircraft.

    All three or none: a photo without its credit and its link is not one a
    dashboard may show.
    """
    if photo is None:
        return {}
    return {
        "photo": photo.src,
        "photo_link": photo.link,
        "photographer": photo.photographer,
    }
