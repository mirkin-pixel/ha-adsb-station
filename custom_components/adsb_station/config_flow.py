"""Config flow for the ADS-B Station integration."""

from __future__ import annotations

import asyncio
import logging
from math import ceil, floor
import socket
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.translation import async_get_translations

# Since 2026.10 Home Assistant runs probatio under the name voluptuous; only
# the type checker needs to be told.
if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from .api import (
    AdsbStationClient,
    AdsbStationConnectionError,
    AdsbStationError,
    async_detect_aircraft_url,
    async_detect_feeders,
    async_detect_statistics,
)
from .const import (
    CONF_AIRCRAFT_DATABASE,
    CONF_AIRCRAFT_URL,
    CONF_FEEDER_TYPE,
    CONF_FOLLOW_UNITS,
    CONF_KEEP_PASSAGES,
    CONF_LOOK_UP_PHOTOS,
    CONF_LOOK_UP_ROUTES,
    CONF_MAP_AIRCRAFT,
    CONF_PROXIMITY_MAX_ALTITUDE,
    CONF_PROXIMITY_RADIUS,
    CONF_RECEIVER_FEATURES,
    CONF_STATISTICS_INTERVAL,
    CONF_STATS_URL,
    CONF_UNITS,
    CONF_WATCHLIST,
    DEFAULT_KEEP_PASSAGES,
    DEFAULT_LOOK_UP_PHOTOS,
    DEFAULT_LOOK_UP_ROUTES,
    DEFAULT_MAP_AIRCRAFT,
    DEFAULT_PROXIMITY_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATION_NAME,
    DEFAULT_STATISTICS_INTERVAL,
    DOMAIN,
    FEEDER_FR24,
    FEEDER_PIAWARE,
    FEEDER_PLANEFINDER,
    FEEDERS,
    ISSUE_SET_BY_HAND,
    MAX_KEEP_PASSAGES,
    MAX_PROXIMITY_ALTITUDE,
    MAX_PROXIMITY_RADIUS,
    MAX_SCAN_INTERVAL,
    MIN_PROXIMITY_RADIUS,
    MIN_SCAN_INTERVAL,
)
from .coordinator import AdsbStationConfigEntry
from .reference import async_load_reference, kind_of
from .units import (
    UNIT_CHOICES,
    UNITS_AUTO,
    Units,
    feet_from,
    feet_in,
    kilometres_from,
    kilometres_in,
    label_of,
    let_follow,
    set_by_hand,
    set_by_hand_lines,
    units_of,
)

_LOGGER = logging.getLogger(__name__)

# A bare decoder has no feed alias, so it is known by its address.
RECEIVER_UNIQUE_ID_PREFIX = "receiver:"


def _feeder_unique_id(
    feeder_type: str, host: str, port: int, payload: dict[str, Any]
) -> str:
    """Return how a feeder is known: fr24feed by its alias, the rest by address."""
    if feeder_type == FEEDER_FR24:
        alias = str(payload.get("feed_alias") or "").strip()
        # Unprefixed, so entries predating the other feeders keep their entities.
        return alias or f"{host}:{port}"
    return f"{feeder_type}:{host}:{port}"


FEEDER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT): selector.NumberSelector(
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
_UNITS_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=UNIT_CHOICES,
        translation_key=CONF_UNITS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)
UNITS_FIELD = {vol.Required(CONF_UNITS, default=UNITS_AUTO): _UNITS_SELECTOR}


_OPTIONS_BEFORE: dict[Any, Any] = {
    **UNITS_FIELD,
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
        CONF_STATISTICS_INTERVAL, default=DEFAULT_STATISTICS_INTERVAL
    ): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            unit_of_measurement="s",
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
}
_OPTIONS_AFTER: dict[Any, Any] = {
    vol.Required(
        CONF_MAP_AIRCRAFT, default=DEFAULT_MAP_AIRCRAFT
    ): selector.BooleanSelector(),
    vol.Required(
        CONF_LOOK_UP_ROUTES, default=DEFAULT_LOOK_UP_ROUTES
    ): selector.BooleanSelector(),
    vol.Required(
        CONF_LOOK_UP_PHOTOS, default=DEFAULT_LOOK_UP_PHOTOS
    ): selector.BooleanSelector(),
    vol.Optional(CONF_WATCHLIST): selector.TextSelector(
        selector.TextSelectorConfig(multiline=True)
    ),
}


