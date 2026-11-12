"""Data update coordinator for the ADS-B Station integration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import logging
from math import atan2, cos, degrees, hypot, radians, sin, sqrt
from typing import Any, Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance

from .api import AdsbStationClient, AdsbStationError, read_gain
from .const import (
    AIRCRAFT_TYPE_GROUPS,
    APPROACH_HORIZON,
    APPROACH_POLLS,
    CATEGORY_ROTORCRAFT,
    CONF_LOOK_UP_PHOTOS,
    CONF_LOOK_UP_ROUTES,
    CONF_PROXIMITY_MAX_ALTITUDE,
    CONF_PROXIMITY_RADIUS,
    CONF_STATISTICS_INTERVAL,
    CONF_WATCHLIST,
    DB_FLAG_INTERESTING,
    DB_FLAG_LADD,
    DB_FLAG_MILITARY,
    DB_FLAG_PIA,
    DEFAULT_LOOK_UP_PHOTOS,
    DEFAULT_LOOK_UP_ROUTES,
    DEFAULT_PROXIMITY_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATISTICS_INTERVAL,
    DEGREE_METRES,
    DOMAIN,
    EMERGENCY_SQUAWKS,
    EMERGENCY_STATUSES,
    EVENT_AIRCRAFT_APPROACHING,
    EVENT_AIRCRAFT_EMERGENCY,
    EVENT_AIRCRAFT_PASSAGE,
    EVENT_WATCHLIST_MATCH,
    FEET_TO_METRES,
    GROUND_ALTITUDE,
    KNOTS_TO_METRES_PER_SECOND,
    MAX_PLAUSIBLE_RANGE,
    MISSED_READS_TOLERATED,
    PASSAGE_GAP,
    RADIO_HORIZON_ALLOWANCE,
    RADIO_HORIZON_METRES_PER_ROOT_FOOT,
    RECEIVER_READ_ATTEMPTS,
    RECEIVER_SILENT_AFTER,
    SECTORS,
    TRAFFIC_AIRLINE,
    TRAFFIC_HELICOPTER,
    TRAFFIC_MILITARY,
    TRAFFIC_OTHER,
    UNSET_RECEIVER_VERSION,
    WATCHLIST_HEX,
    WATCHLIST_SQUAWK,
    WATCHLIST_TYPE,
)
from .photo import AircraftPhoto, build_photo_lookup, photo_attributes
from .reference import (
    EMPTY as EMPTY_REFERENCE,
    ReferenceTables,
    designator_of,
    kind_of,
    normalise,
)
from .route import FlightPosition, FlightRoute, build_route_lookup, route_attributes
from .trails import SkyTrails

_LOGGER = logging.getLogger(__name__)


class SectorRangeRecord(Protocol):
    """A sector range sensor, as far as the reset button needs to know."""

    def reset(self) -> None:
        """Forget the record this sector holds."""


type AdsbStationConfigEntry = ConfigEntry[AdsbStationDataUpdateCoordinator]

# stats.json windows, shortest first. The longer ones cover the first seconds
# after a restart, before the one-minute window has a signal.
STATS_PERIODS = ("last1min", "last5min", "total")


@dataclass(frozen=True, kw_only=True)
class AircraftSummary:
    """One aircraft out of a single poll, as we expose it.

    The distance is None for aircraft without a position; they still count
    for the highest and fastest.
    """

    hex: str
    flight: str | None
    distance: float | None
    altitude: float | None
    speed: float | None
    track: float | None
    vertical_rate: float | None
    rssi: float | None
    seen: float | None
    # Its altitude is None too, so this tells it from an unknown altitude.
    on_ground: bool = False
    registration: str | None
    aircraft_type: str | None
    description: str | None
    military: bool
    # The other dbFlags. Passed on, not acted on: what to hide is up to the
    # dashboard.
    interesting: bool = False
    pia: bool = False
    ladd: bool = False
    # ISO code of the country of registration, from the address block.
    country: str | None = None
    # Emitter category, A0 to D7: tells a helicopter apart without a database.
    category: str | None = None
    # ADS-B, mlat or Mode S, which explains a missing position.
    heard_as: str | None = None
    # From the callsign and the shipped table, with or without routes.
    airline: str | None = None
    # The callsign's designator, even without a name; dashboards key logos on it.
    airline_code: str | None = None
    # Lets routeset tell this flight from the same number elsewhere.
    position: tuple[float, float] | None = None
    # Only for nearby aircraft, when routes are on.
    route: FlightRoute | None = None
    # For nearby and watched aircraft, when photos are on.
    photo: AircraftPhoto | None = None
    # Straight-line prediction; False when receding or too far ahead to trust.
    # The distance is across the ground, in metres.
    approaching: bool = False
    closest_passing_distance: float | None = None
    seconds_to_closest: float | None = None


@dataclass(kw_only=True)
class Passage:
    """One aircraft crossing the radius, start to finish.

    It keeps the closest approach, which is the moment worth reporting.
    """

    hex: str
    started_at: datetime
    last_seen: datetime
    # The aircraft at its closest approach, how close that was in metres, and
    # on which poll.
    closest: AircraftSummary
    closest_distance: float
    closest_at: datetime
    # As on the last poll that saw it.
    current: AircraftSummary
    current_distance: float
    # Strongest over the passage, not necessarily at the closest approach.
    peak_rssi: float | None = None


@dataclass(frozen=True, kw_only=True)
class WatchlistEntry:
    """One line of the watchlist, and what it turned out to be."""

    # As written, for automations to read back.
    line: str
    kind: str
    # As compared: capitals, no dashes.
    value: str


@dataclass(frozen=True, kw_only=True)
class WatchlistMatch:
    """One aircraft on the watchlist, in range of the antenna."""

    entry: WatchlistEntry
    # A name can match the registration or the callsign.
    matched_on: str
    summary: AircraftSummary
    squawk: str | None


@dataclass(frozen=True, kw_only=True)
class EmergencyAircraft:
    """An aircraft squawking one of the emergency codes."""

    hex: str
    flight: str | None
    squawk: str | None
    reason: str
    # How far, how high and what it is, for the event and the attributes.
    summary: AircraftSummary


@dataclass(frozen=True, kw_only=True)
class AircraftStats:
    """Figures derived from a single aircraft.json poll."""

    total: int
    with_position: int
    messages: int | None
    message_rate: float | None
    updated: datetime | None
    closest: AircraftSummary | None
    # Also the range figure, through its distance.
    furthest: AircraftSummary | None = None
    highest: AircraftSummary | None = None
    fastest: AircraftSummary | None = None
    # Everything inside the configured radius, nearest first.
    nearby: tuple[AircraftSummary, ...] = ()
    # Everything the decoder holds, near or not, for questions about one
    # aircraft. No entity shows it.
    heard: tuple[AircraftSummary, ...] = ()
    # Furthest per sector this poll; the all-time records live on the entities.
    by_sector: dict[str, AircraftSummary] = field(default_factory=dict)
    emergencies: tuple[EmergencyAircraft, ...] = ()
    # In watchlist order.
    watched: tuple[WatchlistMatch, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ReceiverStats:
    """Figures derived from a single stats.json poll."""

    period: str
    signal: float | None
    noise: float | None
    signal_to_noise: float | None
    peak_signal: float | None
    strong_signals: int | None
    samples_dropped: int | None
    accepted: int | None
    tracks: int | None
    single_message_tracks: int | None
    demodulator_load: float | None
    gain: float | None
    # Share of Mode S messages the decoder had to throw away, in percent.
    error_rate: float | None = None
    # How the decoder came to know about the aircraft it is tracking.
    aircraft_by_type: dict[str, int] = field(default_factory=dict)
    # Frequency offset of the dongle, in parts per million.
    frequency_error: float | None = None
    positions_decoded: int | None = None
    positions_rejected: int | None = None


@dataclass(frozen=True, kw_only=True)
class AdsbStationData:
    """The data of one poll cycle."""

    # None for a station that only runs a decoder.
    feeder: dict[str, Any] | None = field(default=None)
    aircraft: AircraftStats | None
    stats: ReceiverStats | None = field(default=None)


def _as_float(value: Any) -> float | None:
    """Parse a value that should be a number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Parse a value that should be a whole number."""
    number = _as_float(value)
    return None if number is None else int(number)


def _as_text(value: Any) -> str | None:
    """Return a non-empty, trimmed string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_code(value: Any) -> str | None:
    """Return a code in capitals, so `a7` from a decoder still matches `A7`."""
    text = _as_text(value)
    return None if text is None else text.upper()


