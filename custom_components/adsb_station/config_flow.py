"""Config flow for the ADS-B Station integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    AdsbStationClient,
    AdsbStationConnectionError,
    AdsbStationError,
    async_detect_aircraft_url,
    async_detect_statistics,
)
from .const import (
    CONF_AIRCRAFT_URL,
    CONF_PROXIMITY_RADIUS,
    CONF_RECEIVER_FEATURES,
    CONF_STATS_URL,
    DEFAULT_FEEDER_NAME,
    DEFAULT_PORT,
    DEFAULT_PROXIMITY_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATION_NAME,
    DOMAIN,
    MAX_PROXIMITY_RADIUS,
    MAX_SCAN_INTERVAL,
    MIN_PROXIMITY_RADIUS,
    MIN_SCAN_INTERVAL,
)
from .coordinator import AdsbStationConfigEntry

_LOGGER = logging.getLogger(__name__)

# Identifies an entry that has no feeder of its own. A station with fr24feed is
# known by its feed alias; a bare decoder has nothing comparable, so the address
# it was set up on is the best we can do.
RECEIVER_UNIQUE_ID_PREFIX = "receiver:"

FEEDER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)

RECEIVER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): selector.TextSelector()})

_AIRCRAFT_URL_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
)

# Alongside a feeder the receiver is a bonus and may be skipped; on its own it
# is the only source of data, so there is nothing to set up without it.
OPTIONAL_AIRCRAFT_SCHEMA = vol.Schema(
    {vol.Optional(CONF_AIRCRAFT_URL, default=""): _AIRCRAFT_URL_SELECTOR}
)
REQUIRED_AIRCRAFT_SCHEMA = vol.Schema(
    {vol.Required(CONF_AIRCRAFT_URL, default=""): _AIRCRAFT_URL_SELECTOR}
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                max=MAX_SCAN_INTERVAL,
                step=1,
                unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_PROXIMITY_RADIUS, default=DEFAULT_PROXIMITY_RADIUS
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_PROXIMITY_RADIUS,
                max=MAX_PROXIMITY_RADIUS,
                step=1,
                unit_of_measurement="km",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }
)


class AdsbStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an ADS-B station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host = ""
        self._port: int | None = None
        self._title = DEFAULT_STATION_NAME
        self._aircraft_url = ""
        self._stats_url: str | None = None
        self._features: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask whether this station runs fr24feed."""
        return self.async_show_menu(step_id="user", menu_options=["feeder", "receiver"])

    async def async_step_feeder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address of the fr24feed status server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            monitor, error = await self._async_validate_feeder(host, port)
            if error is None:
                alias = str(monitor.get("feed_alias") or "").strip()
                await self.async_set_unique_id(alias or f"{host}:{port}")
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch(reason="wrong_feeder")
                else:
                    self._abort_if_unique_id_configured()
                self._host = host
                self._port = port
                self._title = alias or f"{DEFAULT_FEEDER_NAME} ({host})"
                return await self.async_step_aircraft()
            errors["base"] = error

        return self.async_show_form(
            step_id="feeder",
            data_schema=self.add_suggested_values_to_schema(
                FEEDER_SCHEMA, user_input or self._feeder_defaults()
            ),
            errors=errors,
        )

    async def async_step_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address of a station that runs no fr24feed."""
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            self._host = host
            self._port = None
            if self.source == SOURCE_RECONFIGURE:
                # A bare decoder has no identity to compare a new address
                # against, so keep the one the entry already has and let it move.
                await self.async_set_unique_id(self._get_reconfigure_entry().unique_id)
            else:
                await self.async_set_unique_id(f"{RECEIVER_UNIQUE_ID_PREFIX}{host}")
                self._abort_if_unique_id_configured()
            self._title = f"{DEFAULT_STATION_NAME} ({host})"
            return await self.async_step_receiver_url()

        return self.async_show_form(
            step_id="receiver",
            data_schema=self.add_suggested_values_to_schema(
                RECEIVER_SCHEMA, self._receiver_defaults()
            ),
        )

    async def async_step_aircraft(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the aircraft.json URL to read next to a feeder."""
        return await self._async_aircraft_step("aircraft", user_input, required=False)

    async def async_step_receiver_url(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the aircraft.json URL of a station without a feeder."""
        return await self._async_aircraft_step(
            "receiver_url", user_input, required=True
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an already configured station."""
        if self._get_reconfigure_entry().data.get(CONF_PORT) is None:
            return await self.async_step_receiver(user_input)
        return await self.async_step_feeder(user_input)

    async def _async_aircraft_step(
        self, step_id: str, user_input: dict[str, Any] | None, *, required: bool
    ) -> ConfigFlowResult:
        """Run one of the two aircraft.json steps."""
        errors: dict[str, str] = {}
        if user_input is None:
            self._aircraft_url = await self._async_suggest_aircraft_url()
        else:
            self._aircraft_url = str(user_input.get(CONF_AIRCRAFT_URL) or "").strip()
            if not self._aircraft_url:
                if not required:
                    return self._async_finish(None)
                errors["base"] = "aircraft_url_required"
            elif (
                error := await self._async_validate_aircraft(self._aircraft_url)
            ) is None:
                return self._async_finish(self._aircraft_url)
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                REQUIRED_AIRCRAFT_SCHEMA if required else OPTIONAL_AIRCRAFT_SCHEMA,
                {CONF_AIRCRAFT_URL: self._aircraft_url},
            ),
            errors=errors,
        )

    def _feeder_defaults(self) -> dict[str, Any]:
        """Return the values to prefill the feeder step with."""
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
            }
        return {CONF_PORT: DEFAULT_PORT}

    def _receiver_defaults(self) -> dict[str, Any]:
        """Return the values to prefill the receiver step with."""
        if self.source == SOURCE_RECONFIGURE:
            return {CONF_HOST: self._get_reconfigure_entry().data[CONF_HOST]}
        return {}

    async def _async_suggest_aircraft_url(self) -> str:
        """Return the current URL, or probe the receiver for one."""
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_entry().data.get(CONF_AIRCRAFT_URL)
            if current:
                return str(current)
        detected = await async_detect_aircraft_url(
            async_get_clientsession(self.hass), self._host
        )
        return detected or ""

    async def _async_validate_feeder(
        self, host: str, port: int
    ) -> tuple[dict[str, Any], str | None]:
        """Read monitor.json. Returns the payload and an error key."""
        client = AdsbStationClient(async_get_clientsession(self.hass), host, port)
        try:
            return await client.async_get_monitor(), None
        except AdsbStationConnectionError:
            return {}, "cannot_connect"
        except AdsbStationError:
            return {}, "invalid_response"
        except Exception:
            _LOGGER.exception("Unexpected error while reading monitor.json")
            return {}, "unknown"

    async def _async_validate_aircraft(self, url: str) -> str | None:
        """Read aircraft.json. Returns an error key, or None."""
        client = AdsbStationClient(
            async_get_clientsession(self.hass), self._host, self._port, url
        )
        try:
            await client.async_get_aircraft()
        except AdsbStationConnectionError:
            return "cannot_connect_aircraft"
        except AdsbStationError:
            return "invalid_aircraft_response"
        except Exception:
            _LOGGER.exception("Unexpected error while reading aircraft.json")
            return "unknown"

        # Not every decoder serves statistics; the fr24feed fork does, older
        # builds do not. Look once, here, so the entities that need it are only
        # created when the receiver can actually feed them.
        self._stats_url, self._features = await async_detect_statistics(
            async_get_clientsession(self.hass), url
        )
        return None

    def _async_finish(self, aircraft_url: str | None) -> ConfigFlowResult:
        """Create or update the config entry."""
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_AIRCRAFT_URL: aircraft_url,
            CONF_STATS_URL: self._stats_url if aircraft_url else None,
            CONF_RECEIVER_FEATURES: self._features if aircraft_url else [],
        }
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return self.async_create_entry(title=self._title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(entry: AdsbStationConfigEntry) -> AdsbStationOptionsFlow:
        """Return the options flow."""
        return AdsbStationOptionsFlow()


class AdsbStationOptionsFlow(OptionsFlow):
    """Handle the options for a configured station."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user change how often the station is polled."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_PROXIMITY_RADIUS: int(user_input[CONF_PROXIMITY_RADIUS]),
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
