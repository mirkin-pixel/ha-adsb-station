"""Constants for the ADS-B Station integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

DOMAIN = "adsb_station"

CONF_FEEDER_TYPE = "feeder_type"

# The feeders we can read. A station often runs several off one decoder; each
# becomes its own entry and device.
FEEDER_FR24 = "fr24feed"
FEEDER_PIAWARE = "piaware"
FEEDER_PLANEFINDER = "planefinder"


@dataclass(frozen=True, kw_only=True)
class FeederKind:
    """Everything that differs between one feeder and the next."""

    key: str
    port: int
    path: str
    # Keys only this feeder's status document has, to recognise it.
    markers: frozenset[str]
    manufacturer: str
    model: str
    # The device name until the feeder reports a better one.
    default_name: str
    # Where else the search looks: docker-piaware serves 80, adsb.im 8082.
    other_ports: tuple[int, ...] = ()


FEEDERS: dict[str, FeederKind] = {
    FEEDER_FR24: FeederKind(
        key=FEEDER_FR24,
        port=8754,
        path="/monitor.json",
        markers=frozenset({"feed_status", "rx_connected", "feed_alias"}),
        manufacturer="Flightradar24",
        model="fr24feed",
        default_name="FR24 feeder",
    ),
    FEEDER_PIAWARE: FeederKind(
        key=FEEDER_PIAWARE,
        port=8080,
        path="/status.json",
        markers=frozenset({"piaware", "adept", "radio"}),
        manufacturer="FlightAware",
        model="PiAware",
        default_name="PiAware feeder",
        other_ports=(80, 8082),
    ),
    FEEDER_PLANEFINDER: FeederKind(
        key=FEEDER_PLANEFINDER,
        port=30053,
        path="/ajax/stats",
        markers=frozenset(
            {"client_version", "total_modes_packets", "master_server_bytes_out"}
        ),
        manufacturer="Plane Finder",
        model="pfclient",
        default_name="Plane Finder feeder",
    ),
}

MODEL_RECEIVER = "ADS-B receiver"
DEFAULT_STATION_NAME = "ADS-B station"

# The unexpanded placeholder fr24feed's dump1090 fork serves in receiver.json.
UNSET_RECEIVER_VERSION = "EB_VERSION"

CONF_AIRCRAFT_URL = "aircraft_url"
CONF_STATS_URL = "stats_url"
CONF_RECEIVER_FEATURES = "receiver_features"

# Compass sectors for the range records, each 45 degrees centred on its
# direction.
SECTORS: tuple[str, ...] = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

# Optional receiver data, detected in the config flow so no entity is created
# for data the decoder never sends. Reconfigure picks up new ones.
FEATURE_GAIN = "gain"
# Only readsb reports these.
FEATURE_AIRCRAFT_TYPES = "aircraft_types"
FEATURE_FREQUENCY_ERROR = "frequency_error"
# Not in fr24feed's dump1090 fork.
FEATURE_POSITIONS = "positions"

# readsb's fourteen source types, summed into the three that say something
# about reception.
AIRCRAFT_TYPE_GROUPS: dict[str, tuple[str, ...]] = {
    "adsb": ("adsb_icao", "adsb_icao_nt", "adsb_other"),
    "mlat": ("mlat",),
    "mode_s": ("mode_s",),
}

# Traffic categories, tried in this order so each aircraft counts once.
# Military goes first: a military helicopter is military before helicopter.
TRAFFIC_MILITARY = "military"
TRAFFIC_HELICOPTER = "helicopter"
TRAFFIC_AIRLINE = "airline"
TRAFFIC_OTHER = "other"
CATEGORY_ROTORCRAFT = "A7"

# Feet per minute before the map shows an aircraft climbing or descending.
CLIMB_RATE_SHOWN = 500

# Bits of readsb's dbFlags, set only with an aircraft database.
DB_FLAG_MILITARY = 1
DB_FLAG_INTERESTING = 2
DB_FLAG_PIA = 4
DB_FLAG_LADD = 8

# Next to aircraft.json in the same data directory.
STATS_FILENAME = "stats.json"
RECEIVER_FILENAME = "receiver.json"
# readsb's furthest position per degree over the last day, for the map.
OUTLINE_FILENAME = "outline.json"
OUTLINE_INTERVAL = timedelta(minutes=5)

# fr24feed's fork has no "emergency" field, only the squawk.
EMERGENCY_SQUAWKS: dict[str, str] = {
    "7500": "hijack",
    "7600": "radio_failure",
    "7700": "emergency",
}

# Under the squawk's reasons; lifeguard, minfuel and reserved are no distress.
EMERGENCY_STATUSES: dict[str, str] = {
    "general": "emergency",
    "unlawful": "hijack",
    "nordo": "radio_failure",
    "downed": "downed",
}

# Fired once per flight in distress, on the first poll it is heard so.
EVENT_AIRCRAFT_EMERGENCY = f"{DOMAIN}_aircraft_emergency"

DEFAULT_AIRCRAFT_PORT = 8080
DEFAULT_HTTP_PORT = 80
# Where tar1090's installer also serves the map when lighttpd is the web server.
TAR1090_PORT = 8504

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600

# The feeder status and stats.json are per-minute figures, so reading them
# more often only adds recorder rows.
CONF_STATISTICS_INTERVAL = "statistics_interval"
DEFAULT_STATISTICS_INTERVAL = 60

# Nearby radius in km. Ten is roughly what you can see and hear.
CONF_PROXIMITY_RADIUS = "proximity_radius"
DEFAULT_PROXIMITY_RADIUS = 10
MIN_PROXIMITY_RADIUS = 1
MAX_PROXIMITY_RADIUS = 500

# Optional ceiling in feet for nearby, overhead and passages, so an airliner
# at cruise inside the radius does not count. Unset by default.
CONF_PROXIMITY_MAX_ALTITUDE = "proximity_max_altitude"
MAX_PROXIMITY_ALTITUDE = 60000

# An entity per nearby aircraft on the map. Off by default: the sensors carry
# the same data.
CONF_MAP_AIRCRAFT = "map_aircraft"
DEFAULT_MAP_AIRCRAFT = False

# Fired once per aircraft crossing the radius.
EVENT_AIRCRAFT_PASSAGE = f"{DOMAIN}_aircraft_passage"

# How long an aircraft must be gone before returning counts as a new passage,
# so one flickering on the edge does not fire every poll.
PASSAGE_GAP = timedelta(minutes=10)

# No samples for this long means the dongle is gone: a restarting decoder is
# back within a minute. Messages cannot tell, a quiet night has none for long.
RECEIVER_SILENT_AFTER = timedelta(minutes=3)

# Missed reads in a row before entities go unavailable. One blip should not
# leave a gap in graphs or re-trigger automations.
MISSED_READS_TOLERATED = 2

# Aircraft to watch for anywhere in range, one per line.
CONF_WATCHLIST = "watchlist"
EVENT_WATCHLIST_MATCH = f"{DOMAIN}_watchlist_match"
# Once it has been out of range for the gap, with how long it was in it.
EVENT_WATCHLIST_LOST = f"{DOMAIN}_watchlist_lost"

# What a watchlist line can be. A name is compared against both registration
# and callsign, since N123AB could be either. Anything else is refused.
WATCHLIST_HEX = "hex"
WATCHLIST_SQUAWK = "squawk"
WATCHLIST_TYPE = "aircraft_type"
WATCHLIST_NAME = "name"

# Passages kept on the board, written whole to the recorder on each arrival.
PASSAGE_BOARD_LENGTH = 20

FEET_TO_METRES = 0.3048
KNOTS_TO_METRES_PER_SECOND = 0.514444
# Length of a degree of latitude.
DEGREE_METRES = 111_320.0
EARTH_RADIUS_METRES = 6_371_000.0

# Approach predictions assume a straight line at constant speed; these limits
# keep that guess from being announced as fact.
EVENT_AIRCRAFT_APPROACHING = f"{DOMAIN}_aircraft_approaching"
# Beyond a few minutes an aircraft may have turned or descended.
APPROACH_HORIZON = timedelta(minutes=5)
# Polls that must agree, so one mis-decoded heading announces nothing.
APPROACH_POLLS = 2

# Radio horizon: the furthest a position at a given height can be believed.
# A mis-decoded position would otherwise set a sector record for good. The
# allowance covers an antenna up to about 350 m above its surroundings.
RADIO_HORIZON_METRES_PER_ROOT_FOOT = 2278.0
RADIO_HORIZON_ALLOWANCE = 80_000
# The same limit for aircraft that report no height.
MAX_PLAUSIBLE_RANGE = 700_000

# The altitude every decoder reports for an aircraft on the ground.
GROUND_ALTITUDE = "ground"

# receiver.json never changes while the decoder runs, but one timeout should
# not decide where every range is measured from.
RECEIVER_READ_ATTEMPTS = 5

# Routes come from an outside service, so they are off unless switched on.
CONF_LOOK_UP_ROUTES = "look_up_routes"
DEFAULT_LOOK_UP_ROUTES = False

# Since October 2026 adsb.im accepts unapproved clients only over http, with a
# User-Agent and at most one request every thirty seconds.
ROUTESET_URL = "http://adsb.im/api/0/routeset"
ROUTESET_MIN_INTERVAL = timedelta(seconds=30)
ROUTESET_MAX_PLANES = 100

# A route holds for the day. A miss is kept shorter: the database may catch up.
ROUTE_CACHE_TTL = timedelta(hours=12)
ROUTE_MISS_CACHE_TTL = timedelta(hours=1)
ROUTE_CACHE_MAX_ENTRIES = 512
# So a busy sky cannot turn into a burst of requests.
ROUTE_MAX_LOOKUPS_PER_POLL = 25

# Photos come from an outside service too, so they are off by default.
CONF_LOOK_UP_PHOTOS = "look_up_photos"
DEFAULT_LOOK_UP_PHOTOS = False

PHOTO_URL = "https://api.planespotters.net/pub/photos/hex/{hex}"
# Planespotters and routeset refuse requests that do not say who is asking.
USER_AGENT = "ADS-B-Station (+https://github.com/mirkin-pixel/ha-adsb-station)"
PHOTO_USER_AGENT = USER_AGENT
# A day is as long as Planespotters' terms allow an answer to be kept.
PHOTO_CACHE_TTL = timedelta(hours=24)
PHOTO_CACHE_MAX_ENTRIES = 512
# One request per aircraft, so fewer than routes, which batch.
PHOTO_MAX_LOOKUPS_PER_POLL = 3

# Where the common receiver images serve aircraft.json, in order of preference.
AIRCRAFT_URL_CANDIDATES: tuple[tuple[int, str], ...] = (
    (DEFAULT_AIRCRAFT_PORT, "/dump1090/data/aircraft.json"),
    (DEFAULT_AIRCRAFT_PORT, "/data/aircraft.json"),
    (DEFAULT_AIRCRAFT_PORT, "/tar1090/data/aircraft.json"),
    (DEFAULT_HTTP_PORT, "/tar1090/data/aircraft.json"),
    (DEFAULT_HTTP_PORT, "/data/aircraft.json"),
    (DEFAULT_AIRCRAFT_PORT, "/skyaware/data/aircraft.json"),
    (DEFAULT_AIRCRAFT_PORT, "/dump1090-fa/data/aircraft.json"),
    (DEFAULT_HTTP_PORT, "/skyaware/data/aircraft.json"),
    (DEFAULT_HTTP_PORT, "/dump1090-fa/data/aircraft.json"),
    (DEFAULT_HTTP_PORT, "/dump1090/data/aircraft.json"),
    (TAR1090_PORT, "/data/aircraft.json"),
)
