"""Services for the ADS-B Station integration.

Most of them answer. Everything the two that look aircraft up return is
already on an entity somewhere, in the attributes of the nearby list or the
closest aircraft. What they add is being able to ask a question rather than
having to know where the answer is kept: which aircraft is that, and what is
up there right now that matches this.

Both answer out of the last poll rather than going back to the decoder. A
poll is fifteen seconds old at worst, an aircraft moves four kilometres in
that time at cruising speed, and a service that fetched on demand would let an
automation hammer a decoder that is already being read on a schedule.

Two change something instead: watch and unwatch keep the watchlist, which is
otherwise only edited under Configure.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util.json import JsonArrayType

# Home Assistant 2026.10 replaced voluptuous with probatio, which keeps its API,
# and puts it in place under the old name before anything is imported. So at
# run time `voluptuous` is probatio there and voluptuous itself before it; only
# the type checker has to be told which one Home Assistant's signatures mean.
if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from .const import DOMAIN
from .coordinator import (
    AdsbStationDataUpdateCoordinator,
    AircraftStats,
    AircraftSummary,
    aircraft_attributes,
    sector_from,
)
from .intent import QUESTIONS, TRAFFIC_KINDS, answer_question
from .speech import language_of
from .watchlist import add_line, remove_line

SERVICE_LOOK_UP_AIRCRAFT: Final = "look_up_aircraft"
SERVICE_LIST_AIRCRAFT: Final = "list_aircraft"
SERVICE_INSTALL_SENTENCES: Final = "install_sentences"
SERVICE_SPEAK: Final = "speak"
SERVICE_WATCH: Final = "watch"
SERVICE_UNWATCH: Final = "unwatch"

# Where the sentences ship, and where Home Assistant reads them from. It
# reads custom sentences out of the configuration directory and nowhere else,
# so an integration cannot simply bring its own; copying them there is the
# whole of what the service does.
SENTENCES_DIRECTORY: Final = "sentences"
CONFIG_SENTENCES_DIRECTORY: Final = "custom_sentences"
SENTENCES_FILE: Final = f"{DOMAIN}.yaml"

ATTR_AIRCRAFT: Final = "aircraft"
ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_MAX_DISTANCE: Final = "max_distance"
ATTR_MIN_ALTITUDE: Final = "min_altitude"
ATTR_MAX_ALTITUDE: Final = "max_altitude"
ATTR_MILITARY: Final = "military"
ATTR_CATEGORY: Final = "category"
ATTR_QUESTION: Final = "question"
ATTR_KIND: Final = "kind"
ATTR_LANGUAGE: Final = "language"

# Shared by both services, so which station is being asked reads the same way
# in either one.
_STATION_FIELD: dict[Any, Any] = {
    vol.Optional(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
        {"integration": DOMAIN}
    )
}

LOOK_UP_SCHEMA: Final = vol.Schema(
    {**_STATION_FIELD, vol.Required(ATTR_AIRCRAFT): cv.string}
)

LIST_SCHEMA: Final = vol.Schema(
    {
        **_STATION_FIELD,
        vol.Optional(ATTR_MAX_DISTANCE): vol.Coerce(float),
        vol.Optional(ATTR_MIN_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_MAX_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_MILITARY): cv.boolean,
        vol.Optional(ATTR_CATEGORY): cv.string,
    }
)


# The line exactly as the watchlist takes it: a hex code, a registration or
# callsign, an aircraft type or a squawk.
WATCH_SCHEMA: Final = vol.Schema(
    {**_STATION_FIELD, vol.Required(ATTR_AIRCRAFT): cv.string}
)

SPEAK_SCHEMA: Final = vol.Schema(
    {
        **_STATION_FIELD,
        vol.Required(ATTR_QUESTION): vol.In(sorted(QUESTIONS)),
        vol.Optional(ATTR_KIND): vol.In(sorted(TRAFFIC_KINDS)),
        vol.Optional(ATTR_LANGUAGE): cv.string,
    }
)


def _station(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[AdsbStationDataUpdateCoordinator, AircraftStats]:
    """Return the station to answer out of, and what it last heard.

    Both at once, because a station that has heard nothing cannot answer
    either service, so the check belongs here rather than in each of them.

    A station that only feeds somewhere has no aircraft of its own, and most
    setups have one or two of those beside the one entry that carries the
    receiver. Skipping them is what lets the field be left out: it only has to
    be filled in by someone reading two antennas.
    """
    entries: list[ConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)

    if (entry_id := call.data.get(ATTR_CONFIG_ENTRY)) is not None:
        for entry in entries:
            if entry.entry_id == entry_id:
                return _receiver_of(entry)
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="station_not_loaded"
        )

    with_aircraft = [entry for entry in entries if _hears_aircraft(entry)]
    if not with_aircraft:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_receiver"
        )
    if len(with_aircraft) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="several_receivers",
            translation_placeholders={
                "stations": ", ".join(sorted(entry.title for entry in with_aircraft))
            },
        )
    return _receiver_of(with_aircraft[0])


def _hears_aircraft(entry: ConfigEntry) -> bool:
    """Return whether this entry has a receiver that has answered."""
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
    return coordinator.data.aircraft is not None


def _receiver_of(
    entry: ConfigEntry,
) -> tuple[AdsbStationDataUpdateCoordinator, AircraftStats]:
    """Return an entry's coordinator, if it has aircraft to answer with."""
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
    if (aircraft := coordinator.data.aircraft) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="station_without_aircraft",
            translation_placeholders={"station": entry.title},
        )
    return coordinator, aircraft


