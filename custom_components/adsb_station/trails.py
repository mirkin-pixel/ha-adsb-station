"""Where each aircraft has been in the last few minutes, for the card's trails.

Kept here rather than in the card, so a card that opens draws them at once.
Only in memory: the recorder would otherwise store the whole sky every poll.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import AircraftSummary

TRAIL_SECONDS = 300

# About a metre, finer than any reported position, and short on the websocket.
_DECIMALS = 5

# latitude, longitude, altitude in feet or None on the ground, seconds since
# the epoch.
Point = tuple[float, float, float | None, float]


class SkyTrails:
    """The recent positions of every aircraft heard, by hex code."""

    def __init__(self) -> None:
        """Start with no trails at all."""
        self._points: dict[str, list[Point]] = {}

    def follow(self, heard: Iterable[AircraftSummary], now: float) -> None:
        """Add where every aircraft is now, and forget what is too old.

        A point is only added when the aircraft moved. An aircraft no longer
        heard with a position loses its trail, or the card would draw a line
        with no aircraft at the end of it.
        """
        placed: set[str] = set()
        for summary in heard:
            if summary.position is None:
                continue
            placed.add(summary.hex)
            latitude, longitude = summary.position
            point: Point = (
                round(latitude, _DECIMALS),
                round(longitude, _DECIMALS),
                None if summary.on_ground else summary.altitude,
                round(now, 1),
            )
            trail = self._points.setdefault(summary.hex, [])
            if not trail or trail[-1][:2] != point[:2]:
                trail.append(point)

        oldest = now - TRAIL_SECONDS
        for hex_code in list(self._points):
            trail = [point for point in self._points[hex_code] if point[3] >= oldest]
            if trail and hex_code in placed:
                self._points[hex_code] = trail
            else:
                del self._points[hex_code]

    def as_dict(self) -> dict[str, list[Point]]:
        """Return every trail, oldest point first."""
        return {hex_code: list(trail) for hex_code, trail in self._points.items()}
