"""The units aircraft figures are given in: nautical, metric or imperial.

Inside the integration everything stays as aircraft.json has it, feet, knots
and kilometres; figures are converted on their way out, in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.const import UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import DistanceConverter, SpeedConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

UNITS_AUTO: Final = "auto"
UNITS_NAUTICAL: Final = "nautical"
UNITS_METRIC: Final = "metric"
UNITS_IMPERIAL: Final = "imperial"
UNIT_CHOICES: Final = [UNITS_AUTO, UNITS_NAUTICAL, UNITS_METRIC, UNITS_IMPERIAL]

# Feet per minute to metres per second.
_FPM_TO_MPS: Final = 0.00508


@dataclass(frozen=True, kw_only=True)
class Units:
    """One system: what a height, a speed and a distance are given in."""

    system: str
    altitude: str
    speed: str
    distance: str
    # Climb and descent: feet a minute, or metres a second.
    rate: str


SYSTEMS: Final = {
    UNITS_NAUTICAL: Units(
        system=UNITS_NAUTICAL,
        altitude=UnitOfLength.FEET,
        speed=UnitOfSpeed.KNOTS,
        distance=UnitOfLength.NAUTICAL_MILES,
        rate="ft/min",
    ),
    UNITS_METRIC: Units(
        system=UNITS_METRIC,
        altitude=UnitOfLength.METERS,
        speed=UnitOfSpeed.KILOMETERS_PER_HOUR,
        distance=UnitOfLength.KILOMETERS,
        rate="m/s",
    ),
    UNITS_IMPERIAL: Units(
        system=UNITS_IMPERIAL,
        altitude=UnitOfLength.FEET,
        speed=UnitOfSpeed.MILES_PER_HOUR,
        distance=UnitOfLength.MILES,
        rate="ft/min",
    ),
}


def units_of(hass: HomeAssistant, choice: str | None) -> Units:
    """Return the chosen system, or Home Assistant's own: imperial or metric."""
    if choice in SYSTEMS:
        return SYSTEMS[choice]
    return SYSTEMS[
        UNITS_IMPERIAL if hass.config.units is US_CUSTOMARY_SYSTEM else UNITS_METRIC
    ]


def _number(value: Any, digits: int, convert: Any) -> Any:
    """Return a figure converted and rounded, anything else as it came."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return value
    result = round(convert(float(value)), digits)
    return int(result) if digits == 0 else result


def converted(value: Any, units: Units) -> Any:
    """Return attributes with every height, speed and distance in these units.

    Through nested lists and dicts, so a list of aircraft is converted too.
    """
    if isinstance(value, list):
        return [converted(item, units) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        if key == "altitude":
            out[key] = _number(
                item,
                0,
                lambda feet: DistanceConverter.convert(
                    feet, UnitOfLength.FEET, units.altitude
                ),
            )
        elif key == "speed":
            out[key] = _number(
                item,
                0,
                lambda knots: SpeedConverter.convert(
                    knots, UnitOfSpeed.KNOTS, units.speed
                ),
            )
        elif key == "vertical_rate":
            out[key] = _number(
                item,
                1 if units.rate == "m/s" else 0,
                lambda fpm: fpm * _FPM_TO_MPS if units.rate == "m/s" else fpm,
            )
        elif key in (
            "distance",
            "slant_distance",
            "closest_passing_distance",
            "radius",
        ):
            out[key] = _number(
                item,
                1,
                lambda km: DistanceConverter.convert(
                    km, UnitOfLength.KILOMETERS, units.distance
                ),
            )
        else:
            out[key] = converted(item, units)
    return out


def unit_attributes(units: Units) -> dict[str, str]:
    """Return what the figures beside them are in, for templates to name."""
    return {
        "altitude_unit": str(units.altitude),
        "speed_unit": str(units.speed),
        "distance_unit": str(units.distance),
        "vertical_rate_unit": units.rate,
    }


# What a person reads beside a number they type, rather than Home Assistant's
# unit name: "NM" where it says "nmi".
LABELS: Final[dict[str, str]] = {UnitOfLength.NAUTICAL_MILES.value: "NM"}


def label_of(unit: str) -> str:
    """Return how a unit is written beside a number to fill in."""
    return LABELS.get(str(unit), str(unit))


def kilometres_in(km: float, units: Units) -> float:
    """Return a distance kept in kilometres, in these units."""
    return DistanceConverter.convert(km, UnitOfLength.KILOMETERS, units.distance)


def kilometres_from(value: float, units: Units) -> float:
    """Return a distance given in these units, in kilometres."""
    return DistanceConverter.convert(value, units.distance, UnitOfLength.KILOMETERS)


def feet_in(feet: float, units: Units) -> float:
    """Return a height kept in feet, in these units."""
    return DistanceConverter.convert(feet, UnitOfLength.FEET, units.altitude)


def feet_from(value: float, units: Units) -> float:
    """Return a height given in these units, in feet."""
    return DistanceConverter.convert(value, units.altitude, UnitOfLength.FEET)