def _position(entry: dict[str, Any]) -> tuple[float, float] | None:
    """Return the position of an aircraft, if it reported one."""
    latitude = _as_float(entry.get("lat"))
    longitude = _as_float(entry.get("lon"))
    if latitude is None or longitude is None:
        return None
    return latitude, longitude


ALTITUDE_KEYS = ("alt_baro", "altitude")


def _altitude(entry: dict[str, Any]) -> float | None:
    """Return the barometric altitude in feet ('altitude' in fr24feed's fork)."""
    for key in ALTITUDE_KEYS:
        if key in entry:
            return _as_float(entry[key])
    return None


def _on_ground(entry: dict[str, Any]) -> bool:
    """Return True if the altitude field says 'ground' rather than a number."""
    for key in ALTITUDE_KEYS:
        if key in entry:
            return str(entry[key]).strip().lower() == GROUND_ALTITUDE
    return False


def _ground_speed(entry: dict[str, Any]) -> float | None:
    """Return the ground speed in knots, under either of its two names."""
    for key in ("gs", "speed"):
        if key in entry:
            return _as_float(entry[key])
    return None


def _vertical_rate(entry: dict[str, Any]) -> float | None:
    """Return the rate of climb or descent in feet per minute.

    Barometric first, as every map shows; fr24feed's fork calls it 'vert_rate'.
    """
    for key in ("baro_rate", "geom_rate", "vert_rate"):
        if (rate := _as_float(entry.get(key))) is not None:
            return rate
    return None


def slant_distance(summary: AircraftSummary) -> float | None:
    """Return the distance through the air in metres, height included.

    Ground distance alone would count an airliner at cruise as overhead.
    Without an altitude it falls back to the ground distance.
    """
    if summary.distance is None:
        return None
    if summary.altitude is None:
        return summary.distance
    return hypot(summary.distance, summary.altitude * FEET_TO_METRES)


def approach_of(
    origin: tuple[float, float], summary: AircraftSummary
) -> tuple[float, float] | None:
    """Return how close an aircraft will pass across the ground, and when.

    A straight line at constant speed, so only for an airborne aircraft with
    position, track and speed that is still closing. Height is left out; the
    overhead ceiling decides whether it matters.
    """
    if summary.position is None or summary.track is None or summary.speed is None:
        return None
    if summary.on_ground or summary.speed <= 0:
        return None

    origin_latitude, origin_longitude = origin
    latitude, longitude = summary.position
    # Flat earth is close enough over a receiver's range.
    north = (latitude - origin_latitude) * DEGREE_METRES
    east = (
        (longitude - origin_longitude) * DEGREE_METRES * cos(radians(origin_latitude))
    )

    speed = summary.speed * KNOTS_TO_METRES_PER_SECOND
    east_per_second = speed * sin(radians(summary.track))
    north_per_second = speed * cos(radians(summary.track))

    # Where the distance stops shrinking: the point on the aircraft's line
    # nearest the antenna. A positive figure here means it is already past it.
    closing = east * east_per_second + north * north_per_second
    if closing >= 0:
        return None
    seconds = -closing / (speed * speed)
    metres = hypot(east + east_per_second * seconds, north + north_per_second * seconds)
    return metres, seconds


def _is_believable(metres: float, altitude: float | None) -> bool:
    """Return whether an aircraft can really be that far away.

    A mis-decoded position lands beyond line of sight, and would otherwise
    set a sector record that stands until reset.
    """
    if metres > MAX_PLAUSIBLE_RANGE:
        return False
    if altitude is None:
        return True
    # Below sea level is real; clamp before the square root.
    horizon = RADIO_HORIZON_METRES_PER_ROOT_FOOT * sqrt(max(altitude, 0.0))
    return metres <= horizon + RADIO_HORIZON_ALLOWANCE


def _under(summary: AircraftSummary, ceiling: float | None) -> bool:
    """Return whether an aircraft is low enough to count as nearby.

    On the ground is always under. Any other aircraft without an altitude
    cannot be judged and does not count.
    """
    if ceiling is None:
        return True
    if summary.on_ground:
        return True
    return summary.altitude is not None and summary.altitude <= ceiling


def _db_flag(entry: dict[str, Any], flag: int) -> bool:
    """Return whether a dbFlags bit is set; False without a database too."""
    flags = _as_int(entry.get("dbFlags"))
    return flags is not None and bool(flags & flag)


def _military_flag(entry: dict[str, Any]) -> bool | None:
    """Return the military bit of dbFlags, or None without a database.

    None lets the address block decide instead; a database answer wins either
    way.
    """
    flags = _as_int(entry.get("dbFlags"))
    return None if flags is None else bool(flags & DB_FLAG_MILITARY)