def _known_aircraft(aircraft: AircraftStats) -> dict[str, AircraftSummary]:
    """Return every aircraft of the last poll, by hex code.

    Those in range are laid over the rest, because they are the same aircraft
    with a route attached: routes are only looked up for the aircraft close
    enough to matter, and that happens after the poll was summarised.
    """
    known = {summary.hex: summary for summary in aircraft.heard}
    known.update({summary.hex: summary for summary in aircraft.nearby})
    return known


def _describe(
    coordinator: AdsbStationDataUpdateCoordinator, summary: AircraftSummary
) -> dict[str, Any]:
    """Describe one aircraft as an answer rather than as an attribute set."""
    return {
        **aircraft_attributes(summary, include_distance=True),
        # Which way to look, which an attribute set leaves to the sector
        # sensors and an answer has nowhere else to get.
        "sector": sector_from(coordinator.origin, summary.position),
    }


async def _async_look_up_aircraft(call: ServiceCall) -> ServiceResponse:
    """Answer with one aircraft, by hex code or by callsign."""
    coordinator, aircraft = _station(call.hass, call)
    wanted = str(call.data[ATTR_AIRCRAFT]).strip().upper()

    for summary in _known_aircraft(aircraft).values():
        if summary.hex.upper() == wanted or (
            summary.flight is not None and summary.flight.strip().upper() == wanted
        ):
            return {"aircraft": _describe(coordinator, summary)}

    # Not an error. An aircraft this station cannot hear is the ordinary
    # answer to "is it up there", and an automation asking that has to be able
    # to tell it apart from a call that went wrong.
    return {"aircraft": None}


async def _async_list_aircraft(call: ServiceCall) -> ServiceResponse:
    """Answer with every aircraft that matches, nearest first."""
    coordinator, aircraft = _station(call.hass, call)
    max_distance = call.data.get(ATTR_MAX_DISTANCE)
    min_altitude = call.data.get(ATTR_MIN_ALTITUDE)
    max_altitude = call.data.get(ATTR_MAX_ALTITUDE)
    military = call.data.get(ATTR_MILITARY)
    category = call.data.get(ATTR_CATEGORY)
    if category is not None:
        category = str(category).strip().upper()

    matching: list[AircraftSummary] = []
    for summary in _known_aircraft(aircraft).values():
        # A filter an aircraft has nothing to answer with excludes it. Asking
        # for everything under 10,000 feet cannot include the aircraft that
        # never said how high it is.
        if max_distance is not None and (
            summary.distance is None or summary.distance / 1000 > max_distance
        ):
            continue
        if min_altitude is not None and (
            summary.altitude is None or summary.altitude < min_altitude
        ):
            continue
        if max_altitude is not None and (
            summary.altitude is None or summary.altitude > max_altitude
        ):
            continue
        if military is not None and summary.military is not military:
            continue
        if category is not None and summary.category != category:
            continue
        matching.append(summary)

    # Nearest first, and the ones we cannot place last rather than first.
    matching.sort(key=lambda summary: (summary.distance is None, summary.distance or 0))
    return {"aircraft": [_describe(coordinator, summary) for summary in matching]}


