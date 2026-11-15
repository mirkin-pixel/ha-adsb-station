"""Repairs: the units of an upgraded station, and units set on a sensor by hand."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .config_flow import UNITS_FIELD
from .const import CONF_UNITS, ISSUE_SET_BY_HAND, ISSUE_UNITS
from .units import (
    UNITS_AUTO,
    label_of,
    let_follow,
    set_by_hand,
    set_by_hand_lines,
    units_of,
)

# As in the config flow: probatio under the name voluptuous since 2026.10.
if TYPE_CHECKING:
    # Missing from 2025.7; only the type checker reads it.
    from homeassistant.components.repairs import RepairsFlowResult
    import probatio as vol
else:
    import voluptuous as vol


def units_placeholders(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str]:
    """Return the station and the units it gives its figures in, for the texts."""
    units = units_of(hass, entry.options.get(CONF_UNITS))
    return {
        "station": entry.title,
        "units": f"{units.altitude}, {units.speed}, {label_of(units.distance)}",
    }


def units_issue_id(entry_id: str) -> str:
    """Return the issue that asks an upgraded station to pick its units."""
    return f"{ISSUE_UNITS}_{entry_id}"


def set_by_hand_issue_id(entry_id: str) -> str:
    """Return the issue that offers to let sensors set by hand follow again."""
    return f"{ISSUE_SET_BY_HAND}_{entry_id}"


def set_by_hand_placeholders(
    entry: ConfigEntry, sensors: list[er.RegistryEntry]
) -> dict[str, str]:
    """Return the station and a line per sensor with the unit it was given."""
    return {"station": entry.title, "sensors": set_by_hand_lines(sensors)}


class UnitsRepairFlow(RepairsFlow):
    """Pick the units right there, Aviation keeping feet and knots."""

    def __init__(self, entry_id: str) -> None:
        """Remember which station the issue is about."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Go to the choice; what arrives here is the issue, not an answer."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show the choice, and save it as Configure would."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="station_removed")
        if user_input is not None:
            options = {
                key: value for key, value in entry.options.items() if key != CONF_UNITS
            }
            if (units := user_input[CONF_UNITS]) != UNITS_AUTO:
                options[CONF_UNITS] = units
            self.hass.config_entries.async_update_entry(entry, options=options)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(UNITS_FIELD),
                {CONF_UNITS: entry.options.get(CONF_UNITS, UNITS_AUTO)},
            ),
            description_placeholders=units_placeholders(self.hass, entry),
        )


class SetByHandRepairFlow(RepairsFlow):
    """Let sensors with a unit of their own follow the setting again."""

    def __init__(self, entry_id: str) -> None:
        """Remember which station the issue is about."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Go to the question; what arrives here is the issue, not an answer."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Name the sensors, and clear their own unit once confirmed."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="station_removed")
        sensors = set_by_hand(self.hass, self._entry_id)
        if user_input is not None:
            let_follow(self.hass, sensors)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=set_by_hand_placeholders(entry, sensors),
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Return the flow that fixes one of this integration's issues."""
    entry_id = str((data or {})["entry_id"])
    if issue_id.startswith(ISSUE_SET_BY_HAND):
        return SetByHandRepairFlow(entry_id)
    return UnitsRepairFlow(entry_id)
