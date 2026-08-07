"""Constants for the ADS-B Station integration."""

DOMAIN = "adsb_station"

# Only a station that includes fr24feed is a Flightradar24 device. One that runs
# just a decoder is whatever the user installed, so it gets no manufacturer.
MANUFACTURER = "Flightradar24"
MODEL_FEEDER = "fr24feed"
MODEL_RECEIVER = "ADS-B receiver"
DEFAULT_FEEDER_NAME = "FR24 feeder"
DEFAULT_STATION_NAME = "ADS-B station"

# What receiver.json holds when nothing expanded the placeholder. The dump1090
# fork that fr24feed ships serves it verbatim.
UNSET_RECEIVER_VERSION = "EB_VERSION"

CONF_AIRCRAFT_URL = "aircraft_url"
CONF_STATS_URL = "stats_url"
CONF_RECEIVER_FEATURES = "receiver_features"

# Optional things a receiver may report. Detected once during the config flow,
# so entities for data a decoder never sends are not created at all. Run
# Reconfigure after upgrading the decoder to pick them up.
FEATURE_GAIN = "gain"
# readsb puts these at the root of stats.json; the other decoders send neither.
FEATURE_AIRCRAFT_TYPES = "aircraft_types"
FEATURE_FREQUENCY_ERROR = "frequency_error"
# Position bookkeeping inside a window. The dump1090 fork of fr24feed has none.
FEATURE_POSITIONS = "positions"

# How readsb labels the way it came to know about an aircraft. Reporting all
# fourteen would be noise, so they are summed into the three that say something
# about your reception: heard directly, computed from timing, or bare Mode S.
AIRCRAFT_TYPE_GROUPS: dict[str, tuple[str, ...]] = {
    "adsb": ("adsb_icao", "adsb_icao_nt", "adsb_other"),
    "mlat": ("mlat",),
    "mode_s": ("mode_s",),
}

# Files that sit next to aircraft.json in the same data directory.
STATS_FILENAME = "stats.json"
RECEIVER_FILENAME = "receiver.json"

# Squawk codes that mean the crew is in trouble. dump1090-fa also reports an
# "emergency" field, but the fr24feed fork only gives us the raw squawk.
EMERGENCY_SQUAWKS: dict[str, str] = {
    "7500": "hijack",
    "7600": "radio_failure",
    "7700": "emergency",
}

DEFAULT_PORT = 8754
DEFAULT_AIRCRAFT_PORT = 8080
DEFAULT_HTTP_PORT = 80

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600

# How close an aircraft has to be to count as nearby, in kilometres. Ten is
# roughly the circle you can see and hear from, which is what makes it useful
# for automations; the range of a good receiver is many times that.
CONF_PROXIMITY_RADIUS = "proximity_radius"
DEFAULT_PROXIMITY_RADIUS = 10
MIN_PROXIMITY_RADIUS = 1
MAX_PROXIMITY_RADIUS = 500

# Where aircraft.json lives on the common receiver images, in the order we
# prefer them. fr24feed ships its own dump1090 on port 8080 under /dump1090;
# readsb with tar1090 puts it behind the normal web server on port 80, which is
# where you end up after upgrading the decoder.
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
)

# Keys that identify a genuine fr24feed monitor.json response.
MONITOR_MARKER_KEYS = frozenset(
    {"feed_status", "rx_connected", "feed_alias", "build_version"}
)