def _watching_station(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry:
    """Return the entry whose watchlist to change.

    The entry that carries the receiver, which is the only one with a
    watchlist. Unlike a question, this does not need the receiver to have
    answered: a list can be kept while the decoder is down for a reboot.
    """
    entries: list[ConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)

    if (entry_id := call.data.get(ATTR_CONFIG_ENTRY)) is not None:
        for entry in entries:
            if entry.entry_id != entry_id:
                continue
            if not _has_receiver(entry):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="station_without_aircraft",
                    translation_placeholders={"station": entry.title},
                )
            return entry
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="station_not_loaded"
        )

    with_receiver = [entry for entry in entries if _has_receiver(entry)]
    if not with_receiver:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_watchlist_station"
        )
    if len(with_receiver) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="several_receivers",
            translation_placeholders={
                "stations": ", ".join(sorted(entry.title for entry in with_receiver))
            },
        )
    return with_receiver[0]


def _has_receiver(entry: ConfigEntry) -> bool:
    """Return whether this entry reads a decoder, answering or not."""
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
    return bool(coordinator.client.aircraft_url)


async def _async_watch(call: ServiceCall) -> None:
    """Put one line on the watchlist."""
    entry = _watching_station(call.hass, call)
    coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
    add_line(call.hass, entry, call.data[ATTR_AIRCRAFT], coordinator.reference.models)


async def _async_unwatch(call: ServiceCall) -> None:
    """Take one line off the watchlist."""
    entry = _watching_station(call.hass, call)
    remove_line(call.hass, entry, call.data[ATTR_AIRCRAFT])


def _copy_sentences(source: Path, target: Path) -> JsonArrayType:
    """Copy the shipped sentences into the configuration. Blocking."""
    installed: JsonArrayType = []
    for language in sorted(item.name for item in source.iterdir() if item.is_dir()):
        origin = source / language / SENTENCES_FILE
        if not origin.is_file():
            continue
        destination = target / language
        destination.mkdir(parents=True, exist_ok=True)
        (destination / SENTENCES_FILE).write_text(origin.read_text("utf-8"), "utf-8")
        installed.append(language)
    return installed


async def _async_install_sentences(call: ServiceCall) -> ServiceResponse:
    """Copy the sentences Assist needs into the configuration directory.

    Home Assistant reads custom sentences from `custom_sentences` under your
    configuration and from nowhere else, so this writes into your
    configuration rather than into its own directory. That is worth being
    plain about: it is a file this integration puts in your folder, it
    overwrites the same file on every call, and copying the two files by hand
    does exactly the same thing. Writing into the configuration is an
    administrator's call, so only an administrator can make this one.

    Nothing is loaded by writing them. Assist reads its sentences at start,
    so `conversation.reload` or a restart is what makes them work.
    """
    hass = call.hass
    source = Path(__file__).parent / SENTENCES_DIRECTORY
    target = Path(hass.config.path(CONFIG_SENTENCES_DIRECTORY))

    try:
        installed = await hass.async_add_executor_job(_copy_sentences, source, target)
    except OSError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="sentences_not_written",
            translation_placeholders={"error": str(err)},
        ) from err

    return {"languages": installed, "installed_in": str(target)}


async def _async_speak(call: ServiceCall) -> ServiceResponse:
    """Return one of the spoken answers, ready to be said back.

    The same five answers the voice questions give, reachable without any
    sentence file: an automation with a sentence trigger writes its own
    wording, calls this, and hands the result to `set_conversation_response`.
    That keeps the awkward part of speaking — a callsign spelled out, an
    airline named, a height rounded and written the way the language writes
    numbers — in here rather than in everyone's template.
    """
    coordinator, aircraft = _station(call.hass, call)
    language = language_of(call.data.get(ATTR_LANGUAGE) or call.hass.config.language)
    return {
        "speech": answer_question(
            call.data[ATTR_QUESTION],
            coordinator,
            aircraft,
            language,
            call.hass.config.units,
            call.data.get(ATTR_KIND),
        )
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services once, rather than once per station."""
    # The ones that write into the configuration, or into the options, are
    # for administrators only, as the options form is; the other three only
    # read the last poll, so anyone may ask them.
    async_register_admin_service(
        hass, DOMAIN, SERVICE_WATCH, _async_watch, schema=WATCH_SCHEMA
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_UNWATCH, _async_unwatch, schema=WATCH_SCHEMA
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_INSTALL_SENTENCES,
        _async_install_sentences,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SPEAK,
        _async_speak,
        schema=SPEAK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOOK_UP_AIRCRAFT,
        _async_look_up_aircraft,
        schema=LOOK_UP_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_AIRCRAFT,
        _async_list_aircraft,
        schema=LIST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
