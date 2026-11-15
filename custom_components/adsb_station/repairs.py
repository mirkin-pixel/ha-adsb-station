"""Repairs: the units an upgraded station now gives its figures in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .config_flow import UNITS_FIELD
from .const import CONF_UNITS
from .units import UNITS_AUTO, label_of, units_of

# As in the config flow: probatio under the name voluptuous since 2026.10.
if TYPE_CHECKING:
    # Missing from 2025.7; only the type checker reads it.
    from homeassistant.components.repairs import RepairsFlowResult
    import probatio as vol
else:
    import voluptuous as vol

ISSUE_UNITS = "units_changed"


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


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Return the flow that fixes one of this integration's issues."""
    return UnitsRepairFlow(str((data or {})["entry_id"]))