def _bearing(
    latitude: float, longitude: float, other_latitude: float, other_longitude: float
) -> float:
    """Return the initial great circle bearing between two points, in degrees."""
    phi1, phi2 = radians(latitude), radians(other_latitude)
    delta = radians(other_longitude - longitude)
    y = sin(delta) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(delta)
    return (degrees(atan2(y, x)) + 360) % 360


def sector_of(bearing: float) -> str:
    """Return the compass sector a bearing falls in, sectors centred on it."""
    return SECTORS[int(((bearing + 22.5) % 360) // 45)]


def sector_from(
    origin: tuple[float, float], position: tuple[float, float] | None
) -> str | None:
    """Return which way an aircraft lies, seen from the antenna."""
    return None if position is None else sector_of(_bearing(*origin, *position))


def _summarise(
    entry: dict[str, Any],
    metres: float | None,
    position: tuple[float, float] | None = None,
    reference: ReferenceTables = EMPTY_REFERENCE,
) -> AircraftSummary:
    """Turn one aircraft.json entry into the shape we expose."""
    flight = _as_text(entry.get("flight"))
    aircraft_type = _as_text(entry.get("t"))
    hex_code = str(entry.get("hex", ""))
    military = _military_flag(entry)
    return AircraftSummary(
        hex=hex_code,
        flight=flight,
        distance=metres,
        position=position,
        altitude=_altitude(entry),
        speed=_ground_speed(entry),
        track=_as_float(entry.get("track")),
        vertical_rate=_vertical_rate(entry),
        rssi=_as_float(entry.get("rssi")),
        seen=_as_float(entry.get("seen")),
        on_ground=_on_ground(entry),
        # Only a decoder with an aircraft database fills these in.
        registration=_as_text(entry.get("r")),
        aircraft_type=aircraft_type,
        # Databases often give a type code without a description.
        description=_as_text(entry.get("desc")) or reference.model_of(aircraft_type),
        military=reference.is_military(hex_code) if military is None else military,
        interesting=_db_flag(entry, DB_FLAG_INTERESTING),
        pia=_db_flag(entry, DB_FLAG_PIA),
        ladd=_db_flag(entry, DB_FLAG_LADD),
        country=reference.country_of(hex_code),
        category=_as_code(entry.get("category")),
        heard_as=_as_text(entry.get("type")),
        airline=reference.airline_of(flight),
        airline_code=designator_of(flight),
    )


def aircraft_attributes(
    summary: AircraftSummary, *, include_distance: bool = False
) -> dict[str, Any]:
    """Describe one aircraft for the attributes of an entity.

    The distance is left out where the entity state already is the distance.
    """
    attributes: dict[str, Any] = {
        "hex": summary.hex,
        "flight": summary.flight,
        "altitude": summary.altitude,
        "speed": summary.speed,
        "track": summary.track,
        # Feet per minute, positive climbing.
        "vertical_rate": summary.vertical_rate,
        "rssi": summary.rssi,
        "seen": summary.seen,
    }
    if include_distance:
        attributes["distance"] = (
            None if summary.distance is None else round(summary.distance / 1000, 1)
        )
    # Left out rather than empty when unknown.
    if summary.registration is not None:
        attributes["registration"] = summary.registration
    if summary.aircraft_type is not None:
        attributes["aircraft_type"] = summary.aircraft_type
    if summary.description is not None:
        attributes["description"] = summary.description
    if summary.country is not None:
        attributes["country"] = summary.country
    if summary.category is not None:
        attributes["category"] = summary.category
    if summary.heard_as is not None:
        attributes["heard_as"] = summary.heard_as
    if summary.military:
        attributes["military"] = True
    if summary.interesting:
        attributes["interesting"] = True
    if summary.pia:
        attributes["pia"] = True
    if summary.ladd:
        attributes["ladd"] = True
    if summary.on_ground:
        attributes["on_ground"] = True
    if summary.approaching:
        attributes["approaching"] = True
        attributes["closest_passing_distance"] = (
            None
            if summary.closest_passing_distance is None
            else round(summary.closest_passing_distance / 1000, 1)
        )
        attributes["seconds_to_closest"] = (
            None
            if summary.seconds_to_closest is None
            else round(summary.seconds_to_closest)
        )
    if summary.airline_code is not None:
        attributes["airline_code"] = summary.airline_code
    if summary.airline is not None:
        attributes["airline"] = summary.airline
    attributes.update(route_attributes(summary.route))
    attributes.update(photo_attributes(summary.photo))
    return attributes


def traffic_kind(summary: AircraftSummary) -> str:
    """Return which of the four traffic counters an aircraft counts under.

    An airline flight is one whose callsign opens with a known designator:
    KLM123 is, PHBXA is not.
    """
    if summary.military:
        return TRAFFIC_MILITARY
    if summary.category == CATEGORY_ROTORCRAFT:
        return TRAFFIC_HELICOPTER
    if summary.airline is not None:
        return TRAFFIC_AIRLINE
    return TRAFFIC_OTHER


def count_of(stats: AircraftStats, kind: str) -> int:
    """Return how many of the aircraft heard this poll are of one kind."""
    return sum(1 for summary in stats.heard if traffic_kind(summary) == kind)


def watchlist_signal(entry_id: str) -> str:
    """Return what is sent when an entry's watchlist changes in place."""
    return f"{DOMAIN}_{entry_id}_watchlist"


def watchlist_of(entry: ConfigEntry, models: dict[str, str]) -> list[WatchlistEntry]:
    """Read the watchlist off an entry, skipping lines it cannot read.

    Those can come from an older type table or a restored backup.
    """
    text = entry.options.get(CONF_WATCHLIST) or ""
    watched = []
    for line in str(text).splitlines():
        if (kind := kind_of(line, models)) is not None:
            watched.append(
                WatchlistEntry(line=line.strip(), kind=kind, value=normalise(line))
            )
    return watched


def _matches(
    watched: WatchlistEntry, summary: AircraftSummary, squawk: str
) -> str | None:
    """Return which field of an aircraft a watchlist line matched on."""
    if watched.kind == WATCHLIST_HEX:
        return "hex" if normalise(summary.hex) == watched.value else None
    if watched.kind == WATCHLIST_SQUAWK:
        return "squawk" if normalise(squawk) == watched.value else None
    if watched.kind == WATCHLIST_TYPE:
        return (
            "aircraft_type"
            if normalise(summary.aircraft_type) == watched.value
            else None
        )
    # A name can be either, so it is compared against both.
    if normalise(summary.registration) == watched.value:
        return "registration"
    return "flight" if normalise(summary.flight) == watched.value else None


def receivers(
    hass: HomeAssistant,
) -> list[tuple[AdsbStationDataUpdateCoordinator, AircraftStats]]:
    """Return every entry that reads a receiver, sorted by title.

    Feeder-only entries are left out, or one decoder's aircraft would count
    twice. Sorting keeps the order independent of load order.
    """
    found = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: AdsbStationDataUpdateCoordinator = entry.runtime_data
        if (aircraft := coordinator.data.aircraft) is not None:
            found.append((entry.title, coordinator, aircraft))
    found.sort(key=lambda station: station[0])
    return [(coordinator, aircraft) for _, coordinator, aircraft in found]


def _emergency_reason(entry: dict[str, Any]) -> str | None:
    """Return why an aircraft counts as an emergency, or None.

    readsb and dump1090-fa state it outright; every decoder gives the squawk,
    which still counts when the status is one that is not distress.
    """
    reported = (_as_text(entry.get("emergency")) or "").lower()
    if (reason := EMERGENCY_STATUSES.get(reported)) is not None:
        return reason
    return EMERGENCY_SQUAWKS.get(str(entry.get("squawk", "")).strip())


class AdsbStationDataUpdateCoordinator(DataUpdateCoordinator[AdsbStationData]):
    """Polls monitor.json and, when configured, aircraft.json and stats.json."""

    config_entry: AdsbStationConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AdsbStationConfigEntry,
        client: AdsbStationClient,
        reference: ReferenceTables = EMPTY_REFERENCE,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self.statistics_interval = timedelta(
            seconds=config_entry.options.get(
                CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Without aircraft.json, faster polling would only repeat statistics.
            update_interval=(
                scan_interval if client.aircraft_url else self.statistics_interval
            ),
        )
        self.client = client
        # None until the first poll, which always reads them.
        self._statistics_read_at: datetime | None = None
        # Empty if the tables could not be read; that costs only names.
        self.reference = reference
        self.receiver_version: str | None = None
        # Routes and photos are the only requests that leave the network, and
        # both are None unless switched on.
        self.route_lookup = build_route_lookup(
            async_get_clientsession(hass),
            config_entry.options.get(CONF_LOOK_UP_ROUTES, DEFAULT_LOOK_UP_ROUTES),
        )
        self.photo_lookup = build_photo_lookup(
            async_get_clientsession(hass),
            config_entry.options.get(CONF_LOOK_UP_PHOTOS, DEFAULT_LOOK_UP_PHOTOS),
        )
        # Registered by the sector sensors, for the reset button.
        self.sector_sensors: list[SectorRangeRecord] = []
        # Aircraft crossing the radius now, by hex, kept across polls.
        self.passages: dict[str, Passage] = {}
        # The nearest of those on the last poll, and when that poll was.
        self.overhead: Passage | None = None
        self.tracked_at: datetime | None = None
        self._previous_messages: tuple[int, float] | None = None
        # Seeded with the start, so a dongle gone from the first poll is noticed.
        self._sampled_at = dt_util.utcnow()
        self._sampled_until: float | None = None
        self.receiver_silent = False
        # Reads in a row each endpoint has missed; see MISSED_READS_TOLERATED.
        self._feeder_misses = 0
        self._aircraft_misses = 0
        self._stats_misses = 0
        # Unavailable right now, for the log's warning and all-clear. Without a
        # last answer to keep, that is from the first miss.
        self._aircraft_out = False
        self._stats_out = False
        self._antenna: tuple[float, float] | None = None
        self._receiver_reads_left = RECEIVER_READ_ATTEMPTS
        self.watchlist = watchlist_of(config_entry, reference.models)
        # To tell a watchlist-only change from one that needs a reload.
        self.started_with = dict(config_entry.options)
        # And a reconfigured station, which always does.
        self.started_with_data = dict(config_entry.data)
        # When each watched aircraft was last seen, so one flight is one message.
        self._announced: dict[str, datetime] = {}
        # The same for aircraft in distress.
        self._distressed: dict[str, datetime] = {}
        # Polls in a row each aircraft has been approaching, and its last warning.
        self._approaching: dict[str, int] = {}
        self._warned: dict[str, datetime] = {}
        self.trails = SkyTrails()

    @property
    def feeder_type(self) -> str | None:
        """Return which feeder this entry reads, if any."""
        return self.client.feeder_type

    @property
    def origin(self) -> tuple[float, float]:
        """Return the point that ranges are measured from."""
        if self._antenna is not None:
            return self._antenna
        return self.hass.config.latitude, self.hass.config.longitude

    @property
    def proximity_radius(self) -> float:
        """Return how close an aircraft counts as nearby, in metres."""
        kilometres = self.config_entry.options.get(
            CONF_PROXIMITY_RADIUS, DEFAULT_PROXIMITY_RADIUS
        )
        return float(kilometres) * 1000

    @property
    def proximity_ceiling(self) -> float | None:
        """Return the nearby ceiling in feet, or None when only the radius counts."""
        feet = self.config_entry.options.get(CONF_PROXIMITY_MAX_ALTITUDE)
        return None if feet in (None, "") else float(feet)

    @property
    def origin_source(self) -> str:
        """Return whether ranges are measured from the receiver or from home."""
        return "receiver" if self._antenna is not None else "home_location"

    async def async_set_watchlist(self) -> None:
        """Take over a changed watchlist without reloading the entry.

        A reload would forget announcements and passages under way, and
        announce and count them again.
        """
        self.watchlist = watchlist_of(self.config_entry, self.reference.models)
        self.started_with = dict(self.config_entry.options)
        async_dispatcher_send(self.hass, watchlist_signal(self.config_entry.entry_id))
        await self.async_request_refresh()

    @callback
    def async_update_listeners(self) -> None:
        """Follow the trails, then notify listeners; every good poll passes here."""
        if self.data is not None and self.data.aircraft is not None:
            self.trails.follow(self.data.aircraft.heard, dt_util.utcnow().timestamp())
        super().async_update_listeners()

    async def _async_update_data(self) -> AdsbStationData:
        """Fetch every endpoint; only the primary source is fatal.

        That is the feeder when there is one, otherwise the receiver.
        """
        if self.data is not None and not self._statistics_due():
            aircraft = await self._async_get_aircraft(
                required=not self.client.has_feeder
            )
            return replace(
                self.data, aircraft=self._count_messages(aircraft, sample=False)
            )

        feeder: dict[str, Any] | None = None
        if self.client.has_feeder:
            try:
                feeder = await self.client.async_get_feeder()
            except AdsbStationError as err:
                self._feeder_misses += 1
                if self.data is None or self._feeder_misses > MISSED_READS_TOLERATED:
                    raise UpdateFailed(err) from err
                _LOGGER.debug("Missed a read of the feeder, keeping the last: %s", err)
                feeder = self.data.feeder
            else:
                self._feeder_misses = 0

        aircraft = await self._async_get_aircraft(required=not self.client.has_feeder)
        data = AdsbStationData(
            feeder=feeder,
            aircraft=self._count_messages(aircraft, sample=True),
            stats=await self._async_get_stats(),
        )
        self._statistics_read_at = dt_util.utcnow()
        return data

    def _count_messages(
        self, aircraft: AircraftStats | None, *, sample: bool
    ) -> AircraftStats | None:
        """Give this poll's aircraft the message figures they should show.

        Those move at the statistics interval; in between, the last ones stand.
        """
        if aircraft is None:
            return None
        previous = self.data.aircraft if self.data is not None else None
        if aircraft is previous:
            # A missed read, keeping the last answer.
            return aircraft
        if not sample and previous is not None:
            return replace(
                aircraft,
                messages=previous.messages,
                message_rate=previous.message_rate,
            )
        now = None if aircraft.updated is None else aircraft.updated.timestamp()
        return replace(
            aircraft, message_rate=self._take_message_rate(aircraft.messages, now)
        )

    def _check_samples(self, data: dict[str, Any] | None) -> None:
        """Note whether the dongle is delivering, and say so when it stops.

        A dead dongle can look like an empty sky. Samples flow whether anything
        flies or not, so the last minute's sample count tells them apart; a
        minute that did not move on means a hung decoder. A decoder that counts
        no samples is trusted. None is an unreadable stats.json.
        """
        now = dt_util.utcnow()
        window = data.get("last1min") if data is not None else None
        if isinstance(window, dict):
            local = window.get("local")
            samples = (
                _as_int(local.get("samples_processed"))
                if isinstance(local, dict)
                else None
            )
            until = _as_float(window.get("end"))
            moved_on = until is None or until != self._sampled_until
            self._sampled_until = until
            if samples is None or (samples > 0 and moved_on):
                self._sampled_at = now
        elif data is not None:
            self._sampled_at = now

        silent = now - self._sampled_at >= RECEIVER_SILENT_AFTER
        if silent == self.receiver_silent:
            return
        self.receiver_silent = silent

        entry = self.config_entry
        issue_id = f"receiver_silent_{entry.entry_id}"
        if not silent:
            _LOGGER.info(
                "The dongle behind %s is delivering again", self.client.stats_url
            )
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        _LOGGER.warning(
            "The dongle behind %s has delivered no samples since %s. It may be "
            "gone or wedged; plugging it back in or restarting the decoder "
            "usually helps",
            self.client.stats_url,
            self._sampled_at.isoformat(timespec="seconds"),
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="receiver_silent",
            translation_placeholders={
                "station": entry.title,
                "minutes": str(int(RECEIVER_SILENT_AFTER.total_seconds() // 60)),
            },
        )

    def _statistics_due(self) -> bool:
        """Return whether the feeder and stats.json should be read this poll.

        Half a poll of slack, so jitter does not push a read to the next poll.
        """
        if self._statistics_read_at is None:
            return True
        slack = (self.update_interval or timedelta()) / 2
        elapsed = dt_util.utcnow() - self._statistics_read_at
        return elapsed + slack >= self.statistics_interval

    async def _async_get_aircraft(self, *, required: bool) -> AircraftStats | None:
        """Fetch aircraft.json; an unreachable receiver is fatal only if required."""
        if not self.client.aircraft_url:
            return None
        try:
            data = await self.client.async_get_aircraft()
        except AdsbStationError as err:
            self._aircraft_misses += 1
            previous = self.data.aircraft if self.data is not None else None
            if previous is not None and self._aircraft_misses <= MISSED_READS_TOLERATED:
                # The last answer, unchanged, so nothing is announced twice.
                _LOGGER.debug(
                    "Missed a read of %s, keeping the last: %s",
                    self.client.aircraft_url,
                    err,
                )
                return previous
            if required:
                # No stats.json this poll either, so no samples.
                if self.client.stats_url:
                    self._check_samples(None)
                raise UpdateFailed(err) from err
            # The feeder entities keep working; log the outage once.
            if not self._aircraft_out:
                self._aircraft_out = True
                _LOGGER.warning(
                    "Could not read %s: %s. The aircraft entities become "
                    "unavailable until the receiver answers again",
                    self.client.aircraft_url,
                    err,
                )
            return None

        if self._aircraft_out:
            self._aircraft_out = False
            _LOGGER.info("%s can be read again", self.client.aircraft_url)
        self._aircraft_misses = 0

        await self._async_read_receiver()
        stats = await self._async_add_routes(self._build_aircraft_stats(data))
        stats = await self._async_add_photos(stats)
        # After routes and photos, so the events carry them.
        self._track_passages(stats)
        self._announce_watched(stats)
        self._announce_approaching(stats)
        self._announce_emergencies(stats)
        return stats

    def _track_passages(self, stats: AircraftStats) -> None:
        """Follow the aircraft crossing the radius, and announce new ones.

        From the nearby list, dropping aircraft that are too high or on the
        ground, so taxiing traffic at a nearby field is no passage.
        """
        now = dt_util.utcnow()
        radius = self.proximity_radius
        in_view: list[Passage] = []

        for summary in stats.nearby:
            if summary.on_ground:
                continue
            metres = slant_distance(summary)
            if metres is None or metres > radius:
                continue

            passage = self.passages.get(summary.hex)
            # The gap plus a poll: at the slowest interval polls are as far
            # apart as the gap, and every one would start a new passage.
            if passage is None or now - passage.last_seen > self._remembered():
                passage = Passage(
                    hex=summary.hex,
                    started_at=now,
                    last_seen=now,
                    closest=summary,
                    closest_distance=metres,
                    closest_at=now,
                    current=summary,
                    current_distance=metres,
                    peak_rssi=summary.rssi,
                )
                self.passages[summary.hex] = passage
                in_view.append(passage)
                self._announce(passage, metres)
                continue

            in_view.append(passage)
            passage.last_seen = now
            passage.current = summary
            passage.current_distance = metres
            if metres < passage.closest_distance:
                passage.closest = summary
                passage.closest_distance = metres
                passage.closest_at = now
            if summary.rssi is not None and (
                passage.peak_rssi is None or summary.rssi > passage.peak_rssi
            ):
                passage.peak_rssi = summary.rssi

        # The nearest seen this poll; one not seen now is not overhead.
        self.overhead = (
            min(in_view, key=lambda passage: passage.current_distance)
            if in_view
            else None
        )
        self.tracked_at = now

        # Forget passages gone longer than the gap.
        for hex_code in [
            hex_code
            for hex_code, passage in self.passages.items()
            if now - passage.last_seen > self._remembered()
        ]:
            del self.passages[hex_code]

    def _remembered(self) -> timedelta:
        """Return how long a passage stays in memory after it was last seen.

        The gap, and the poll after it that forgets it: with a slow interval
        an aircraft is only known to be gone one poll after it went.
        """
        return PASSAGE_GAP + (self.update_interval or timedelta())

    def in_view(self, now: datetime) -> bool:
        """Return True while the last poll that followed the aircraft is recent.

        With the decoder gone that poll stays the last one, and what it saw
        is no longer up there.
        """
        return self.tracked_at is not None and now - self.tracked_at <= (
            self._remembered()
        )

    def last_passed(self, now: datetime) -> tuple[Passage, datetime] | None:
        """Return the aircraft that most recently came past, and when.

        Past means gone, or seen further away than it once was. When is its
        closest approach; for one that stayed longer than the gap after that
        and then left, the moment it was last seen. Measured against the
        clock rather than the last poll, so a memory polls no longer refresh
        still ages.
        """
        in_view = self.in_view(now)
        found: list[tuple[datetime, Passage]] = []
        for passage in self.passages.values():
            when = passage.closest_at
            if in_view and passage.last_seen == self.tracked_at:
                # Still in view: past once it is further off than it was, and
                # overhead rather than past when that was long ago.
                if passage.current_distance <= passage.closest_distance:
                    continue
                if now - when > PASSAGE_GAP:
                    continue
            elif now - passage.last_seen > self._remembered():
                # What the next poll will forget, or would have.
                continue
            elif passage.last_seen - when > PASSAGE_GAP:
                # It stayed; what is recent is that it left.
                when = passage.last_seen
            found.append((when, passage))

        if not found:
            return None
        # The latest, and of two on the same poll the one that came closer.
        when, passage = max(
            found, key=lambda item: (item[0], -item[1].closest_distance)
        )
        return passage, when

    def _announce_approaching(self, stats: AircraftStats) -> None:
        """Fire an event for an aircraft that is about to come over.

        Only within the passage radius and ceiling, only after APPROACH_POLLS
        polls agree, and once per PASSAGE_GAP.
        """
        now = dt_util.utcnow()
        radius = self.proximity_radius
        ceiling = self.proximity_ceiling
        coming: set[str] = set()

        for summary in stats.heard:
            if not summary.approaching or summary.closest_passing_distance is None:
                continue
            if summary.closest_passing_distance > radius or not _under(
                summary, ceiling
            ):
                continue

            coming.add(summary.hex)
            if self._approaching.get(summary.hex, 0) + 1 < APPROACH_POLLS:
                self._approaching[summary.hex] = (
                    self._approaching.get(summary.hex, 0) + 1
                )
                continue
            self._approaching[summary.hex] = APPROACH_POLLS

            warned = self._warned.get(summary.hex)
            if warned is not None and now - warned <= PASSAGE_GAP:
                continue
            self._warned[summary.hex] = now
            self.hass.bus.async_fire(
                EVENT_AIRCRAFT_APPROACHING,
                {
                    "entry_id": self.config_entry.entry_id,
                    "station": self.config_entry.title,
                    **aircraft_attributes(summary, include_distance=True),
                },
            )

        # One that stopped approaching starts counting again.
        for hex_code in set(self._approaching) - coming:
            del self._approaching[hex_code]
        for hex_code in [
            hex_code
            for hex_code, warned in self._warned.items()
            if now - warned > PASSAGE_GAP
        ]:
            del self._warned[hex_code]

    def _announce_watched(self, stats: AircraftStats) -> None:
        """Fire an event for each watched aircraft in range, at any distance."""
        now = dt_util.utcnow()
        for match in stats.watched:
            # Last seen rather than last announced, so one that stays in
            # range for an hour is still one message.
            # The gap plus a poll, or at the slowest interval every poll would
            # look like a return.
            seen = self._announced.get(match.summary.hex)
            self._announced[match.summary.hex] = now
            if seen is not None and now - seen <= self._remembered():
                continue
            self.hass.bus.async_fire(
                EVENT_WATCHLIST_MATCH,
                {
                    "entry_id": self.config_entry.entry_id,
                    "station": self.config_entry.title,
                    "watching": match.entry.line,
                    "matched_on": match.matched_on,
                    "squawk": match.squawk,
                    **aircraft_attributes(match.summary, include_distance=True),
                },
            )

        # Gone longer than the gap: announce it again when it returns.
        for hex_code in [
            hex_code
            for hex_code, seen in self._announced.items()
            if now - seen > self._remembered()
        ]:
            del self._announced[hex_code]

    def _announce_emergencies(self, stats: AircraftStats) -> None:
        """Fire an event for each aircraft in distress, at any distance or height.

        Once per flight, as the watchlist does. Only its start: an aircraft
        that leaves range cannot be told from one whose emergency is over.
        """
        now = dt_util.utcnow()
        for emergency in stats.emergencies:
            seen = self._distressed.get(emergency.hex)
            self._distressed[emergency.hex] = now
            if seen is not None and now - seen <= self._remembered():
                continue
            self.hass.bus.async_fire(
                EVENT_AIRCRAFT_EMERGENCY,
                {
                    "entry_id": self.config_entry.entry_id,
                    "station": self.config_entry.title,
                    "reason": emergency.reason,
                    "squawk": emergency.squawk,
                    **aircraft_attributes(emergency.summary, include_distance=True),
                },
            )

        for hex_code in [
            hex_code
            for hex_code, seen in self._distressed.items()
            if now - seen > self._remembered()
        ]:
            del self._distressed[hex_code]

    def _announce(self, passage: Passage, metres: float) -> None:
        """Fire the event for a passage that has just begun.

        Per aircraft, so a second arrival while one is overhead is not missed.
        """
        self.hass.bus.async_fire(
            EVENT_AIRCRAFT_PASSAGE,
            {
                "entry_id": self.config_entry.entry_id,
                "station": self.config_entry.title,
                **aircraft_attributes(passage.closest, include_distance=True),
                # Through the air; "distance" is across the ground.
                "slant_distance": round(metres / 1000, 1),
            },
        )

    async def _async_add_routes(self, stats: AircraftStats) -> AircraftStats:
        """Look up the routes of the nearby aircraft only, to spare routeset."""
        if self.route_lookup is None or not stats.nearby:
            return stats

        flights = [
            FlightPosition(
                callsign=summary.flight,
                latitude=None if summary.position is None else summary.position[0],
                longitude=None if summary.position is None else summary.position[1],
            )
            for summary in stats.nearby
            if summary.flight is not None
        ]
        if not flights:
            return stats

        routes = await self.route_lookup.async_resolve(flights)
        if not routes:
            return stats

        return replace(
            stats,
            nearby=tuple(
                summary
                if (route := routes.get(summary.flight or "")) is None
                else replace(summary, route=route)
                for summary in stats.nearby
            ),
        )

    async def _async_add_photos(self, stats: AircraftStats) -> AircraftStats:
        """Look up photos of the nearby and the watched aircraft.

        Not under a PIA address: it is reused, so the photo could be of
        another airframe.
        """
        if self.photo_lookup is None:
            return stats

        wanted = [
            summary
            for summary in (
                *stats.nearby,
                *(match.summary for match in stats.watched),
            )
            if not summary.pia
        ]
        if not wanted:
            return stats

        photos = await self.photo_lookup.async_resolve(
            summary.hex for summary in wanted
        )
        if not photos:
            return stats

        def with_photo(summary: AircraftSummary) -> AircraftSummary:
            if summary.pia or (photo := photos.get(summary.hex.lower())) is None:
                return summary
            return replace(summary, photo=photo)

        return replace(
            stats,
            nearby=tuple(with_photo(summary) for summary in stats.nearby),
            watched=tuple(
                replace(match, summary=with_photo(match.summary))
                for match in stats.watched
            ),
        )

    async def _async_get_stats(self) -> ReceiverStats | None:
        """Fetch stats.json, tolerating a receiver that is not reachable."""
        if not self.client.stats_url:
            return None
        try:
            data = await self.client.async_get_stats()
        except AdsbStationError as err:
            # A missed read counts as no samples towards going silent.
            self._check_samples(None)
            self._stats_misses += 1
            previous = self.data.stats if self.data is not None else None
            if previous is not None and self._stats_misses <= MISSED_READS_TOLERATED:
                _LOGGER.debug(
                    "Missed a read of %s, keeping the last: %s",
                    self.client.stats_url,
                    err,
                )
                return previous
            if not self._stats_out:
                self._stats_out = True
                _LOGGER.warning(
                    "Could not read %s: %s. The reception statistics become "
                    "unavailable until the receiver answers again",
                    self.client.stats_url,
                    err,
                )
            return None

        if self._stats_out:
            self._stats_out = False
            _LOGGER.info("%s can be read again", self.client.stats_url)
        self._stats_misses = 0

        self._check_samples(data)
        return self._build_receiver_stats(data)

    async def _async_read_receiver(self) -> None:
        """Read receiver.json once: the antenna position and the decoder version.

        Neither changes while the decoder runs. A failed request gets a few
        more tries before falling back to the home location until a reload.
        """
        if self._receiver_reads_left <= 0:
            return
        self._receiver_reads_left -= 1
        try:
            data = await self.client.async_get_receiver()
        except AdsbStationError as err:
            if self._receiver_reads_left > 0:
                _LOGGER.debug("Could not read receiver.json: %s. Trying again", err)
            else:
                _LOGGER.warning(
                    "Could not read receiver.json in %s attempts: %s. Range is "
                    "measured from the Home Assistant home location instead of "
                    "from the antenna, and will be until this entry is reloaded",
                    RECEIVER_READ_ATTEMPTS,
                    err,
                )
            return

        self._receiver_reads_left = 0

        # Without a feeder, this names the decoder on the device page.
        version = _as_text(data.get("version"))
        if version is not None and version != UNSET_RECEIVER_VERSION:
            self.receiver_version = version

        position = _position({"lat": data.get("lat"), "lon": data.get("lon")})
        # No coordinates (fr24feed's fork) or 0,0 (unconfigured): use home.
        if position is None or position == (0.0, 0.0):
            _LOGGER.debug(
                "receiver.json has no usable position; measuring range from the "
                "Home Assistant home location instead"
            )
            return

        self._antenna = position
        _LOGGER.debug("Measuring range from the receiver position in receiver.json")

    def _build_aircraft_stats(self, data: dict[str, Any]) -> AircraftStats:
        """Turn a raw aircraft.json document into the figures we expose.

        Aircraft not heard for a moment still count: their range was really
        reached, and the count then matches the decoder's own map.
        """
        aircraft: list[dict[str, Any]] = [
            entry for entry in data["aircraft"] if isinstance(entry, dict)
        ]
        origin_latitude, origin_longitude = self.origin
        radius = self.proximity_radius
        ceiling = self.proximity_ceiling

        with_position = 0
        # Each record keeps the plain number it won on, so comparisons stay typed.
        closest: AircraftSummary | None = None
        closest_metres: float | None = None
        furthest: AircraftSummary | None = None
        furthest_metres: float | None = None
        highest: AircraftSummary | None = None
        highest_feet: float | None = None
        fastest: AircraftSummary | None = None
        fastest_knots: float | None = None
        nearby: list[AircraftSummary] = []
        heard: list[AircraftSummary] = []
        watched: list[WatchlistMatch] = []
        by_sector: dict[str, AircraftSummary] = {}
        sector_metres: dict[str, float] = {}
        emergencies: list[EmergencyAircraft] = []

        for entry in aircraft:
            metres: float | None = None
            if (position := _position(entry)) is not None:
                metres = distance(origin_latitude, origin_longitude, *position)
                # An unbelievable position is dropped; the aircraft still counts.
                if metres is not None and not _is_believable(
                    metres, altitude := _altitude(entry)
                ):
                    _LOGGER.debug(
                        "Ignoring the position of %s: %.0f km is further than "
                        "line of sight allows at %s feet",
                        entry.get("hex"),
                        metres / 1000,
                        altitude,
                    )
                    metres = None
                if metres is None:
                    position = None
                else:
                    with_position += 1

            summary = _summarise(entry, metres, position, self.reference)
            if (approach := approach_of(self.origin, summary)) is not None:
                passing, seconds = approach
                if seconds <= APPROACH_HORIZON.total_seconds():
                    summary = replace(
                        summary,
                        approaching=True,
                        closest_passing_distance=passing,
                        seconds_to_closest=seconds,
                    )
            heard.append(summary)

            if (reason := _emergency_reason(entry)) is not None:
                emergencies.append(
                    EmergencyAircraft(
                        hex=str(entry.get("hex", "")),
                        flight=_as_text(entry.get("flight")),
                        squawk=_as_text(entry.get("squawk")),
                        reason=reason,
                        summary=summary,
                    )
                )

            # First matching line wins, so one aircraft is one match.
            squawk = _as_text(entry.get("squawk")) or ""
            for line in self.watchlist:
                if (field := _matches(line, summary, squawk)) is not None:
                    watched.append(
                        WatchlistMatch(
                            entry=line,
                            matched_on=field,
                            summary=summary,
                            squawk=squawk or None,
                        )
                    )
                    break

            # These two include aircraft without a position.
            if summary.altitude is not None and (
                highest_feet is None or summary.altitude > highest_feet
            ):
                highest, highest_feet = summary, summary.altitude
            if summary.speed is not None and (
                fastest_knots is None or summary.speed > fastest_knots
            ):
                fastest, fastest_knots = summary, summary.speed

            if metres is None or position is None:
                continue
            if furthest_metres is None or metres > furthest_metres:
                furthest, furthest_metres = summary, metres
            if closest_metres is None or metres < closest_metres:
                closest, closest_metres = summary, metres
            # The ceiling applies to nearby only, not to reception figures or
            # emergencies; do not move it up.
            if metres <= radius and _under(summary, ceiling):
                nearby.append(summary)

            sector = sector_of(_bearing(origin_latitude, origin_longitude, *position))
            if sector not in sector_metres or metres > sector_metres[sector]:
                by_sector[sector], sector_metres[sector] = summary, metres

        nearby.sort(key=lambda item: item.distance or 0.0)
        now = _as_float(data.get("now"))

        return AircraftStats(
            total=len(aircraft),
            with_position=with_position,
            messages=_as_int(data.get("messages")),
            # Filled in by _count_messages.
            message_rate=None,
            updated=None if now is None else dt_util.utc_from_timestamp(now),
            closest=closest,
            furthest=furthest,
            highest=highest,
            fastest=fastest,
            nearby=tuple(nearby),
            heard=tuple(heard),
            by_sector=by_sector,
            emergencies=tuple(emergencies),
            watched=tuple(watched),
        )

    def _take_message_rate(
        self, messages: int | None, now: float | None
    ) -> float | None:
        """Return the messages per second since the previous poll.

        Consumes the held sample, so call it once per poll.
        """
        if messages is None or now is None:
            return None

        previous = self._previous_messages
        self._previous_messages = (messages, now)
        if previous is None:
            return None

        previous_messages, previous_now = previous
        elapsed = now - previous_now
        # Time or count going backwards means the receiver restarted.
        if elapsed <= 0 or messages < previous_messages:
            return None
        return (messages - previous_messages) / elapsed

    def _build_receiver_stats(self, data: dict[str, Any]) -> ReceiverStats:
        """Turn a raw stats.json document into the figures we expose."""
        period, window = self._pick_period(data)
        local = window.get("local")
        local = local if isinstance(local, dict) else {}

        signal = _as_float(local.get("signal"))
        noise = _as_float(local.get("noise"))
        tracks = window.get("tracks")
        tracks = tracks if isinstance(tracks, dict) else {}

        return ReceiverStats(
            period=period,
            signal=signal,
            noise=noise,
            signal_to_noise=None if signal is None or noise is None else signal - noise,
            peak_signal=_as_float(local.get("peak_signal")),
            strong_signals=_as_int(local.get("strong_signals")),
            samples_dropped=_as_int(local.get("samples_dropped")),
            accepted=_accepted(local.get("accepted")),
            tracks=_as_int(tracks.get("all")),
            single_message_tracks=_as_int(tracks.get("single_message")),
            demodulator_load=_demodulator_load(window),
            # readsb reports the gain once for the document, not per window.
            gain=read_gain(window, data),
            error_rate=_error_rate(local),
            aircraft_by_type=_aircraft_by_type(data),
            frequency_error=_as_float(data.get("estimated_ppm")),
            positions_decoded=_positions(window, ("global_ok", "local_ok")),
            positions_rejected=_positions(
                window, ("global_bad", "global_range", "global_speed")
            ),
        )

    @staticmethod
    def _pick_period(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Return the shortest window that actually measured a signal."""
        fallback: tuple[str, dict[str, Any]] = ("last1min", {})
        for name in STATS_PERIODS:
            window = data.get(name)
            if not isinstance(window, dict):
                continue
            if not fallback[1]:
                fallback = (name, window)
            local = window.get("local")
            if isinstance(local, dict) and local.get("signal") is not None:
                return name, window
        return fallback


def _accepted(value: Any) -> int | None:
    """Return the accepted message count, summed over error-correction levels."""
    if isinstance(value, list):
        counts = [_as_int(item) for item in value]
        return sum(count for count in counts if count is not None)
    return _as_int(value)


def _error_rate(local: dict[str, Any]) -> float | None:
    """Return the share of Mode S messages that failed to decode, in percent.

    None for a minute without messages, rather than a misleading zero.
    """
    total = _as_int(local.get("modes"))
    bad = _as_int(local.get("bad"))
    if total is None or bad is None or total <= 0:
        return None
    return bad / total * 100


def _aircraft_by_type(data: dict[str, Any]) -> dict[str, int]:
    """Return how the decoder came to know about the aircraft it tracks."""
    counts = data.get("aircraft_count_by_type")
    if not isinstance(counts, dict):
        return {}
    grouped: dict[str, int] = {}
    for group, keys in AIRCRAFT_TYPE_GROUPS.items():
        values = [_as_int(counts.get(key)) for key in keys]
        grouped[group] = sum(value for value in values if value is not None)
    return grouped


def _positions(window: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    """Return a sum of position counters out of a window's cpr block."""
    cpr = window.get("cpr")
    if not isinstance(cpr, dict):
        return None
    values = [_as_int(cpr.get(key)) for key in keys]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _demodulator_load(window: dict[str, Any]) -> float | None:
    """Return how much of the window dump1090 spent on the CPU, in percent."""
    cpu = window.get("cpu")
    if not isinstance(cpu, dict):
        return None
    start = _as_float(window.get("start"))
    end = _as_float(window.get("end"))
    if start is None or end is None or end <= start:
        return None

    # The counters are milliseconds of CPU time inside a window of seconds.
    spent = [_as_float(cpu.get(key)) for key in ("demod", "reader", "background")]
    used = sum(value for value in spent if value is not None)
    return used / ((end - start) * 1000) * 100