def options_schema(units: Units) -> vol.Schema:
    """Return the options, the radius and the ceiling to fill in in these units."""
    return vol.Schema(
        {
            **_OPTIONS_BEFORE,
            vol.Required(
                CONF_PROXIMITY_RADIUS,
                default=round(kilometres_in(DEFAULT_PROXIMITY_RADIUS, units), 1),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    # Outward, so a radius at either end is shown inside them.
                    min=floor(kilometres_in(MIN_PROXIMITY_RADIUS, units) * 10) / 10,
                    max=ceil(kilometres_in(MAX_PROXIMITY_RADIUS, units)),
                    step=0.1,
                    unit_of_measurement=label_of(units.distance),
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_PROXIMITY_MAX_ALTITUDE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=round(feet_in(MAX_PROXIMITY_ALTITUDE, units)),
                    step=1,
                    unit_of_measurement=label_of(units.altitude),
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_KEEP_PASSAGES, default=DEFAULT_KEEP_PASSAGES
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=MAX_KEEP_PASSAGES,
                    step=1,
                    unit_of_measurement="d",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            **_OPTIONS_AFTER,
        }
    )


class AdsbStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for an ADS-B station."""

    VERSION = 5
    MINOR_VERSION = 3

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host = ""
        self._port: int | None = None
        self._feeder_type: str | None = None
        self._title = DEFAULT_STATION_NAME
        self._aircraft_url = ""
        self._stats_url: str | None = None
        self._features: list[str] = []
        # What a search found: the feeders, by kind and port, and the decoder.
        self._found: list[tuple[str, int]] = []
        self._decoder: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address, and look there for the decoder and the feeders."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=RECEIVER_SCHEMA)
        self._host = str(user_input[CONF_HOST]).strip()
        session = async_get_clientsession(self.hass)
        feeders, decoder = await asyncio.gather(
            async_detect_feeders(session, self._host),
            async_detect_aircraft_url(session, self._host),
        )
        configured = self._async_current_ids(include_ignore=False)
        self._found = [
            (key, port)
            for key, port, payload in feeders
            if _feeder_unique_id(key, self._host, port, payload) not in configured
        ]
        # Once per station: a decoder another entry reads would count twice.
        self._decoder = (
            None
            if decoder is None or await self._async_decoder_already_read()
            else decoder
        )
        if not self._found and (
            self._decoder is None
            or f"{RECEIVER_UNIQUE_ID_PREFIX}{self._host}" in configured
        ):
            return await self.async_step_nothing_found()
        return await self.async_step_found()

    async def async_step_nothing_found(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Leave the choice to the user, with the host already filled in."""
        return self.async_show_menu(
            step_id="nothing_found",
            menu_options=[*FEEDERS, "receiver"],
            description_placeholders={"host": self._host},
        )

    async def async_step_found(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Say what was found, and what adding it does."""
        lines = [
            f"- {FEEDERS[key].model} ({self._host}:{port})" for key, port in self._found
        ]
        if self._decoder is not None:
            lines.insert(0, f"- aircraft.json ({self._decoder})")
        first = (
            FEEDERS[self._found[0][0]].model if self._found else DEFAULT_STATION_NAME
        )
        return self.async_show_menu(
            step_id="found",
            menu_options=["add", "manual"],
            description_placeholders={
                "host": self._host,
                "found": "\n".join(lines),
                "first": first,
                "later": ", ".join(FEEDERS[key].model for key, _ in self._found[1:])
                or "-",
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose by hand after all, with the host already filled in."""
        return self.async_show_menu(
            step_id="manual", menu_options=[*FEEDERS, "receiver"]
        )

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the first of what was found; offer the other feeders as discovered."""
        for key, port in self._found[1:]:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: port,
                        CONF_FEEDER_TYPE: key,
                    },
                )
            )
        if self._found:
            key, port = self._found[0]
            payload, error = await self._async_validate_feeder(self._host, port, key)
            if error is not None:
                return self.async_abort(reason=error)
            await self.async_set_unique_id(
                _feeder_unique_id(key, self._host, port, payload)
            )
            self._abort_if_unique_id_configured()
            self._feeder_type, self._port = key, port
            alias = (
                str(payload.get("feed_alias") or "").strip()
                if key == FEEDER_FR24
                else ""
            )
            self._title = alias or f"{FEEDERS[key].default_name} ({self._host})"
        else:
            await self.async_set_unique_id(f"{RECEIVER_UNIQUE_ID_PREFIX}{self._host}")
            self._abort_if_unique_id_configured()
            self._title = f"{DEFAULT_STATION_NAME} ({self._host})"
        if self._decoder is not None and (
            error := await self._async_validate_aircraft(self._decoder)
        ):
            return self.async_abort(reason=error)
        return self._async_finish(self._decoder)

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Offer a feeder found next to one just added, to add with one click."""
        self._host = str(discovery_info[CONF_HOST])
        self._port = int(discovery_info[CONF_PORT])
        self._feeder_type = str(discovery_info[CONF_FEEDER_TYPE])
        payload, error = await self._async_validate_feeder(
            self._host, self._port, self._feeder_type
        )
        if error is not None:
            return self.async_abort(reason=error)
        await self.async_set_unique_id(
            _feeder_unique_id(self._feeder_type, self._host, self._port, payload)
        )
        self._abort_if_unique_id_configured()
        kind = FEEDERS[self._feeder_type]
        alias = (
            str(payload.get("feed_alias") or "").strip()
            if self._feeder_type == FEEDER_FR24
            else ""
        )
        self._title = alias or f"{kind.default_name} ({self._host})"
        self.context["title_placeholders"] = {"name": f"{kind.model} ({self._host})"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the discovered feeder, without a decoder: another entry reads it."""
        if user_input is not None:
            return self._async_finish(None)
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_fr24feed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the Flightradar24 feeder."""
        return await self._async_feeder_step(FEEDER_FR24, user_input)

    async def async_step_piaware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the FlightAware feeder."""
        return await self._async_feeder_step(FEEDER_PIAWARE, user_input)

    async def async_step_planefinder(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the Plane Finder feeder."""
        return await self._async_feeder_step(FEEDER_PLANEFINDER, user_input)

    async def _async_feeder_step(
        self, feeder_type: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Ask for the address of one kind of feeder."""
        kind = FEEDERS[feeder_type]
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            payload, error = await self._async_validate_feeder(host, port, feeder_type)
            if error is None:
                self._feeder_type = feeder_type
                alias = (
                    str(payload.get("feed_alias") or "").strip()
                    if feeder_type == FEEDER_FR24
                    else ""
                )
                await self.async_set_unique_id(
                    _feeder_unique_id(feeder_type, host, port, payload)
                )
                if self.source == SOURCE_RECONFIGURE:
                    if alias:
                        self._abort_if_unique_id_mismatch(reason="wrong_feeder")
                    else:
                        await self.async_set_unique_id(
                            self._get_reconfigure_entry().unique_id
                        )
                else:
                    self._abort_if_unique_id_configured()
                self._host = host
                self._port = port
                self._title = alias or f"{kind.default_name} ({host})"
                return await self.async_step_aircraft()
            errors["base"] = error

        return self.async_show_form(
            step_id=feeder_type,
            data_schema=self.add_suggested_values_to_schema(
                FEEDER_SCHEMA, user_input or self._feeder_defaults(kind.port)
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
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_PORT) is None:
            return await self.async_step_receiver(user_input)
        # Entries made before there was more than one kind of feeder record no
        # type, and fr24feed is the only one they can be.
        feeder_type = entry.data.get(CONF_FEEDER_TYPE) or FEEDER_FR24
        return await self._async_feeder_step(feeder_type, user_input)

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
                self._aircraft_schema(required),
                {CONF_AIRCRAFT_URL: self._aircraft_url},
            ),
            errors=errors,
        )

    @staticmethod
    def _aircraft_schema(required: bool) -> vol.Schema:
        """Return the aircraft.json step; the units live under Configure."""
        return REQUIRED_AIRCRAFT_SCHEMA if required else OPTIONAL_AIRCRAFT_SCHEMA

    def _feeder_defaults(self, port: int) -> dict[str, Any]:
        """Return the values to prefill a feeder step with."""
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
            }
        return {CONF_PORT: port} | ({CONF_HOST: self._host} if self._host else {})

    def _receiver_defaults(self) -> dict[str, Any]:
        """Return the values to prefill the receiver step with."""
        if self.source == SOURCE_RECONFIGURE:
            return {CONF_HOST: self._get_reconfigure_entry().data[CONF_HOST]}
        return {CONF_HOST: self._host} if self._host else {}

    async def _async_suggest_aircraft_url(self) -> str:
        """Return the current URL, or probe the receiver for one."""
        if self.source == SOURCE_RECONFIGURE:
            current = self._get_reconfigure_entry().data.get(CONF_AIRCRAFT_URL)
            if current:
                return str(current)
        if await self._async_decoder_already_read():
            # Empty for a second feeder, so one decoder is not counted twice.
            return ""
        detected = await async_detect_aircraft_url(
            async_get_clientsession(self.hass), self._host
        )
        return detected or ""

    async def _async_decoder_already_read(self) -> bool:
        """Return True if another entry already reads this host's decoder."""
        reconfiguring = (
            self._get_reconfigure_entry().entry_id
            if self.source == SOURCE_RECONFIGURE
            else None
        )
        others = [
            str(entry.data[CONF_HOST])
            for entry in self._async_current_entries()
            if entry.entry_id != reconfiguring and entry.data.get(CONF_AIRCRAFT_URL)
        ]
        if not others:
            return False
        if self._host in others:
            return True
        # One machine reached as an address on one entry and as a name on
        # another is still one machine, and would be read twice over.
        mine = await self._async_addresses(self._host)
        if not mine:
            return False
        # Written out rather than passed to any(): a generator with an await
        # in it is an async generator, which any() cannot iterate at all.
        for host in others:
            if mine & await self._async_addresses(host):
                return True
        return False

    async def _async_addresses(self, host: str) -> set[str]:
        """Return the addresses a host resolves to, or nothing if it will not."""
        try:
            found = await self.hass.async_add_executor_job(
                socket.getaddrinfo, host, None
            )
        except OSError:
            _LOGGER.debug("Could not resolve %s", host)
            return set()
        # The address is the first element of the sockaddr, whether that is an
        # IPv4 pair or an IPv6 quadruple.
        return {str(entry[4][0]) for entry in found}

    async def _async_validate_feeder(
        self, host: str, port: int, feeder_type: str
    ) -> tuple[dict[str, Any], str | None]:
        """Read the feeder's status. Returns the payload and an error key."""
        client = AdsbStationClient(
            async_get_clientsession(self.hass), host, port, feeder_type=feeder_type
        )
        try:
            return await client.async_get_feeder(), None
        except AdsbStationConnectionError:
            return {}, "cannot_connect"
        except AdsbStationError:
            return {}, "invalid_response"
        except Exception:
            _LOGGER.exception("Unexpected error while reading the feeder status")
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

        # Detected once, so entities are only created for what is reported.
        self._stats_url, self._features = await async_detect_statistics(
            async_get_clientsession(self.hass), url
        )
        return None

    def _async_finish(self, aircraft_url: str | None) -> ConfigFlowResult:
        """Create or update the config entry."""
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_FEEDER_TYPE: self._feeder_type,
            CONF_AIRCRAFT_URL: aircraft_url,
            CONF_STATS_URL: self._stats_url if aircraft_url else None,
            CONF_RECEIVER_FEATURES: self._features if aircraft_url else [],
        }
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            if entry.state is not ConfigEntryState.LOADED:
                # Never set up, so there is no update listener to reload it;
                # a station that moved address is the usual reason to be here.
                return self.async_update_reload_and_abort(entry, data=data)
            # The update listener reloads a loaded entry when its data
            # changed; reloading here as well would reload it twice.
            self.hass.config_entries.async_update_entry(entry, data=data)
            return self.async_abort(reason="reconfigure_successful")
        # The units follow Home Assistant until changed under Configure.
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
            options: dict[str, Any] = {
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                CONF_STATISTICS_INTERVAL: int(user_input[CONF_STATISTICS_INTERVAL]),
                # Kept within what the integration takes, whatever the unit.
                CONF_PROXIMITY_RADIUS: min(
                    max(
                        self._kept(
                            CONF_PROXIMITY_RADIUS,
                            user_input[CONF_PROXIMITY_RADIUS],
                            kilometres_from,
                            DEFAULT_PROXIMITY_RADIUS,
                        ),
                        MIN_PROXIMITY_RADIUS,
                    ),
                    MAX_PROXIMITY_RADIUS,
                ),
                CONF_KEEP_PASSAGES: int(
                    user_input.get(CONF_KEEP_PASSAGES, DEFAULT_KEEP_PASSAGES)
                ),
                CONF_MAP_AIRCRAFT: user_input[CONF_MAP_AIRCRAFT],
                CONF_LOOK_UP_ROUTES: user_input[CONF_LOOK_UP_ROUTES],
                CONF_LOOK_UP_PHOTOS: user_input[CONF_LOOK_UP_PHOTOS],
            }
            if (units := user_input.get(CONF_UNITS, UNITS_AUTO)) != UNITS_AUTO:
                options[CONF_UNITS] = units
            if user_input.get(CONF_AIRCRAFT_DATABASE):
                options[CONF_AIRCRAFT_DATABASE] = True
            # Left empty means no ceiling at all, so the option is absent
            # rather than nought: nought would be a ceiling on the ground.
            ceiling = user_input.get(CONF_PROXIMITY_MAX_ALTITUDE)
            if ceiling not in (None, ""):
                options[CONF_PROXIMITY_MAX_ALTITUDE] = self._kept(
                    CONF_PROXIMITY_MAX_ALTITUDE, ceiling, feet_from, None
                )

            watchlist = str(user_input.get(CONF_WATCHLIST) or "")
            models = (await async_load_reference(self.hass)).models
            # Refused, naming the line, rather than saved and never matched.
            unreadable = [
                line.strip()
                for line in watchlist.splitlines()
                if line.strip() and kind_of(line, models) is None
            ]
            if unreadable:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self.add_suggested_values_to_schema(
                        self._schema(), user_input
                    ),
                    errors={CONF_WATCHLIST: "unreadable_watchlist"},
                    description_placeholders={
                        **await self._placeholders(),
                        "lines": ", ".join(unreadable),
                    },
                )
            if watchlist.strip():
                options[CONF_WATCHLIST] = watchlist.strip()

            # Not an option: a one-off, which leaves nothing to keep.
            if user_input.get(CONF_FOLLOW_UNITS):
                let_follow(
                    self.hass, set_by_hand(self.hass, self.config_entry.entry_id)
                )
                ir.async_delete_issue(
                    self.hass,
                    DOMAIN,
                    f"{ISSUE_SET_BY_HAND}_{self.config_entry.entry_id}",
                )

            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                self._schema(), self._shown()
            ),
            description_placeholders=await self._placeholders(),
        )

    async def _placeholders(self) -> dict[str, str]:
        """Say where distances are measured from, and name the sensors with a unit
        of their own, for the box about them.
        """
        placeholders = {"measured_from": await self._measured_from()}
        if sensors := set_by_hand(self.hass, self.config_entry.entry_id):
            placeholders["sensors"] = set_by_hand_lines(sensors)
        return placeholders

    async def _measured_from(self) -> str:
        """Return the sentence on the point distances start at; none for a feeder."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is None or not self.config_entry.data.get(CONF_AIRCRAFT_URL):
            return ""
        texts = await async_get_translations(
            self.hass, self.hass.config.language, "selector", {DOMAIN}
        )
        key = f"component.{DOMAIN}.selector.measured_from.options."
        return texts.get(key + coordinator.origin_source, "")

    @property
    def _units(self) -> Units:
        """Return the units the form shows the radius and the ceiling in."""
        return units_of(self.hass, self.config_entry.options.get(CONF_UNITS))

    def _shown(self) -> dict[str, Any]:
        """Return the options as the form shows them: in the chosen units."""
        options = dict(self.config_entry.options)
        radius = options.get(CONF_PROXIMITY_RADIUS, DEFAULT_PROXIMITY_RADIUS)
        options[CONF_PROXIMITY_RADIUS] = round(kilometres_in(radius, self._units), 1)
        if (feet := options.get(CONF_PROXIMITY_MAX_ALTITUDE)) not in (None, ""):
            options[CONF_PROXIMITY_MAX_ALTITUDE] = round(feet_in(feet, self._units))
        return options

    def _kept(
        self, key: str, typed: float, to_stored: Any, default: float | None
    ) -> float:
        """Return what to store: the old value if it was left as shown.

        Kept in km or feet, the units it was filled in are only how it is
        shown, so saving again does not move it by the rounding.
        """
        stored = self.config_entry.options.get(key, default)
        if stored is not None and float(typed) == self._shown().get(key):
            return float(stored)
        return round(float(to_stored(float(typed), self._units)), 3)

    def _schema(self) -> vol.Schema:
        """Offer the download only to a decoder that names no aircraft itself.

        And the box that lets sensors follow only while one has a unit of its own,
        under the units it is about.
        """
        entry = self.config_entry
        fields = dict(options_schema(self._units).schema)
        if set_by_hand(self.hass, entry.entry_id):
            units, *rest = fields.items()
            fields = {
                units[0]: units[1],
                vol.Optional(CONF_FOLLOW_UNITS, default=False): bool,
                **dict(rest),
            }
        coordinator = getattr(entry, "runtime_data", None)
        if entry.options.get(CONF_AIRCRAFT_DATABASE) or (
            entry.data.get(CONF_AIRCRAFT_URL)
            and coordinator is not None
            and coordinator.decoder_has_database is False
        ):
            fields[vol.Optional(CONF_AIRCRAFT_DATABASE, default=False)] = bool
        return vol.Schema(fields)
