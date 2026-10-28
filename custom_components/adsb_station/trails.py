"""Where each aircraft has been in the last few minutes.

The dashboard card draws a trail behind every aircraft. Kept by the card
itself, a trail would start over every time the card is opened, which on a
phone is every time anyone looks: a dashboard would only ever show a few
seconds of each. Kept here, a card that opens gets the last five minutes at
once.

Only in memory. A restart starts over, and nothing of it reaches the state
machine or the recorder, which would write the whole sky to the database on
every poll.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import AircraftSummary

TRAIL_SECONDS = 300

# Five decimals is about a metre, which is closer than any position an
# aircraft reports, and keeps what goes over the websocket short.
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

        A point is only added when the aircraft moved: a poll that read the
        same position twice, or kept the last read, adds nothing.
        """
        for summary in heard:
            if summary.position is None:
                continue
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
            if trail:
                self._points[hex_code] = trail
            else:
                del self._points[hex_code]

    def as_dict(self) -> dict[str, list[Point]]:
        """Return every trail, oldest point first."""
        return {hex_code: list(trail) for hex_code, trail in self._points.items()}
