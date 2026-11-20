/*
 * ADS-B Station card, served by the integration on every dashboard.
 *
 * Entities are found by translation key, not by their language-dependent IDs.
 * The sky comes over a websocket subscription while the card is open. Plain
 * JavaScript with no build step, so the repository is exactly what runs.
 */

const DOMAIN = "adsb_station";
const CARD = "adsb-station-card";
const TABLE_CARD = "adsb-station-table-card";
const SUBSCRIBE = `${DOMAIN}/subscribe_aircraft`;
const LOOK_UP_ROUTE = `${DOMAIN}/look_up_route`;
const LOOK_UP_PHOTO = `${DOMAIN}/look_up_photo`;
const SVG = "http://www.w3.org/2000/svg";

const STRINGS = {
  en: {
    name: "ADS-B Station",
    description:
      "The sky around the station, the aircraft overhead with its photo, the others nearby, and how the station is doing.",
    overhead: "Overhead now",
    last_overhead: "Last overhead",
    nothing: "Nothing overhead right now",
    no_station: "No ADS-B station with a receiver was found.",
    nearby: "Also nearby",
    on_ground: "on the ground",
    photo: "Photo",
    received: "received",
    station: "Station",
    coverage: "furthest heard",
    coverage_day: "furthest heard, last 24 h",
    no_positions: "No aircraft with a position",
    compass: ["N", "E", "S", "W"],
    sky: "Aircraft around the station",
    show_nearby: "Show the aircraft nearby",
    show_airports: "Show the airports",
    max_nearby: "How many nearby to show at most",
    show_status: "Show how the station is doing",
    table_name: "ADS-B Station table",
    table_description: "Every aircraft the station has a position for, to sort and search.",
    search: "Search flight, registration or type",
    title_passages: "Passages today",
    title_aircraft: "Aircraft received",
    col_flight: "Flight",
    col_speed: "Speed",
    col_altitude: "Height",
    col_distance: "Distance",
    col_bearing: "Direction",
    col_type: "Type",
    col_rssi: "Signal (dBFS)",
    col_at: "Time",
    col_duration: "In view",
    list: "Show",
    list_now: "What is in the air now",
    list_passages: "What came over today",
    no_passages: "Nothing has come over yet today",
    closest: "Closest",
    strongest: "Strongest signal",
    close: "Close",
    watched: "On your watchlist",
    emergency: "Emergency",
    hijack: "Hijack",
    radio_failure: "Emergency: radio failure",
    downed: "Emergency: downed",
    title: "Title",
    map: "Map",
    map_radar: "Radar",
    map_streets: "Map with streets",
    map_none: "No map",
    map_scale: "Radar scale",
    scale_aircraft: "Automatic, to fit the aircraft",
    scale_coverage: "Automatic, to fit the range records",
    scale_fixed: "Fixed",
    map_range: "Fixed range, in the station's units",
    max_altitude: "Highest altitude shown, in the station's units",
    palette: "Height colours",
    palette_default: "Rainbow, as tar1090",
    palette_colorblind: "Yellow to blue, for colour blindness",
    kind_airline: "Airline",
    kind_other: "Other",
    kind_helicopter: "Helicopter",
    kind_military: "Military",
    no_position: "No position",
    no_position_hint: "Received, but not on the radar: heard without a position, or with an impossible one",
    class_A1: "Light aircraft",
    class_A2: "Small aircraft",
    class_A3: "Large aircraft",
    class_A4: "Large aircraft",
    class_A5: "Heavy aircraft",
    class_A6: "High performance aircraft",
    class_A7: "Helicopter",
    class_B1: "Glider",
    class_B2: "Balloon",
    class_B3: "Parachutist",
    class_B4: "Ultralight",
    class_B6: "Drone",
    class_B7: "Spacecraft",
    class_C1: "Emergency vehicle",
    class_C2: "Service vehicle",
    wind: "wind",
    roll: "roll",
    route_pending: "Looking up the route…",
    route_unknown: "No route known",
    route_failed: "Could not look up the route",
    passes: "Passes {distance} away in {time}",
    watch: "Add to watchlist",
    watch_failed: "Could not add it",
  },
  nl: {
    name: "ADS-B Station",
    description:
      "De lucht rond het station, het vliegtuig overhead met foto, de andere dichtbij, en hoe het station ervoor staat.",
    overhead: "Nu overhead",
    last_overhead: "Laatst overhead",
    nothing: "Er is nu niets overhead",
    no_station: "Er is geen ADS-B-station met een ontvanger gevonden.",
    nearby: "Ook dichtbij",
    on_ground: "aan de grond",
    photo: "Foto",
    received: "ontvangen",
    station: "Station",
    coverage: "verst gehoord",
    coverage_day: "verst gehoord, laatste 24 uur",
    no_positions: "Geen toestellen met een positie",
    compass: ["N", "O", "Z", "W"],
    sky: "Toestellen rond het station",
    show_nearby: "Toestellen dichtbij tonen",
    show_airports: "Luchthavens tonen",
    max_nearby: "Hoeveel toestellen dichtbij maximaal",
    show_status: "Tonen hoe het station ervoor staat",
    table_name: "ADS-B Station tabel",
    table_description: "Elk toestel waarvan het station een positie heeft, om te sorteren en te doorzoeken.",
    search: "Zoek vlucht, registratie of type",
    title_passages: "Passages vandaag",
    title_aircraft: "Ontvangen toestellen",
    col_flight: "Vlucht",
    col_speed: "Snelheid",
    col_altitude: "Hoogte",
    col_distance: "Afstand",
    col_bearing: "Richting",
    col_type: "Type",
    col_rssi: "Signaal (dBFS)",
    col_at: "Tijd",
    col_duration: "In beeld",
    list: "Tonen",
    list_now: "Wat er nu in de lucht is",
    list_passages: "Wat er vandaag overkwam",
    no_passages: "Er is vandaag nog niets overgekomen",
    closest: "Dichtstbij",
    strongest: "Sterkste signaal",
    close: "Sluiten",
    watched: "Op je watchlist",
    emergency: "Noodgeval",
    hijack: "Kaping",
    radio_failure: "Noodgeval: radiostoring",
    downed: "Noodgeval: neergestort",
    title: "Titel",
    map: "Kaart",
    map_radar: "Radar",
    map_streets: "Landkaart",
    map_none: "Geen kaart",
    map_scale: "Schaal van de radar",
    scale_aircraft: "Automatisch, passend bij de toestellen",
    scale_coverage: "Automatisch, passend bij de bereikrecords",
    scale_fixed: "Vast",
    map_range: "Vast bereik, in de eenheden van het station",
    max_altitude: "Hoogste getoonde hoogte, in de eenheden van het station",
    palette: "Kleuren voor de hoogte",
    palette_default: "Regenboog, zoals tar1090",
    palette_colorblind: "Geel naar blauw, voor kleurenblindheid",
    kind_airline: "Lijnvlucht",
    kind_other: "Overig",
    kind_helicopter: "Helikopter",
    kind_military: "Militair",
    no_position: "Zonder positie",
    no_position_hint: "Ontvangen, maar niet op de radar: gehoord zonder positie, of met een onmogelijke",
    class_A1: "Licht vliegtuig",
    class_A2: "Klein vliegtuig",
    class_A3: "Groot vliegtuig",
    class_A4: "Groot vliegtuig",
    class_A5: "Zwaar vliegtuig",
    class_A6: "Snel, wendbaar toestel",
    class_A7: "Helikopter",
    class_B1: "Zweefvliegtuig",
    class_B2: "Ballon",
    class_B3: "Parachutist",
    class_B4: "Ultralicht",
    class_B6: "Drone",
    class_B7: "Ruimtevaartuig",
    class_C1: "Hulpvoertuig",
    class_C2: "Dienstvoertuig",
    wind: "wind",
    roll: "rolhoek",
    route_pending: "Route opzoeken…",
    route_unknown: "Geen route bekend",
    route_failed: "Route opzoeken mislukt",
    passes: "Komt op {distance} langs, over {time}",
    watch: "Op watchlist zetten",
    watch_failed: "Toevoegen mislukt",
  },
};

// Climbing or descending faster than this, in feet per minute, gets an arrow.
// The same line the map icons draw.
const CLIMB_RATE_SHOWN = 500;
const DEFAULT_MAX_NEARBY = 5;
const MAP_STYLES = ["radar", "map", "none"];

// A trail goes with its aircraft at once, or it would end in nothing.
const TRAIL_SECONDS = 300;
// Between polls each aircraft flies on along its track, redrawn every second,
// but no further than this past the last sky, in case no more come.
const FLY_ON_SECONDS = 30;
// Where a callsign may go, in turn: right above an aircraft, right below,
// left above, left below; true where it ends at the aircraft.
const LABEL_SPOTS = [
  [12, -8, false],
  [12, 16, false],
  [-12, -8, true],
  [-12, 16, true],
];
// As far ahead as the integration foresees an approach.
const HEADING_SECONDS = 300;
// Wider than this, only the large airports, or the radar is all dots.
const ALL_AIRPORTS_KM = 200;
// After "no route", a later tap asks again; the integration caches the miss.
const ROUTE_RETRY_SECONDS = 60;
// The integration answers within forty seconds; after this the answer is lost.
const ROUTE_WAIT_SECONDS = 60;
// The radar's outer ring snaps to one of these, in kilometres, unless it is
// fixed: to the aircraft in the sky now, or to the range records as well.
// Up to 700 km, the furthest the integration believes a position at all.
const RANGE_STEPS = [5, 10, 25, 50, 100, 150, 200, 300, 400, 500, 600, 700];
const FURTHEST_KM = 700;
// tar1090's three: per unit shown, how many of it in one of what the
// integration sends (feet, knots, kilometres), and the legend's heights.
const UNIT_SYSTEMS = {
  nautical: { height: ["ft", 1], speed: ["kt", 1], distance: ["NM", 1 / 1.852], ticks: [0, 15000, 30000, 45000] },
  metric: { height: ["m", 0.3048], speed: ["km/h", 1.852], distance: ["km", 1], ticks: [0, 4000, 8000, 12000] },
  imperial: {
    height: ["ft", 1],
    speed: ["mph", 1.150779],
    distance: ["mi", 1 / 1.609344],
    ticks: [0, 15000, 30000, 45000],
  },
};
// The integration names its distance unit beside the figures it sends.
const SYSTEM_BY_DISTANCE = { nmi: "nautical", km: "metric", mi: "imperial" };
const SCALES = ["aircraft", "coverage", "fixed"];
// What the table card lists: the sky now, or the passage board.
const LISTS = ["now", "passages"];
// The traffic counters' kinds, to show or hide on the radar.
const KINDS = ["airline", "other", "helicopter", "military"];
const DEFAULT_FIXED_RANGE = 100;
// From this width the sky and the rest stand side by side; up to the other,
// the table drops its less needed columns.
const SIDE_BY_SIDE = 720;
const NARROW = 480;
// The compass sectors the station keeps a range record for, clockwise from
// north, each centred on its direction.
const SECTORS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"];
const KILOMETRES = { km: 1, m: 0.001, mi: 1.609344, ft: 0.0003048, nmi: 1.852 };

// Warm and low to cool and high, in steps that follow the phases of a flight.
const ALTITUDE_TOP = 45000;
const ALTITUDE_HUES = [
  [0, 8],
  [1500, 28],
  [4000, 48],
  [8000, 95],
  [15000, 160],
  [25000, 210],
  [35000, 262],
  [45000, 305],
];
const GROUND_COLOR = "#8c8c8c";
const PALETTES = ["default", "colorblind"];
// Yellow low to blue high, every 5,000 ft: the one axis red and green blind
// eyes still tell apart. Mixed in OKLab, so its steps look even.
const COLORBLIND = [
  [255, 210, 63],
  [234, 203, 101],
  [212, 195, 127],
  [191, 187, 147],
  [170, 178, 163],
  [149, 169, 178],
  [127, 159, 191],
  [106, 148, 203],
  [84, 136, 214],
  [61, 123, 224],
];

// Pointing north in a 24 box around the origin, turned to the track.
const SHAPES = {
  jet:
    "M0,-11 L1.5,-8 L1.5,-3 L10,2 L10,4 L1.5,1.5 L1,7 L4,9.5 L4,11 L0,10 " +
    "L-4,11 L-4,9.5 L-1,7 L-1.5,1.5 L-10,4 L-10,2 L-1.5,-3 L-1.5,-8 Z",
  light:
    "M0,-10 L1.2,-7 L1.2,-4 L11,-3.5 L11,-1.5 L1.2,-1 L0.8,6 L4,7.5 L4,9 " +
    "L0,8.5 L-4,9 L-4,7.5 L-0.8,6 L-1.2,-1 L-11,-1.5 L-11,-3.5 L-1.2,-4 L-1.2,-7 Z",
  helicopter:
    "M-11,-1.6 L11,1.6 L11,2.4 L-11,-0.8 Z M-1,-12 L1,-12 L1,9 L-1,9 Z " +
    "M0,-6 C3,-6 3.5,-2 3.5,0 C3.5,3 2,5 1,6 L0.8,11 L3,12 L3,13 L-3,13 " +
    "L-3,12 L-0.8,11 L-1,6 C-2,5 -3.5,3 -3.5,0 C-3.5,-2 -3,-6 0,-6 Z",
};

function strings(hass) {
  const language = (hass && hass.locale && hass.locale.language) || "en";
  return STRINGS[language.split("-")[0]] || STRINGS.en;
}

function el(tag, attributes, ...children) {
  // Never innerHTML: the text comes from aircraft and other servers.
  const node = document.createElement(tag);
  return fill(node, attributes, children);
}

function svg(tag, attributes, ...children) {
  return fill(document.createElementNS(SVG, tag), attributes, children);
}

// OpenStreetMap has no dark tiles, so they are inverted for a dark theme, as
// Home Assistant's map does: invert(1) hue-rotate(180deg) brightness(0.95)
// contrast(0.9), written as SVG filter primitives because WebKit ignores CSS
// filters on elements inside an SVG (bugs.webkit.org/show_bug.cgi?id=246106).
function darkTiles() {
  const channel = (c, attributes) => svg(`feFunc${c}`, attributes);
  return svg(
    "filter",
    { id: "dark", "color-interpolation-filters": "sRGB" },
    svg(
      "feComponentTransfer",
      {},
      ["R", "G", "B"].map((c) => channel(c, { type: "table", tableValues: "1 0" })),
    ),
    svg("feColorMatrix", { type: "hueRotate", values: 180 }),
    svg(
      "feComponentTransfer",
      {},
      ["R", "G", "B"].map((c) => channel(c, { type: "linear", slope: 0.855, intercept: 0.05 })),
    ),
  );
}

function fill(node, attributes, children) {
  for (const [key, value] of Object.entries(attributes || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.setAttribute("class", value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  // A clickable element that is not a real button answers Enter and Space too.
  if (attributes?.role === "button" && attributes.onclick && !attributes.onkeydown) {
    node.addEventListener("keydown", (event) => {
      if (event.target !== node || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      attributes.onclick(event);
    });
  }
  for (const child of children.flat()) {
    if (child === undefined || child === null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function aircraftIcon(aircraft) {
  if (aircraft.category === "A7") return "mdi:helicopter";
  if (aircraft.military) return "mdi:shield-airplane";
  const rate = aircraft.vertical_rate;
  if (typeof rate === "number" && rate >= CLIMB_RATE_SHOWN) return "mdi:airplane-takeoff";
  if (typeof rate === "number" && rate <= -CLIMB_RATE_SHOWN) return "mdi:airplane-landing";
  return "mdi:airplane";
}

// Where an aircraft is after flying on for this many seconds.
function flownOn(plane, seconds) {
  const { speed, track, latitude, longitude } = plane;
  if (plane.on_ground || typeof speed !== "number" || typeof track !== "number") return plane;
  const km = (speed * 1.852 * Math.min(Math.floor(seconds), FLY_ON_SECONDS)) / 3600;
  if (!km) return plane;
  const way = (track * Math.PI) / 180;
  return {
    ...plane,
    latitude: latitude + (km * Math.cos(way)) / 111.32,
    longitude: longitude + (km * Math.sin(way)) / (111.32 * Math.cos((latitude * Math.PI) / 180)),
  };
}

// The picked aircraft's line some minutes on, and the point on it nearest the
// station while it still comes: the integration's own straight line.
function headingOf(plane, origin, elapsed) {
  const { speed, track, latitude, longitude } = plane;
  if (plane.on_ground || !(speed > 0) || typeof track !== "number") return null;
  const way = (track * Math.PI) / 180;
  const perLon = 111.32 * Math.cos((origin[0] * Math.PI) / 180);
  const at = (km) => [latitude + (km * Math.cos(way)) / 110.574, longitude + (km * Math.sin(way)) / perLon];
  const left = plane.seconds_to_closest - elapsed;
  let closest = null;
  if (plane.approaching && left > 0) {
    const east = lonDelta(longitude, origin[1]) * perLon;
    const north = (latitude - origin[0]) * 110.574;
    closest = at(-(east * Math.sin(way) + north * Math.cos(way)));
  }
  return { end: at((speed * 1.852 * HEADING_SECONDS) / 3600), closest };
}

// Distress first, then the watchlist: what makes an aircraft stand out.
// How long a passage was in view.
const minutes = (seconds) => (seconds < 60 ? `${seconds} s` : `${Math.round(seconds / 60)} min`);
const mark = (plane) => (plane.emergency ? "distress" : plane.watched ? "watch" : null);

function altitudeColor(altitude, onGround, palette) {
  if (onGround || typeof altitude !== "number") return GROUND_COLOR;
  if (palette === "colorblind") {
    const at = (Math.min(Math.max(altitude, 0), ALTITUDE_TOP) / ALTITUDE_TOP) * (COLORBLIND.length - 1);
    const i = Math.min(Math.floor(at), COLORBLIND.length - 2);
    const [low, high] = [COLORBLIND[i], COLORBLIND[i + 1]];
    return `rgb(${low.map((value, j) => Math.round(value + (at - i) * (high[j] - value))).join(", ")})`;
  }
  let hue = ALTITUDE_HUES[ALTITUDE_HUES.length - 1][1];
  for (let i = 1; i < ALTITUDE_HUES.length; i++) {
    const [top, topHue] = ALTITUDE_HUES[i];
    if (altitude <= top) {
      const [bottom, bottomHue] = ALTITUDE_HUES[i - 1];
      const share = Math.max(0, (altitude - bottom) / (top - bottom));
      hue = bottomHue + share * (topHue - bottomHue);
      break;
    }
  }
  return `hsl(${Math.round(hue)}, 80%, 52%)`;
}

// The points along the shortest way over the earth between two places, which
// is the way an airliner flies: on a map a long route bows towards the pole.
function greatCircle(from, to, steps = 48) {
  const radians = (degrees) => (degrees * Math.PI) / 180;
  const degrees = (value) => (value * 180) / Math.PI;
  const toVector = ([lat, lon]) => [
    Math.cos(radians(lat)) * Math.cos(radians(lon)),
    Math.cos(radians(lat)) * Math.sin(radians(lon)),
    Math.sin(radians(lat)),
  ];
  const a = toVector(from);
  const b = toVector(to);
  const angle = Math.acos(Math.min(1, Math.max(-1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
  if (angle < 1e-9) return [from, to];
  const points = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const k1 = Math.sin((1 - t) * angle) / Math.sin(angle);
    const k2 = Math.sin(t * angle) / Math.sin(angle);
    const [x, y, z] = [0, 1, 2].map((axis) => k1 * a[axis] + k2 * b[axis]);
    points.push([degrees(Math.atan2(z, Math.hypot(x, y))), degrees(Math.atan2(y, x))]);
  }
  return points;
}

function shapeOf(aircraft) {
  const category = aircraft.category || "";
  if (category === "A7") return { path: SHAPES.helicopter, scale: 0.9 };
  if (category === "A1" || category.startsWith("B")) return { path: SHAPES.light, scale: 0.85 };
  if (category === "A5") return { path: SHAPES.jet, scale: 1.2 };
  return { path: SHAPES.jet, scale: 1 };
}

// Only https addresses become links or images.
function safeUrl(value) {
  return typeof value === "string" && value.startsWith("https://") ? value : null;
}

function numeric(state) {
  if (!state) return null;
  const value = Number.parseFloat(state.state);
  return Number.isFinite(value) ? value : null;
}

// OpenStreetMap's own data through Home Assistant's proxy since 2026.9, the
// same tiles its own map draws. Drawn here in the theme's colours, and only
// what helps place an aircraft: water, borders, main roads and towns.
const PROXY_VECTOR = (z, x, y) => `/api/map_tiles/vector/${z}/${x}/${y}.mvt`;
const MAX_VECTOR_ZOOM = 14;
const VECTOR_RETRY = 60 * 1000;
const VECTOR_CACHE = 64;
const ROADS = new Set(["trunk", "primary"]);
const RIVERS = new Set(["river", "canal"]);
const PLACE_RANK = { capital: 0, state_capital: 1, city: 2, town: 3, village: 4 };
const MAX_PLACE_NAMES = 30;
// Layers of one tile come in different extents; all are drawn in this one.
const BASEMAP_EXTENT = 4096;

// A Mapbox vector tile, as far as drawing it needs: each layer's features with
// their properties and geometry. Protocol Buffers by hand: no build step.
function decodeTile(bytes) {
  let pos = 0;
  const varint = () => {
    let result = 0;
    let shift = 0;
    let byte;
    do {
      byte = bytes[pos++];
      result += (byte & 0x7f) * 2 ** shift;
      shift += 7;
    } while (byte & 0x80);
    return result;
  };
  const skip = (wire) => {
    if (wire === 0) varint();
    else if (wire === 1) pos += 8;
    else if (wire === 2) pos += varint();
    else if (wire === 5) pos += 4;
    else throw new Error(`wire type ${wire}`);
  };
  const string = () => {
    const end = varint() + pos;
    const value = new TextDecoder().decode(bytes.subarray(pos, end));
    pos = end;
    return value;
  };
  const packed = () => {
    const end = varint() + pos;
    const values = [];
    while (pos < end) values.push(varint());
    return values;
  };
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const value = () => {
    const end = varint() + pos;
    let result = null;
    while (pos < end) {
      const tag = varint();
      const field = tag >> 3;
      if (field === 1) result = string();
      else if (field === 2) {
        result = view.getFloat32(pos, true);
        pos += 4;
      } else if (field === 3) {
        result = view.getFloat64(pos, true);
        pos += 8;
      } else if (field === 4 || field === 5) result = varint();
      else if (field === 6) result = zigzag(varint());
      else if (field === 7) result = Boolean(varint());
      else skip(tag & 7);
    }
    return result;
  };
  const layers = {};
  while (pos < bytes.length) {
    const tag = varint();
    // Field 3, length-delimited: a layer. Nothing else is at the top.
    if (tag !== 0x1a) {
      skip(tag & 7);
      continue;
    }
    const end = varint() + pos;
    const layer = { extent: 4096, keys: [], values: [], features: [] };
    let name = "";
    while (pos < end) {
      const inner = varint();
      const field = inner >> 3;
      if (field === 1) name = string();
      else if (field === 2) {
        const stop = varint() + pos;
        const feature = { tags: [], geometry: [] };
        while (pos < stop) {
          const part = varint();
          if (part >> 3 === 2) feature.tags = packed();
          else if (part >> 3 === 4) feature.geometry = packed();
          else skip(part & 7);
        }
        layer.features.push(feature);
      } else if (field === 3) layer.keys.push(string());
      else if (field === 4) layer.values.push(value());
      else if (field === 5) layer.extent = varint();
      else skip(inner & 7);
    }
    for (const feature of layer.features) {
      feature.properties = {};
      for (let i = 0; i + 1 < feature.tags.length; i += 2) {
        feature.properties[layer.keys[feature.tags[i]]] = layer.values[feature.tags[i + 1]];
      }
    }
    layers[name] = layer;
  }
  return layers;
}

function zigzag(n) {
  return n % 2 ? -(n + 1) / 2 : n / 2;
}

// A feature's geometry as SVG path data, scaled to BASEMAP_EXTENT.
function pathData(geometry, factor) {
  let x = 0;
  let y = 0;
  let d = "";
  for (let i = 0; i < geometry.length;) {
    const command = geometry[i] & 7;
    const count = geometry[i++] >> 3;
    if (command === 7) {
      d += "Z";
      continue;
    }
    for (let n = 0; n < count && i + 1 < geometry.length; n++) {
      x += zigzag(geometry[i++]);
      y += zigzag(geometry[i++]);
      d += `${command === 1 ? "M" : n === 0 ? "L" : " "}${x * factor} ${y * factor}`;
    }
  }
  return d;
}

// What of a decoded tile gets drawn: one path per kind of line or area, so a
// tile is a handful of elements, and the places that may get a name.
function basemapTile(layers) {
  const paths = { water: "", river: "", road: "", motorway: "", state: "", country: "" };
  const each = (name, draw) => {
    const layer = layers[name];
    if (!layer) return;
    const factor = BASEMAP_EXTENT / (layer.extent || BASEMAP_EXTENT);
    for (const feature of layer.features) draw(feature, factor);
  };
  const water = (feature, factor) => (paths.water += pathData(feature.geometry, factor));
  each("ocean", water);
  each("water_polygons", water);
  each("water_lines", (feature, factor) => {
    if (RIVERS.has(feature.properties.kind)) paths.river += pathData(feature.geometry, factor);
  });
  each("streets", (feature, factor) => {
    const kind = feature.properties.kind;
    if (kind === "motorway") paths.motorway += pathData(feature.geometry, factor);
    else if (ROADS.has(kind)) paths.road += pathData(feature.geometry, factor);
  });
  each("boundaries", (feature, factor) => {
    if (feature.properties.maritime) return;
    const level = Number(feature.properties.admin_level);
    if (level === 2) paths.country += pathData(feature.geometry, factor);
    else if (level === 4) paths.state += pathData(feature.geometry, factor);
  });
  const places = [];
  each("place_labels", (feature, factor) => {
    const { name, kind, population } = feature.properties;
    if (!name || !(kind in PLACE_RANK) || feature.geometry.length < 3) return;
    places.push({
      name,
      rank: PLACE_RANK[kind],
      population: Number(population) || 0,
      x: zigzag(feature.geometry[1]) * factor,
      y: zigzag(feature.geometry[2]) * factor,
    });
  });
  return { extent: BASEMAP_EXTENT, paths: Object.entries(paths).filter(([, d]) => d), places };
}

// The biggest places first; a name that would cover an aircraft, its
// callsign or a name already placed, or run off the map, is left off.
function placeNames(places, size, avoid) {
  const taken = [...avoid];
  const seen = new Set();
  const names = [];
  for (const place of places) {
    if (names.length >= MAX_PLACE_NAMES || seen.has(place.name)) continue;
    const half = (place.name.length * 5.6 + 6) / 2;
    const box = [place.x - half, place.y - 7, place.x + half, place.y + 7];
    if (box[0] < 0 || box[1] < 0 || box[2] > size || box[3] > size) continue;
    if (taken.some((t) => box[0] < t[2] && box[2] > t[0] && box[1] < t[3] && box[3] > t[1])) continue;
    seen.add(place.name);
    taken.push(box);
    const attributes = { class: place.rank <= 2 ? "place big" : "place", x: place.x.toFixed(1), y: place.y.toFixed(1) };
    names.push(svg("text", attributes, place.name));
  }
  return names;
}

// Web Mercator, at a fractional zoom: tiles of the level below are scaled up.
const TILE_SIZE = 256;
const EQUATOR_METRES_PER_PIXEL = 156543.03392;
// OpenStreetMap's raster tiles stop here.
const MAX_TILE_ZOOM = 19;
// Through Home Assistant's tile proxy since 2026.9, with a token valid half an
// hour; before that, straight from OpenStreetMap.
const PROXY_TILES = (z, x, y, token) => `/api/map_tiles/raster/${z}/${x}/${y}.png?token=${encodeURIComponent(token)}`;
const UPSTREAM_TILES = (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`;
const TOKEN_REFRESH = 20 * 60 * 1000;

// Degrees east of a longitude, folded into -180 to 180 across the date line.
function lonDelta(lon, from) {
  return ((((lon - from) % 360) + 540) % 360) - 180;
}

function mercatorView(origin, range, reach, centre, size) {
  const [latitude, longitude] = origin;
  const shrink = Math.cos((latitude * Math.PI) / 180);
  const zoom = Math.min(
    MAX_TILE_ZOOM,
    Math.max(1, Math.log2((EQUATOR_METRES_PER_PIXEL * shrink * reach) / (range * 1000))),
  );
  const world = TILE_SIZE * 2 ** zoom;
  const toWorld = (lat, lon) => {
    const phi = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
    return [((lon + 180) / 360) * world, ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * world];
  };
  const [cx, cy] = toWorld(latitude, longitude);
  const project = (lat, lon) => {
    const [x, y] = toWorld(lat, longitude + lonDelta(lon, longitude));
    return [centre + x - cx, centre + y - cy];
  };
  const perKm = 1000 / ((EQUATOR_METRES_PER_PIXEL * shrink) / 2 ** zoom);

  // Every tile of a level that the view shows, with where it goes and how big.
  const grid = (level) => {
    const side = TILE_SIZE * 2 ** (zoom - level);
    const count = 2 ** level;
    const left = cx - centre;
    const top = cy - centre;
    const found = [];
    for (let ty = Math.floor(top / side); ty <= Math.floor((top + size) / side); ty++) {
      if (ty < 0 || ty >= count) continue;
      for (let tx = Math.floor(left / side); tx <= Math.floor((left + size) / side); tx++) {
        const x = ((tx % count) + count) % count;
        found.push({ z: level, x, y: ty, left: tx * side - left, top: ty * side - top, side });
      }
    }
    return found;
  };
  // One level deeper than the zoom, drawn smaller, so the map stays sharp on
  // a screen with more pixels than points: there are no @2x tiles.
  const tiles = (url) =>
    grid(Math.min(MAX_TILE_ZOOM, Math.floor(zoom) + 1)).map((tile) => ({
      href: url(tile.z, tile.x, tile.y),
      // A hair larger than the tile, so no seam shows between two.
      x: +tile.left.toFixed(2),
      y: +tile.top.toFixed(2),
      size: +(tile.side + 0.5).toFixed(2),
    }));
  // A level above the zoom, as vector maps do: its tiles hold what fits that
  // scale, and lines stay sharp however large they are drawn.
  const vectorTiles = () => grid(Math.max(0, Math.min(MAX_VECTOR_ZOOM, Math.floor(zoom) - 1)));
  return { perKm, project, tiles, vectorTiles, size, key: `${zoom}|${cx}|${cy}` };
}

class AdsbStationCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    const text = strings(window.__adsbStationHass);
    return {
      schema: [
        { name: "device_id", selector: { device: { integration: DOMAIN } } },
        { name: "title", selector: { text: {} } },
        {
          name: "map",
          selector: {
            select: {
              mode: "dropdown",
              options: MAP_STYLES.map((value) => ({
                value,
                label: text[`map_${value === "map" ? "streets" : value}`],
              })),
            },
          },
        },
        {
          name: "map_scale",
          selector: {
            select: {
              mode: "dropdown",
              options: SCALES.map((value) => ({ value, label: text[`scale_${value}`] })),
            },
          },
        },
        {
          name: "map_range",
          selector: { number: { min: 5, max: 700, mode: "box" } },
        },
        {
          name: "max_altitude",
          selector: { number: { min: 100, max: 60000, step: 100, mode: "box" } },
        },
        {
          name: "palette",
          selector: {
            select: {
              mode: "dropdown",
              options: PALETTES.map((value) => ({ value, label: text[`palette_${value}`] })),
            },
          },
        },
        { name: "show_airports", selector: { boolean: {} } },
        { name: "show_nearby", selector: { boolean: {} } },
        {
          name: "max_nearby",
          selector: { number: { min: 1, max: 20, mode: "box" } },
        },
        { name: "show_status", selector: { boolean: {} } },
      ],
      computeLabel: (schema) => {
        const text = strings(window.__adsbStationHass);
        return { device_id: text.station, ...text }[schema.name];
      },
    };
  }

  constructor() {
    super();
    // hex → the points it was seen at, oldest first.
    this._trails = new Map();
    // [code, latitude, longitude, large], sent once with the first sky.
    this._airports = [];
    this._sky = null;
    this._selected = null;
    // Kinds tapped off under the radar; not kept past a reload.
    this._hidden = new Set();
    // hex → { status, points, at }: pending, found, unknown, failed or off.
    this._routes = new Map();
    // hex → busy, added or failed, for the watchlist button.
    this._watching = new Map();
    this._onlyTable = false;
    this._sort = { key: "distance", descending: false };
    this._query = "";
  }

  setConfig(config) {
    this._config = {
      map: "radar",
      palette: "default",
      show_airports: true,
      show_nearby: true,
      show_status: true,
      max_nearby: DEFAULT_MAX_NEARBY,
      ...(config || {}),
    };
    if (!MAP_STYLES.includes(this._config.map)) this._config.map = "radar";
    this._signature = undefined;
    this._range = undefined;
    if (this._skyBox) this._skyBox.replaceChildren();
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // The config form has no hass of its own to read the language from.
    window.__adsbStationHass = hass;
    if (this._config) this._render();
  }

  connectedCallback() {
    if (this._hass && this._config) {
      this._signature = undefined;
      this._render();
    }
  }

  disconnectedCallback() {
    this._unsubscribe();
  }

  getCardSize() {
    return this._config && this._config.map !== "none" ? 12 : 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  // Every entity of this integration, by its translation key, on one device.
  _find() {
    const entities = Object.values(this._hass.entities || {}).filter((entry) => entry.platform === DOMAIN);
    const overhead = entities.filter(
      (entry) =>
        entry.translation_key === "overhead_flight" &&
        (!this._config.device_id || entry.device_id === this._config.device_id),
    );
    if (!overhead.length) return null;
    const device = overhead[0].device_id;
    const on = (key) => entities.find((entry) => entry.device_id === device && entry.translation_key === key);
    // A station commonly feeds several networks, each its own device, and the
    // feed status of every one of them belongs in the status line.
    const feeds = entities.filter(
      (entry) => entry.translation_key === "feed" || entry.translation_key === "piaware_feed",
    );
    return {
      device,
      overhead: overhead[0],
      nearby: on("aircraft_nearby"),
      passages: on("passages_today"),
      watch: on("watch"),
      received: on("aircraft_received"),
      rate: on("message_rate"),
      range: on("max_range"),
      snr: on("signal_to_noise"),
      sectors: SECTORS.map((sector) => on(`max_range_${sector}`)),
      feeds,
    };
  }

  _state(entry) {
    return entry ? this._hass.states[entry.entity_id] : undefined;
  }

  _render() {
    const found = this._find();
    this._found = found;
    this._follow(found);
    const watched = found
      ? [
          found.overhead,
          found.nearby,
          found.passages,
          found.received,
          found.rate,
          found.range,
          found.snr,
          ...found.sectors,
          ...found.feeds,
        ]
      : [];
    // Only redraw when something this card shows has changed. Home Assistant
    // hands every card the whole state machine on every change anywhere.
    const signature = JSON.stringify([
      this._config,
      this._hass.locale && this._hass.locale.language,
      watched.map((entry) => {
        const state = this._state(entry);
        return state && [state.state, state.last_updated];
      }),
    ]);
    if (signature === this._signature) return;
    this._signature = signature;

    const text = strings(this._hass);
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this._card = el("ha-card");
      this._skyBox = el("div", { class: "sky" });
      this._body = el("div", { class: "body" });
      this._statusBox = el("div", { class: "status-box" });
      // Built once and kept, so typing in the search box survives every push.
      this._tableBox = el("div", { class: "table" });
      this._card.append(this._statusBox, el("div", { class: "layout" }, this._skyBox, this._body), this._tableBox);
      this.shadowRoot.replaceChildren(el("style", {}, STYLE), this._card);
      // Measured, not a container query: WebKit scrolls a phone up when the
      // content of a query container changes.
      if (window.ResizeObserver) {
        new ResizeObserver(([entry]) => {
          const width = entry.contentRect.width;
          this._card.classList.toggle("side-by-side", width >= SIDE_BY_SIDE);
          this._card.classList.toggle("narrow", width <= NARROW);
        }).observe(this._card);
      }
    }
    if (this._config.title) this._card.setAttribute("header", this._config.title);
    else this._card.removeAttribute("header");

    const showSky = Boolean(found) && this._config.map !== "none";
    this._card.querySelector(".layout").classList.toggle("with-sky", showSky);
    this._skyBox.hidden = !showSky;

    const body = [];
    if (!found) {
      body.push(el("div", { class: "empty" }, text.no_station));
    } else if (!this._onlyTable) {
      body.push(this._overhead(found, text));
      if (this._config.show_nearby) body.push(this._nearby(found, text));
    }
    this._body.replaceChildren(...body.filter(Boolean));
    const status = found && !this._onlyTable && this._config.show_status ? this._status(found, text) : null;
    this._statusBox.replaceChildren(...(status ? [status] : []));
    this._statusBox.hidden = !status;
    if (showSky) this._drawSky();
    this._tableBox.hidden = !(found && this._onlyTable);
    if (!this._tableBox.hidden) this._drawTable(text);
  }

  // The same picture element while the aircraft stays, so a poll does not
  // load it again.
  _photoOf(src, alt) {
    if (!this._photo || this._photo.getAttribute("src") !== src) {
      this._photo = el("img", { src, alt, loading: "lazy" });
    }
    this._photo.alt = alt;
    return this._photo;
  }

  _moreInfo(entry) {
    return () => {
      if (!entry) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: entry.entity_id },
          bubbles: true,
          composed: true,
        }),
      );
    };
  }

  _number(value, digits) {
    return new Intl.NumberFormat(this._hass.locale ? this._hass.locale.language : undefined, {
      maximumFractionDigits: digits,
    }).format(value);
  }

  // --- The subscription ---------------------------------------------------

  _follow(found) {
    const wanted =
      found &&
      (this._config.map !== "none" || (this._onlyTable && !this._passages())) &&
      this.isConnected &&
      this._hass.connection
        ? found.device
        : null;
    if (wanted === this._following) return;
    this._unsubscribe();
    if (!wanted) return;
    this._following = wanted;
    this._sky = null;
    this._trails.clear();
    this._airports = [];
    const subscription = this._hass.connection.subscribeMessage((sky) => this._receive(sky), {
      type: SUBSCRIBE,
      device_id: wanted,
    });
    this._subscription = subscription;
    // A subscription that is refused leaves the radar empty rather than
    // breaking the rest of the card.
    subscription.catch(() => {
      if (this._subscription === subscription) this._subscription = null;
    });
  }

  _unsubscribe() {
    clearInterval(this._flying);
    this._flying = null;
    const subscription = this._subscription;
    this._subscription = null;
    this._following = null;
    if (subscription) subscription.then((unsubscribe) => unsubscribe()).catch(() => {});
  }

  _receive(sky) {
    this._sky = sky;
    this._receivedAt = Date.now();
    this._flying ||= setInterval(() => this._skyBox && !this._skyBox.hidden && this._drawSky(), 1000);
    const now = Date.now() / 1000;
    const here = new Set((sky.aircraft || []).map((plane) => plane.hex));
    if (Array.isArray(sky.airports)) this._airports = sky.airports;
    // The first sky brings where every aircraft has been lately, kept by the
    // integration, so a card that just opened does not start from nothing.
    if (sky.trails) {
      this._trails.clear();
      for (const [hex, points] of Object.entries(sky.trails)) {
        if (!here.has(hex)) continue;
        this._trails.set(
          hex,
          points.map(([lat, lon, altitude, t]) => ({ lat, lon, altitude, ground: altitude === null, t })),
        );
      }
    }
    for (const plane of sky.aircraft || []) {
      const trail = this._trails.get(plane.hex) || [];
      const last = trail[trail.length - 1];
      if (!last || last.lat !== plane.latitude || last.lon !== plane.longitude) {
        trail.push({
          lat: plane.latitude,
          lon: plane.longitude,
          altitude: plane.altitude,
          ground: plane.on_ground,
          t: now,
        });
      }
      while (trail.length && trail[0].t < now - TRAIL_SECONDS) trail.shift();
      this._trails.set(plane.hex, trail);
    }
    for (const hex of [...this._trails.keys()]) {
      if (!here.has(hex)) this._trails.delete(hex);
    }
    if (this._skyBox && !this._skyBox.hidden) this._drawSky();
    if (this._tableBox && !this._tableBox.hidden) this._drawTable();
  }

  // --- The sky --------------------------------------------------------------

  _drawSky() {
    const text = strings(this._hass);
    const streets = this._config.map === "map";
    // Redrawn every second, so keyboard focus moves to the new marker.
    const focused = this.shadowRoot.activeElement && this.shadowRoot.activeElement.dataset.hex;
    this._skyBox.replaceChildren(
      ...[
        el(
          "div",
          { class: "scope-box" },
          this._radar(text, streets),
          this._legend(text),
          streets ? this._attribution() : null,
        ),
        this._kinds(text),
        this._picked(text),
      ].filter(Boolean),
    );
    // Without scrolling to it: redrawn every second, it would pull a phone
    // scrolled down to the passage board back up to the radar.
    if (focused) {
      const marker = this._skyBox.querySelector(`.plane[data-hex="${focused}"]`);
      if (marker) marker.focus({ preventScroll: true });
    }
  }

  // Which scale the radar keeps. A range set without a scale is taken as a
  // fixed one, which is what map_range meant before there was a choice.
  _scaleMode() {
    const mode = this._config.map_scale;
    if (SCALES.includes(mode)) return mode;
    return Number(this._config.map_range) > 0 ? "fixed" : "aircraft";
  }

  _scale(sky) {
    const mode = this._scaleMode();
    // Set in the station's units, like everything the card shows.
    if (mode === "fixed") return (Number(this._config.map_range) || DEFAULT_FIXED_RANGE) / this._units().distance[1];
    const furthest = Math.max(
      sky ? sky.radius || 0 : 0,
      ...((sky && sky.aircraft) || []).map((plane) => plane.distance || 0),
      // The records as well, so the whole shape of the coverage fits.
      ...(mode === "coverage" ? this._outlineKm(sky) || this._coverage() || [] : []),
    );
    // Round steps in the unit shown, up to the first that reaches 700 km;
    // a step of other units is no step at all.
    const per = this._units().distance[1];
    if (this._rangePer !== per) this._range = undefined;
    this._rangePer = per;
    // Held until the sky clearly fits a smaller ring, so one aircraft at the
    // edge coming and going does not make the whole radar breathe.
    if (this._range && furthest <= this._range && furthest > this._range * 0.6) return this._range;
    const steps = RANGE_STEPS.map((step) => step / per);
    const last = steps.findIndex((km) => km >= FURTHEST_KM);
    const usable = last < 0 ? steps : steps.slice(0, last + 1);
    this._range = usable.find((km) => km >= furthest) || usable[usable.length - 1];
    return this._range;
  }

  // One drawing for both: on the radar's scope, or on map tiles.
  _radar(text, streets) {
    const sky = this._sky && {
      ...this._sky,
      aircraft: this._belowCeiling()
        .filter((plane) => !this._hidden.has(plane.kind))
        .map((plane) => flownOn(plane, (Date.now() - this._receivedAt) / 1000)),
    };
    const size = 400;
    const centre = size / 2;
    const reach = 184;
    const range = this._scale(sky);
    const origin = sky ? [sky.latitude, sky.longitude] : null;

    // Flat around the station on the radar; the tiles' projection on the map.
    let perKm = reach / range;
    let project = (lat, lon) => {
      const east = lonDelta(lon, origin[1]) * 111.32 * Math.cos((origin[0] * Math.PI) / 180);
      const north = (lat - origin[0]) * 110.574;
      return [centre + east * perKm, centre - north * perKm];
    };
    let tiles = null;
    if (streets && origin) {
      const view = mercatorView(origin, range, reach, centre, size);
      perKm = view.perKm;
      project = view.project;
      tiles = this._tiles(view);
    }
    const inView = streets
      ? ([x, y]) => x >= -2 && x <= size + 2 && y >= -2 && y <= size + 2
      : ([x, y]) => Math.hypot(x - centre, y - centre) <= reach + 2;
    const distances = [
      { km: range / 2, y: centre - (range / 2) * perKm - 4 },
      { km: range, y: centre - range * perKm + 14 },
    ].map(({ km, y }) => ({ x: centre + 4, y, text: this._distance(km) }));

    const scope = svg("svg", {
      class: streets ? "radar streets" : "radar",
      viewBox: `0 0 ${size} ${size}`,
      role: "group",
      "aria-label": text.sky,
    });
    const shape = streets
      ? svg("rect", { x: 0, y: 0, width: size, height: size, rx: 12 })
      : svg("circle", { cx: centre, cy: centre, r: reach });
    scope.append(svg("defs", {}, svg("clipPath", { id: "scope" }, shape), streets && darkTiles()));
    if (streets) {
      scope.append(svg("rect", { class: "land", x: 0, y: 0, width: size, height: size, "clip-path": "url(#scope)" }));
      if (tiles) scope.append(tiles);
    } else {
      scope.append(svg("circle", { class: "scope", cx: centre, cy: centre, r: reach }));
    }
    scope.append(
      svg(
        "g",
        { "clip-path": "url(#scope)" },
        svg("circle", { class: "ring", cx: centre, cy: centre, r: (range / 2) * perKm }),
        svg("circle", { class: "ring", cx: centre, cy: centre, r: range * perKm }),
        streets ? null : svg("line", { class: "ring", x1: centre - reach, y1: centre, x2: centre + reach, y2: centre }),
        streets ? null : svg("line", { class: "ring", x1: centre, y1: centre - reach, x2: centre, y2: centre + reach }),
      ),
      ...distances.map(({ x, y, text }) => svg("text", { class: "distance", x, y }, text)),
    );
    const coverage = this._coverage();
    const outline = sky && Array.isArray(sky.outline) && sky.outline.length > 2 ? sky.outline : null;
    if (outline) {
      // readsb's own shape, a point per degree, where the decoder keeps one.
      const corners = outline.map(([lat, lon]) =>
        project(lat, lon)
          .map((v) => v.toFixed(1))
          .join(","),
      );
      scope.append(svg("polygon", { class: "coverage", points: corners.join(" "), "clip-path": "url(#scope)" }));
    } else if (coverage) {
      const corners = coverage.map((km, i) => {
        const bearing = (i * 45 * Math.PI) / 180;
        const out = km * perKm;
        return `${(centre + Math.sin(bearing) * out).toFixed(1)},${(centre - Math.cos(bearing) * out).toFixed(1)}`;
      });
      scope.append(svg("polygon", { class: "coverage", points: corners.join(" "), "clip-path": "url(#scope)" }));
    }
    if (sky && sky.radius && sky.radius < range) {
      scope.append(svg("circle", { class: "near", cx: centre, cy: centre, r: sky.radius * perKm }));
    }
    if (!streets) {
      const [north, east, south, west] = text.compass;
      scope.append(
        svg("text", { class: "compass", x: centre, y: centre - reach - 4 }, north),
        svg("text", { class: "compass", x: centre + reach + 9, y: centre + 4 }, east),
        svg("text", { class: "compass", x: centre, y: centre + reach + 13 }, south),
        svg("text", { class: "compass", x: centre - reach - 9, y: centre + 4 }, west),
      );
    }

    // The airports, under everything that moves. A code that would cover
    // another or the station, or run off the edge, is left off; a picked
    // route draws its own.
    const fields = [];
    if (origin && this._config.show_airports) {
      const picked = this._selected && sky && (sky.aircraft || []).find((plane) => plane.hex === this._selected);
      const route = picked && this._routeOf(picked);
      const ends = new Set(route ? [route.origin.code, route.destination.code] : []);
      const layer = svg("g", { class: "fields", "clip-path": "url(#scope)" });
      const taken = [[centre - 9, centre - 9, centre + 9, centre + 9]];
      for (const [code, lat, lon, large] of this._airports) {
        if ((!large && range > ALL_AIRPORTS_KM) || ends.has(code)) continue;
        const [x, y] = project(lat, lon);
        if (!inView([x, y])) continue;
        const box = [x + 4, y - 6, x + 6 + 5.6 * code.length, y + 5];
        const free =
          inView([box[2], box[1]]) &&
          inView([box[2], box[3]]) &&
          !taken.some((o) => box[0] < o[2] && o[0] < box[2] && box[1] < o[3] && o[1] < box[3]);
        if (free) taken.push(box);
        layer.append(
          svg(
            "g",
            { transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})` },
            svg("circle", { r: 2.5 }),
            free ? svg("text", { x: 5, y: 3.5 }, code) : null,
          ),
        );
      }
      fields.push(...taken.slice(1));
      scope.append(layer);
    }

    if (origin) {
      const trails = svg("g", { class: "trails", "clip-path": "url(#scope)" });
      const flown = new Map(((sky && sky.aircraft) || []).map((plane) => [plane.hex, plane]));
      for (const [hex, trail] of this._trails) {
        // On to where the aircraft has flown since, so it trails no gap.
        const plane = flown.get(hex);
        if (!plane) continue;
        const last = trail.at(-1);
        const moved = plane && last && (plane.latitude !== last.lat || plane.longitude !== last.lon);
        const points = moved ? [...trail, { ...last, lat: plane.latitude, lon: plane.longitude }] : trail;
        for (let i = 1; i < points.length; i++) {
          const [x1, y1] = project(points[i - 1].lat, points[i - 1].lon);
          const [x2, y2] = project(points[i].lat, points[i].lon);
          const { altitude, ground } = points[i];
          trails.append(svg("line", { x1, y1, x2, y2, stroke: altitudeColor(altitude, ground, this._config.palette) }));
        }
      }
      scope.append(trails);
    }
    scope.append(svg("circle", { class: "home", cx: centre, cy: centre, r: 4 }));

    // The way the picked aircraft came and is going: flown from where it left
    // to where it is now, and dashed on to where it lands.
    const chosen = this._selected && sky && (sky.aircraft || []).find((plane) => plane.hex === this._selected);
    const route = chosen && this._routeOf(chosen);
    if (route) {
      const here = [chosen.latitude, chosen.longitude];
      const line = (from, to) =>
        greatCircle(from, to)
          .map(([lat, lon]) =>
            project(lat, lon)
              .map((value) => value.toFixed(1))
              .join(","),
          )
          .join(" ");
      const ends = [route.origin, route.destination];
      scope.append(
        svg(
          "g",
          { class: "route", "clip-path": "url(#scope)" },
          svg("polyline", { class: "flown", points: line([route.origin.latitude, route.origin.longitude], here) }),
          svg("polyline", {
            class: "ahead",
            points: line(here, [route.destination.latitude, route.destination.longitude]),
          }),
          ends.map((airport) => {
            const [x, y] = project(airport.latitude, airport.longitude);
            return svg(
              "g",
              { class: "airport", transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})` },
              svg("circle", { r: 4 }),
              svg("text", { x: 7, y: 4 }, airport.code || ""),
            );
          }),
        ),
      );
    }

    const heading = chosen && headingOf(chosen, origin, (Date.now() - this._receivedAt) / 1000);
    if (heading) {
      const [x1, y1] = project(chosen.latitude, chosen.longitude);
      const [x2, y2] = project(...heading.end);
      const point = heading.closest && project(...heading.closest);
      scope.append(
        svg(
          "g",
          { class: "heading", "clip-path": "url(#scope)" },
          svg("line", { x1, y1, x2, y2 }),
          point ? svg("circle", { class: "closest", cx: point[0], cy: point[1], r: 4 }) : null,
        ),
      );
    }

    const planes = ((sky && sky.aircraft) || [])
      .map((plane) => ({ plane, at: project(plane.latitude, plane.longitude) }))
      .filter(({ at }) => inView(at));

    // Picked first, then nearest. A label goes to the first corner of its
    // aircraft where it covers no other label, aircraft or ring distance, and
    // is left off where there is none.
    const labelled = new Map();
    const placed = [];
    const others = planes.map(({ plane, at: [x, y] }) => [plane.hex, [x - 10, y - 10, x + 10, y + 10]]);
    const ringLabels = distances.map(({ x, y, text }) => [x - 2, y - 11, x + 2 + 6.4 * text.length, y + 3]);
    const ranked = [...planes].sort(
      (a, b) =>
        (b.plane.hex === this._selected) - (a.plane.hex === this._selected) ||
        (a.plane.distance || 0) - (b.plane.distance || 0),
    );
    for (const {
      plane,
      at: [x, y],
    } of ranked) {
      const width = 2 + 6.4 * String(plane.flight || plane.hex).length;
      for (const [dx, dy, end] of LABEL_SPOTS) {
        const left = x + dx + (end ? -width + 1 : -1);
        const box = [left, y + dy - 10, left + width, y + dy + 3];
        const covers = (other) => box[0] < other[2] && other[0] < box[2] && box[1] < other[3] && other[1] < box[3];
        if (placed.some(covers) || ringLabels.some(covers)) continue;
        if (others.some(([hex, other]) => hex !== plane.hex && covers(other))) continue;
        placed.push(box);
        labelled.set(plane.hex, { x: dx, y: dy, "text-anchor": end ? "end" : undefined });
        break;
      }
    }

    // Place names go where the aircraft, their callsigns and the ring
    // distances leave room.
    if (tiles && this._basemapLayer && tiles === this._basemapLayer.node) {
      const marks = planes.map(({ at: [x, y] }) => [x - 12, y - 12, x + 12, y + 12]);
      const station = [centre - 9, centre - 9, centre + 9, centre + 9];
      const rings = distances.map(({ x, y, text }) => [x - 2, y - 11, x + 2 + 6.4 * text.length, y + 3]);
      const names = placeNames(this._basemapLayer.places, size, [...placed, ...marks, station, ...rings, ...fields]);
      tiles.after(svg("g", { class: "basemap", "clip-path": "url(#scope)" }, names));
    }

    // The highest drawn last, so the one overhead at cruising height is not
    // hidden under a trail far below it.
    for (const {
      plane,
      at: [x, y],
    } of [...planes].sort((a, b) => (a.plane.altitude || 0) - (b.plane.altitude || 0))) {
      const { path, scale } = shapeOf(plane);
      const selected = plane.hex === this._selected;
      const marker = svg(
        "g",
        {
          class: selected ? "plane selected" : "plane",
          transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})`,
          role: "button",
          tabindex: "0",
          "aria-label": plane.flight || plane.hex,
          "data-hex": plane.hex,
          onclick: () => this._select(plane.hex),
        },
        svg("title", {}, this._describe(plane, text)),
        selected ? svg("circle", { class: "halo", r: 15 }) : null,
        mark(plane) ? svg("circle", { class: mark(plane), r: 11 }) : null,
        svg("path", {
          d: path,
          fill: altitudeColor(plane.altitude, plane.on_ground, this._config.palette),
          transform: `rotate(${Math.round(plane.track || 0)}) scale(${scale})`,
        }),
        labelled.has(plane.hex)
          ? svg("text", { class: "callsign", ...labelled.get(plane.hex) }, plane.flight || plane.hex)
          : null,
      );
      scope.append(marker);
    }
    if (sky && !planes.length) {
      scope.append(svg("text", { class: "quiet", x: centre, y: centre + 30 }, text.no_positions));
    }
    return scope;
  }

  // Kept while view, token and theme are unchanged, so tiles do not reload.
  _tiles(view) {
    const token = this._tileToken();
    if (token === undefined) return null;
    if (token && this._vector !== false && typeof fetch === "function") {
      const basemap = this._basemap(view, token);
      if (basemap || this._vector === undefined) return basemap;
    }
    const dark = Boolean(this._hass.themes && this._hass.themes.darkMode);
    const key = `${view.key}|${token}|${dark}`;
    if (this._tileLayer && this._tileLayer.key === key) return this._tileLayer.node;
    const url = token ? (z, x, y) => PROXY_TILES(z, x, y, token) : UPSTREAM_TILES;
    const node = svg(
      "g",
      { class: dark ? "tiles dark" : "tiles", "clip-path": "url(#scope)", filter: dark && "url(#dark)" },
      view.tiles(url).map((tile) =>
        svg("image", {
          href: tile.href,
          x: tile.x,
          y: tile.y,
          width: tile.size,
          height: tile.size,
          preserveAspectRatio: "none",
        }),
      ),
    );
    this._tileLayer = { key, node };
    return node;
  }

  // OpenStreetMap's data drawn in the theme's colours. Null until a first tile
  // is in; a Home Assistant without vector tiles turns this off for the raster.
  _basemap(view, token) {
    const tiles = view.vectorTiles();
    const cache = (this._vectorTiles ||= new Map());
    const now = Date.now();
    for (const tile of tiles) {
      const id = `${tile.z}/${tile.x}/${tile.y}`;
      const held = cache.get(id);
      if (held && !(held.retryAt <= now)) continue;
      cache.set(id, { pending: true });
      // The token as a header keeps the address, and so the browser's cache,
      // the same when the token changes. Home Assistant 2026.9 only takes it
      // in the address, and refuses the header with a 403.
      const inQuery = this._vectorTokenInQuery;
      const url = PROXY_VECTOR(tile.z, tile.x, tile.y);
      const asked = inQuery
        ? fetch(`${url}?token=${encodeURIComponent(token)}`)
        : fetch(url, { headers: { "X-Map-Tiles-Token": token } });
      let retryAt = Date.now() + VECTOR_RETRY;
      asked
        .then((response) => {
          if (response.status === 404) this._vector = false;
          if (response.status === 403 && !inQuery) {
            this._vectorTokenInQuery = true;
            retryAt = 0;
          }
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.arrayBuffer();
        })
        .then((buffer) => {
          cache.set(id, basemapTile(decodeTile(new Uint8Array(buffer))));
          this._vector = true;
          while (cache.size > VECTOR_CACHE) cache.delete(cache.keys().next().value);
        })
        .catch(() => cache.set(id, { retryAt }))
        .finally(() => {
          if (this._skyBox && !this._skyBox.hidden && this._config.map === "map") this._drawSky();
        });
    }
    const ready = tiles.filter((tile) => (cache.get(`${tile.z}/${tile.x}/${tile.y}`) || {}).paths);
    if (!ready.length) return null;
    const key = `${view.key}|${ready.map((tile) => `${tile.z}/${tile.x}/${tile.y}`).join(",")}`;
    if (this._basemapLayer && this._basemapLayer.key === key) return this._basemapLayer.node;

    const places = [];
    const drawn = ready.map((tile) => {
      const data = cache.get(`${tile.z}/${tile.x}/${tile.y}`);
      const scale = tile.side / data.extent;
      for (const place of data.places) {
        places.push({ ...place, x: tile.left + place.x * scale, y: tile.top + place.y * scale });
      }
      // Each tile cut to its own square: tiles overlap at the edges, and what
      // is there twice would show twice.
      const clip = `tile-${tile.z}-${tile.x}-${tile.y}`;
      return svg(
        "g",
        { transform: `translate(${tile.left.toFixed(2)} ${tile.top.toFixed(2)}) scale(${scale})` },
        svg("clipPath", { id: clip }, svg("rect", { x: 0, y: 0, width: data.extent, height: data.extent })),
        svg(
          "g",
          { "clip-path": `url(#${clip})` },
          data.paths.map(([kind, d]) => svg("path", { class: kind, d })),
        ),
      );
    });
    places.sort((a, b) => a.rank - b.rank || b.population - a.population);
    const node = svg("g", { class: "basemap", "clip-path": "url(#scope)" }, drawn);
    this._basemapLayer = { key, node, places };
    return node;
  }

  // The token for Home Assistant's tile proxy: a string, null where there is
  // no proxy to ask, or undefined while that is still being found out.
  _tileToken() {
    const fresh = this._token && Date.now() - this._token.at < TOKEN_REFRESH;
    if (!fresh && !this._askingToken && this._hass.connection && this._hass.connection.sendMessagePromise) {
      this._askingToken = true;
      this._hass.connection
        .sendMessagePromise({ type: "map_tiles/access_token" })
        .then((result) => (result && result.token ? result.token : null))
        .catch(() => null)
        .then((token) => {
          this._token = { value: token, at: Date.now() };
          this._askingToken = false;
          if (this._skyBox && !this._skyBox.hidden && this._config.map === "map") this._drawSky();
        });
    }
    if (this._token) return this._token.value;
    // No websocket at all to ask over: straight to OpenStreetMap.
    return this._hass.connection && this._hass.connection.sendMessagePromise ? undefined : null;
  }

  // The tiles are OpenStreetMap's, which asks to be credited where they are
  // shown.
  _attribution() {
    return el(
      "div",
      { class: "attribution" },
      "© ",
      el("a", { href: "https://www.openstreetmap.org/copyright", target: "_blank", rel: "noopener" }, "OpenStreetMap"),
      " contributors",
    );
  }

  // One line on an aircraft, for where only text can go.
  _describe(plane, text) {
    return [
      [plane.flight || plane.hex, plane.airline].filter(Boolean).join(" · "),
      plane.description || plane.aircraft_type,
      this._height(plane, text),
      this._distance(plane.distance),
    ]
      .filter(Boolean)
      .join(" · ");
  }

  // How far each point of readsb's outline lies, in km, or null without one.
  _outlineKm(sky) {
    if (!sky || !Array.isArray(sky.outline) || sky.outline.length < 3) return null;
    const across = 111.32 * Math.cos((sky.latitude * Math.PI) / 180);
    return sky.outline.map(([lat, lon]) =>
      Math.hypot(lonDelta(lon, sky.longitude) * across, (lat - sky.latitude) * 110.574),
    );
  }

  // Range record per sector in km, clockwise from north; needs at least three.
  _coverage() {
    const found = this._found;
    if (!found) return null;
    const records = found.sectors.map((entry) => {
      const state = this._state(entry);
      const value = numeric(state);
      if (value === null) return null;
      const unit = state.attributes.unit_of_measurement || "km";
      return unit in KILOMETRES ? value * KILOMETRES[unit] : null;
    });
    if (records.filter((km) => km !== null).length < 3) return null;
    return records.map((km) => km || 0);
  }

  _select(hex) {
    this._selected = this._selected === hex ? null : hex;
    // A route is only asked for where it can be drawn.
    if (this._selected && !this._skyBox.hidden) this._lookUpRoute(this._selected);
    if (!this._skyBox.hidden) this._drawSky();
    if (!this._tableBox.hidden) this._drawTable();
  }

  // Both ends of an aircraft's route with where they are, if known: sent
  // along for the nearby ones, asked for on a tap for the rest.
  _routeOf(plane) {
    if (plane.route_points) return plane.route_points;
    const asked = this._routes.get(plane.hex);
    return asked ? asked.points : null;
  }

  _lookUpRoute(hex) {
    const plane = this._sky && (this._sky.aircraft || []).find((p) => p.hex === hex);
    if (!plane || plane.route_points || !this._following || !this._hass.callWS) return;
    const asked = this._routes.get(hex);
    const now = Date.now() / 1000;
    if (asked) {
      // A failed question is asked again on the next tap.
      const wait = { pending: ROUTE_WAIT_SECONDS, failed: 0 }[asked.status] ?? ROUTE_RETRY_SECONDS;
      if (asked.points || asked.at > now - wait) return;
    }
    this._routes.set(hex, { status: "pending", points: null, at: now });
    const answered = (status, points = null) => this._routes.set(hex, { status, points, at: Date.now() / 1000 });
    this._hass
      .callWS({ type: LOOK_UP_ROUTE, device_id: this._following, hex })
      .then((answer) => {
        const points = (answer && answer.route_points) || null;
        answered(points ? "found" : (answer && answer.status) || "unknown", points);
      })
      .catch(() => answered("failed"))
      .finally(() => {
        if (this._selected === hex) this._drawSky();
      });
  }

  // Every aircraft at or under the altitude set, if one is.
  _belowCeiling() {
    // In the station's units; the sky is in feet.
    const ceiling = (Number(this._config.max_altitude) || 0) / this._units().height[1];
    return ((this._sky && this._sky.aircraft) || []).filter((plane) => !ceiling || !(plane.altitude > ceiling));
  }

  // One button per kind, with how many there are, to take it off the radar.
  _kinds(text) {
    if (!this._sky) return null;
    const planes = this._belowCeiling();
    return el(
      "div",
      { class: "kinds" },
      KINDS.map((kind) => {
        const count = planes.filter((plane) => plane.kind === kind).length;
        const shown = !this._hidden.has(kind);
        // Home Assistant's own filter chip: a tick when on, an outline when off.
        return el(
          "button",
          {
            class: count ? "kind" : "kind none",
            "aria-pressed": String(shown),
            onclick: () => {
              if (!this._hidden.delete(kind)) this._hidden.add(kind);
              this._drawSky();
            },
          },
          shown ? this._icon(`kind ${kind}`, "mdi:check") : null,
          `${text[`kind_${kind}`]} `,
          el("span", { class: "count" }, count),
        );
      }),
      // So the five add up to the aircraft received. Plain text, as it is no
      // filter; kept at 0 so the row does not change width.
      el("span", { class: "unplaced", title: text.no_position_hint }, `${text.no_position} ${this._sky.unplaced ?? 0}`),
    );
  }

  _legend(text) {
    const feet =
      this._config.palette === "colorblind" ? COLORBLIND.map((_, i) => i * 5000) : ALTITUDE_HUES.map(([at]) => at);
    const stops = feet.map(
      (at) => `${altitudeColor(at, false, this._config.palette)} ${((at / ALTITUDE_TOP) * 100).toFixed(1)}%`,
    );
    return el(
      "div",
      { class: "legend" },
      el(
        "div",
        { class: "keys" },
        el("span", { class: "key" }, el("span", { class: "dot ground" }), text.on_ground),
        this._outlineKm(this._sky)
          ? el("span", { class: "key" }, el("span", { class: "area" }), text.coverage_day)
          : this._coverage()
            ? el("span", { class: "key" }, el("span", { class: "area" }), text.coverage)
            : null,
      ),
      el(
        "div",
        { class: "scale" },
        el("div", { class: "bar", style: `background: linear-gradient(to right, ${stops.join(", ")})` }),
        el(
          "div",
          { class: "ticks" },
          this._units().ticks.map((value, i, all) => {
            const [unit, per] = this._units().height;
            const share = (value / per / ALTITUDE_TOP) * 100;
            const label = this._number(value, 0) + (i === all.length - 1 ? ` ${unit}` : "");
            // Centred on its height, but kept inside the bar at either end.
            const shift = share < 5 ? "0" : share > 95 ? "-100%" : "-50%";
            return el("span", { style: `left: ${share.toFixed(1)}%; transform: translateX(${shift})` }, label);
          }),
        ),
      ),
    );
  }

  // An icon kept across the redraws of every second: a new ha-icon loads
  // its picture anew, and would not get the time to show it.
  _icon(slot, icon) {
    this._icons ||= new Map();
    let node = this._icons.get(slot);
    if (!node) {
      node = el("ha-icon", {});
      this._icons.set(slot, node);
    }
    if (node.getAttribute("icon") !== icon) node.setAttribute("icon", icon);
    return node;
  }

  _picked(text) {
    const found = this._selected && this._sky && (this._sky.aircraft || []).find((p) => p.hex === this._selected);
    if (!found) return null;
    // Just put on the watchlist: said so now, not after the next read.
    const plane = this._watching.get(found.hex) === "added" ? { ...found, watched: true } : found;
    const tint = altitudeColor(plane.altitude, plane.on_ground, this._config.palette);
    return el(
      "div",
      { class: "picked" },
      el(
        "div",
        { class: "head" },
        el("span", { class: "badge-icon", style: `--tint: ${tint}` }, this._icon("picked", aircraftIcon(plane))),
        el(
          "div",
          { class: "names" },
          el("div", { class: "title" }, plane.flight || plane.hex, plane.airline ? ` · ${plane.airline}` : ""),
          el(
            "div",
            { class: "sub" },
            [plane.description || plane.aircraft_type, plane.registration].filter(Boolean).join(" · "),
          ),
        ),
        this._watchButton(plane, text),
      ),
      mark(plane) ? el("div", { class: `mark ${mark(plane)}` }, text[plane.emergency || "watched"]) : null,
      this._watching.get(plane.hex) === "failed" ? el("div", { class: "failed" }, text.watch_failed) : null,
      this._routeLine(plane, text),
      this._figures(plane, text),
      this._passing(plane, text),
      this._flightLine(plane, text),
    );
  }

  // Height, speed and distance, each a figure of its own with its unit small.
  _figures(plane, text) {
    const cells = [
      [text.col_altitude, this._height(plane, text)],
      [text.col_speed, this._speed(plane.speed)],
      [text.col_distance, this._distance(plane.distance)],
    ].filter(([, value]) => value);
    if (!cells.length) return null;
    return el(
      "div",
      { class: "stats" },
      cells.map(([label, value]) => {
        const at = value.lastIndexOf(" ");
        const unit = at > 0 && /\d/.test(value.slice(0, at)) ? value.slice(at + 1) : "";
        return el(
          "div",
          { class: "stat" },
          el("span", { class: "caption" }, label),
          el("b", {}, unit ? value.slice(0, at) : value),
          unit ? el("small", {}, ` ${unit}`) : null,
        );
      }),
    );
  }

  // One tap puts the picked aircraft on the watchlist, through the box anyone
  // may fill rather than the action only an administrator may call.
  _watchButton(plane, text) {
    const box = this._found && this._found.watch;
    const line = plane.registration || plane.hex;
    if (plane.watched || !box || !line || line.startsWith("~")) return null;
    return el(
      "button",
      {
        class: "watch-button",
        "aria-label": text.watch,
        title: text.watch,
        disabled: this._watching.get(plane.hex) === "busy",
        onclick: () => this._watch(plane.hex, line, box),
      },
      this._icon("watch", "mdi:eye-plus-outline"),
    );
  }

  async _watch(hex, line, box) {
    this._watching.set(hex, "busy");
    this._drawSky();
    try {
      await this._hass.callService("text", "set_value", { value: line }, { entity_id: box.entity_id });
      this._watching.set(hex, "added");
    } catch {
      this._watching.set(hex, "failed");
    }
    if (this._skyBox && !this._skyBox.hidden) this._drawSky();
  }

  // How close the picked aircraft comes, and in how long, while it still comes.
  _passing(plane, text) {
    const left = Math.round(plane.seconds_to_closest - (Date.now() - this._receivedAt) / 1000);
    if (!plane.approaching || !(left > 0) || typeof plane.closest_passing_distance !== "number") return null;
    const words = text.passes
      .replace("{distance}", this._distance(plane.closest_passing_distance))
      .replace("{time}", minutes(left));
    return el("div", { class: "tip passing" }, this._icon("passing", "mdi:crosshairs-gps"), el("span", {}, words));
  }

  // What else the aircraft says of its flight, where the decoder passes it on.
  _flightLine(plane, text) {
    const number = (value) => typeof value === "number";
    const parts = [
      text[`class_${plane.category}`],
      number(plane.mach)
        ? `Mach ${this._number(plane.mach, 2)}`
        : number(plane.ias)
          ? `IAS ${this._speed(plane.ias)}`
          : null,
      number(plane.wind_direction) && number(plane.wind_speed)
        ? `${text.wind} ${this._number(plane.wind_direction, 0)}° ${this._speed(plane.wind_speed)}`
        : null,
      number(plane.temperature)
        ? this._units() === UNIT_SYSTEMS.imperial
          ? `${this._number((plane.temperature * 9) / 5 + 32, 0)} °F`
          : `${this._number(plane.temperature, 0)} °C`
        : null,
      // Only in a turn worth the name.
      number(plane.roll) && Math.abs(plane.roll) >= 5 ? `${text.roll} ${this._number(Math.abs(plane.roll), 0)}°` : null,
    ].filter(Boolean);
    if (!parts.length) return null;
    // Each part kept whole, so a line breaks between them, not inside one.
    const kept = parts.flatMap((part, i) => [i ? " · " : null, el("span", { class: "whole" }, part)]);
    return el("div", { class: "fine" }, kept.filter(Boolean));
  }

  // Where it comes from and goes to, under the aircraft's name. Without a
  // route, whether one is on its way, unknown, or could not be looked up.
  _routeLine(plane, text) {
    const route = this._routeOf(plane);
    if (!route) {
      const asked = this._routes.get(plane.hex);
      if (!asked) return null;
      const lost = asked.status === "pending" && asked.at <= Date.now() / 1000 - ROUTE_WAIT_SECONDS;
      const status = lost ? "failed" : asked.status;
      const words = { pending: text.route_pending, unknown: text.route_unknown, failed: text.route_failed }[status];
      return words ? el("div", { class: `secondary route-line ${status}` }, words) : null;
    }
    const end = (airport) => [airport.code, airport.location].filter(Boolean).join(" ");
    const airport = (where, side) =>
      el(
        "div",
        { class: `airport ${side}` },
        el("b", {}, where.code || where.location),
        where.code ? el("span", {}, where.location) : null,
      );
    return el(
      "div",
      { class: "route", role: "img", "aria-label": `${end(route.origin)} → ${end(route.destination)}` },
      airport(route.origin, "from"),
      el("div", { class: "line" }, this._icon("route", "mdi:airplane")),
      airport(route.destination, "to"),
    );
  }

  // --- Overhead and nearby -------------------------------------------------

  _overhead(found, text) {
    const state = this._state(found.overhead);
    const plane = state ? this._fromSensors(state.attributes, state) : {};
    const known = state && !["unknown", "unavailable"].includes(state.state) && (plane.flight || plane.hex);
    if (!known) {
      return el("div", { class: "empty" }, el("ha-icon", { icon: "mdi:airplane-off" }), text.nothing);
    }

    // One tile: the photo or the aircraft's icon, what it is, and where.
    // The photo leads to its page and names who took it, as Planespotters asks
    // of anyone showing one. Without all three it is not shown at all.
    const photo = safeUrl(plane.photo);
    const link = safeUrl(plane.photo_link);
    const credited = photo && link && plane.photographer;
    const name = plane.flight || state.state;
    const tint = altitudeColor(plane.altitude, plane.on_ground, this._config.palette);
    const details = el(
      "div",
      { class: "details", role: "button", tabindex: "0", onclick: this._moreInfo(found.overhead) },
      credited
        ? el(
            "a",
            {
              class: "photo",
              href: link,
              target: "_blank",
              rel: "noopener",
              // The photo opens its page, not the aircraft's details.
              onclick: (event) => event.stopPropagation(),
            },
            this._photoOf(photo, name),
          )
        : el("span", { class: "badge-icon", style: `--tint: ${tint}` }, el("ha-icon", { icon: aircraftIcon(plane) })),
      el(
        "div",
        { class: "lines" },
        el("div", { class: "label" }, plane.overhead === false ? text.last_overhead : text.overhead),
        el("div", { class: "primary" }, name, plane.airline ? ` · ${plane.airline}` : ""),
        el(
          "div",
          { class: "secondary" },
          [plane.description || plane.aircraft_type, plane.registration].filter(Boolean).join(" · "),
        ),
      ),
      el(
        "div",
        { class: "aside" },
        plane.origin && plane.destination ? el("div", {}, `${plane.origin} → ${plane.destination}`) : null,
        el("div", {}, [this._height(plane, text), this._distance(plane.distance)].filter(Boolean).join(" · ")),
      ),
    );
    return el(
      "div",
      { class: "overhead" },
      details,
      credited
        ? el(
            "div",
            { class: "credit" },
            `${text.photo}: ${plane.photographer} / `,
            el("a", { href: link, target: "_blank", rel: "noopener" }, "Planespotters.net"),
          )
        : null,
    );
  }

  _height(plane, text) {
    if (plane.on_ground) return text.on_ground;
    if (typeof plane.altitude !== "number") return null;
    const rate = plane.vertical_rate;
    const arrow =
      typeof rate === "number" && rate >= CLIMB_RATE_SHOWN
        ? "↑ "
        : typeof rate === "number" && rate <= -CLIMB_RATE_SHOWN
          ? "↓ "
          : "";
    const [unit, per] = this._units().height;
    return `${arrow}${this._number(plane.altitude * per, 0)} ${unit}`;
  }

  _distance(km) {
    if (typeof km !== "number") return null;
    const [unit, per] = this._units().distance;
    return `${this._number(km * per, 1)} ${unit}`;
  }

  _speed(knots) {
    if (typeof knots !== "number") return null;
    const [unit, per] = this._units().speed;
    return `${this._number(knots * per, 0)} ${unit}`;
  }

  // The integration's units, as the sky or a sensor names them. Before
  // either has arrived, Home Assistant's own: imperial for US units.
  _units() {
    return (this._sky && UNIT_SYSTEMS[this._sky.units]) || this._stationUnits() || this._hassUnits();
  }

  _hassUnits() {
    const system = this._hass && this._hass.config && this._hass.config.unit_system;
    return system && system.length === "mi" ? UNIT_SYSTEMS.imperial : UNIT_SYSTEMS.metric;
  }

  // What the integration sends its sensors' figures in, if any says so.
  _stationUnits() {
    const found = this._found || {};
    for (const key of ["overhead", "nearby", "passages"]) {
      const units = this._unitsOf(this._state(found[key]));
      if (units) return units;
    }
    return null;
  }

  // The units one sensor gives its figures in, as its attributes name them.
  _unitsOf(state) {
    const name = state && SYSTEM_BY_DISTANCE[state.attributes.distance_unit];
    return name ? UNIT_SYSTEMS[name] : null;
  }

  // An aircraft from a sensor's attributes, back in the feet, knots and
  // kilometres the radar's feed has, so both are shown the same way.
  _fromSensors(plane, state) {
    const units = this._unitsOf(state);
    if (!units || !plane) return plane;
    const back = (value, per) => (typeof value === "number" ? value / per : value);
    return {
      ...plane,
      altitude: back(plane.altitude, units.height[1]),
      speed: back(plane.speed, units.speed[1]),
      distance: back(plane.distance, units.distance[1]),
      // Metres a second on a metric station, feet a minute otherwise.
      vertical_rate: units === UNIT_SYSTEMS.metric ? back(plane.vertical_rate, 0.00508) : plane.vertical_rate,
    };
  }

  _nearby(found, text) {
    const state = this._state(found.nearby);
    const list =
      state && Array.isArray(state.attributes.aircraft)
        ? state.attributes.aircraft.map((p) => this._fromSensors(p, state))
        : [];
    const overhead = this._state(found.overhead);
    const skip = overhead && overhead.attributes.overhead !== false ? overhead.attributes.hex : null;
    const others = list
      .filter((plane) => plane.hex !== skip)
      .slice(0, Number(this._config.max_nearby) || DEFAULT_MAX_NEARBY);
    if (!others.length) return null;
    return el(
      "div",
      { class: "nearby" },
      el("div", { class: "label" }, text.nearby),
      others.map((plane) =>
        el(
          "div",
          { class: "row", role: "button", tabindex: "0", onclick: this._moreInfo(found.nearby) },
          el("ha-icon", {
            icon: aircraftIcon(plane),
            style: `color: ${altitudeColor(plane.altitude, plane.on_ground, this._config.palette)}`,
          }),
          el("span", { class: "flight" }, plane.flight || plane.hex),
          el("span", { class: "what" }, plane.airline || plane.description || ""),
          el("span", { class: "figure" }, this._distance(plane.distance) || ""),
          el("span", { class: "figure" }, this._height(plane, text) || ""),
        ),
      ),
    );
  }

  // --- Every aircraft, as a table --------------------------------------------

  _passages() {
    return this._onlyTable && this._config.list === "passages";
  }

  _columns(text) {
    const figure = (value, show) => (typeof value === "number" ? show(value) : "");
    if (this._passages()) {
      const language = this._hass.locale && this._hass.locale.language;
      const time = (at) => new Date(at).toLocaleTimeString(language, { hour: "2-digit", minute: "2-digit" });
      return [
        { key: "at", sort: (p) => p.at, show: (p) => (p.at ? time(p.at) : "") },
        { key: "flight", sort: (p) => p.flight || p.hex, show: (p) => p.flight || p.hex },
        { key: "altitude", sort: (p) => p.altitude, show: (p) => this._height(p, text) || "" },
        { key: "distance", sort: (p) => p.distance, show: (p) => this._distance(p.distance) || "" },
        { key: "type", sort: (p) => p.aircraft_type, show: (p) => p.aircraft_type || "", wide: true },
        { key: "duration", sort: (p) => p.duration, show: (p) => figure(p.duration, minutes), wide: true },
      ];
    }
    return [
      { key: "flight", sort: (p) => p.flight || p.hex, show: (p) => p.flight || p.hex },
      { key: "altitude", sort: (p) => (p.on_ground ? 0 : p.altitude), show: (p) => this._height(p, text) || "" },
      { key: "distance", sort: (p) => p.distance, show: (p) => this._distance(p.distance) || "" },
      { key: "bearing", sort: (p) => p.bearing, show: (p) => figure(p.bearing, (b) => `${b}°`) },
      { key: "type", sort: (p) => p.aircraft_type, show: (p) => p.aircraft_type || "", wide: true },
      { key: "rssi", sort: (p) => p.rssi, show: (p) => figure(p.rssi, (r) => this._number(r, 1)), wide: true },
    ];
  }

  _drawTable(text = strings(this._hass)) {
    const columns = this._columns(text);
    const cell = (column) =>
      [column.wide && "wide", !["flight", "type", "at"].includes(column.key) && "number"].filter(Boolean).join(" ") ||
      undefined;
    const language = this._hass.locale && this._hass.locale.language;
    if (this._tableLanguage !== language) {
      this._tableLanguage = language;
      this._search = el("input", {
        type: "search",
        placeholder: text.search,
        "aria-label": text.search,
        oninput: (event) => {
          this._query = event.target.value.trim().toLowerCase();
          this._drawTable();
        },
      });
      this._search.value = this._query;
      this._head = el("tr");
      this._rows = el("tbody");
      this._tableTitle = el("div", { class: "table-title" });
      // Faded at the bottom while there is more to scroll to.
      this._scroll = el(
        "div",
        { class: "scroll", onscroll: () => this._fadeTable() },
        el("table", {}, el("thead", {}, this._head), this._rows),
      );
      this._tableBox.replaceChildren(this._tableTitle, this._search, this._scroll);
    }

    const { key, descending } = this._sort;
    this._head.replaceChildren(
      ...columns.map((column) =>
        el(
          "th",
          {
            class: cell(column),
            "aria-sort": column.key === key ? (descending ? "descending" : "ascending") : undefined,
            onclick: () => {
              this._sort = { key: column.key, descending: column.key === key && !descending };
              this._drawTable();
            },
          },
          text[`col_${column.key}`],
          column.key === key ? (descending ? " ▾" : " ▴") : "",
        ),
      ),
    );

    const by = columns.find((column) => column.key === key).sort;
    const unknown = (value) => value === undefined || value === null;
    const query = this._query;
    const sensor = this._passages() && this._state(this._found && this._found.passages);
    const source = this._passages()
      ? ((sensor && Array.isArray(sensor.attributes.passages) && sensor.attributes.passages) || []).map((p) =>
          this._fromSensors(p, sensor),
        )
      : (this._sky && this._sky.aircraft) || [];
    const planes = source
      .filter(
        (p) =>
          !query ||
          [p.flight, p.registration, p.hex, p.aircraft_type].some((v) => v && v.toLowerCase().includes(query)),
      )
      .sort((a, b) => {
        const [x, y] = [by(a), by(b)];
        // Unknown last, whichever way round.
        if (unknown(x) || unknown(y)) return unknown(x) - unknown(y);
        const order = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
        return descending ? -order : order;
      });

    // A passage opens on its own; an aircraft in the air is picked on the radar.
    const board = this._passages();
    const open = (p) => (board ? this._showPassage(p, text) : this._select(p.hex));
    this._rows.replaceChildren(
      ...planes.map((p) =>
        el(
          "tr",
          {
            class: [p.hex === this._selected && "selected", mark(p)].filter(Boolean).join(" ") || undefined,
            "data-hex": p.hex,
            tabindex: board ? "0" : undefined,
            onclick: () => open(p),
            onkeydown: (event) => {
              if (board && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                open(p);
              }
            },
          },
          columns.map((column) => el("td", { class: cell(column) }, column.show(p))),
        ),
      ),
    );
    if (!planes.length) {
      const none = this._passages() ? text.no_passages : text.no_positions;
      this._rows.append(el("tr", {}, el("td", { colspan: columns.length, class: "none" }, none)));
    }
    // A title of its own, unless the dashboard gave the card one.
    this._tableTitle.hidden = Boolean(this._config.title);
    this._tableTitle.replaceChildren(
      el("span", {}, board ? text.title_passages : text.title_aircraft),
      el("span", { class: "count" }, this._number(source.length, 0)),
    );
    this._fadeTable();
  }

  _fadeTable() {
    const box = this._scroll;
    if (box) box.classList.toggle("more", box.scrollHeight - box.scrollTop - box.clientHeight > 1);
  }

  // A passage on its own: on a dashboard without the radar there is nowhere
  // else to show it. Its photo is asked for when the station looks them up.
  _showPassage(p, text) {
    if (!this._dialog) {
      this._dialog = el("dialog", {
        class: "passage",
        "aria-labelledby": "passage-name",
        // The dialog itself is only what lies around its content.
        onclick: (event) => event.target === this._dialog && this._dialog.close(),
        onclose: () => {
          const row = this._rows.querySelector(`tr[data-hex="${this._shown}"]`);
          this._shown = null;
          if (row) row.focus({ preventScroll: true });
        },
      });
      this.shadowRoot.append(this._dialog);
    }
    this._shown = p.hex;
    const language = this._hass.locale && this._hass.locale.language;
    const facts = [
      [text.col_at, p.at && new Date(p.at).toLocaleTimeString(language, { hour: "2-digit", minute: "2-digit" })],
      [text.col_duration, typeof p.duration === "number" && minutes(p.duration)],
      [text.closest, this._distance(p.distance)],
      [text.col_altitude, this._height(p, text)],
      [text.strongest, typeof p.peak_rssi === "number" && `${this._number(p.peak_rssi, 1)} dBFS`],
    ].filter(([, value]) => value);
    const photo = el("div", { class: "passage-photo" });
    this._dialog.replaceChildren(
      el(
        "div",
        // Focus on the window rather than its button, which would show a ring on a tap.
        { class: "passage-box", tabindex: "-1", autofocus: true },
        el(
          "div",
          { class: "passage-head" },
          el("div", { class: "primary", id: "passage-name" }, p.flight || p.hex, p.airline ? ` · ${p.airline}` : ""),
          el("button", { class: "close", "aria-label": text.close, onclick: () => this._dialog.close() }, "×"),
        ),
        photo,
        el(
          "div",
          { class: "secondary" },
          [p.description || p.aircraft_type, p.registration, p.hex.toUpperCase()].filter(Boolean).join(" · "),
        ),
        p.route ? el("div", { class: "secondary" }, p.route) : null,
        el(
          "dl",
          {},
          facts.flatMap(([name, value]) => [el("dt", {}, name), el("dd", {}, value)]),
        ),
      ),
    );
    if (!this._dialog.open) this._dialog.showModal();
    // Not under a borrowed address: the photo would be of another airframe.
    if (p.pia || !this._found || !this._hass.callWS) return;
    this._hass
      .callWS({ type: LOOK_UP_PHOTO, device_id: this._found.device, hex: p.hex })
      .then((answer) => {
        const src = safeUrl(answer.photo);
        const link = safeUrl(answer.photo_link);
        if (this._shown !== p.hex || !src || !link || !answer.photographer) return;
        // Credited and linked, as Planespotters asks, like the overhead one.
        photo.replaceChildren(
          el(
            "a",
            { class: "photo", href: link, target: "_blank", rel: "noopener" },
            el("img", { src, alt: p.flight || p.hex }),
          ),
          el(
            "div",
            { class: "credit" },
            `${text.photo}: ${answer.photographer} / `,
            el("a", { href: link, target: "_blank", rel: "noopener" }, "Planespotters.net"),
          ),
        );
      })
      .catch(() => {});
  }

  // --- The station ----------------------------------------------------------

  _status(found, text) {
    const shown = (entry) => {
      const state = this._state(entry);
      if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
      return this._hass.formatEntityState ? this._hass.formatEntityState(state) : state.state;
    };
    const line = el("div", { class: "status" });
    const figures = [
      [
        found.received,
        found.received && shown(found.received) && `${shown(found.received)} ${text.received}`,
        "mdi:airplane",
      ],
      [found.rate, shown(found.rate), "mdi:message-flash-outline"],
      [found.range, shown(found.range), "mdi:radar"],
      // How far the aircraft stand above the noise, in one figure: what a
      // change to the gain or the antenna is judged by.
      [found.snr, found.snr && shown(found.snr) && `S/N ${shown(found.snr)}`, "mdi:signal"],
    ].filter(([, value]) => value);
    for (const [entry, value, icon] of figures) {
      line.append(
        el(
          "span",
          { class: "figures badge", role: "button", tabindex: "0", onclick: this._moreInfo(entry) },
          el("ha-icon", { icon }),
          value,
        ),
      );
    }
    for (const entry of found.feeds) {
      const state = this._state(entry);
      if (!state) continue;
      const good = state.state === "on" || state.state === "green";
      const warn = state.state === "amber";
      const network = entry.translation_key === "piaware_feed" ? "FlightAware" : "Flightradar24";
      line.append(
        el(
          "span",
          {
            class: `feed badge ${good ? "good" : warn ? "warn" : "bad"}`,
            role: "button",
            tabindex: "0",
            title: this._hass.formatEntityState ? this._hass.formatEntityState(state) : state.state,
            onclick: this._moreInfo(entry),
          },
          el("ha-icon", {
            icon: good ? "mdi:check-circle" : warn ? "mdi:alert-circle" : "mdi:close-circle",
          }),
          network,
        ),
      );
    }
    return line;
  }
}

// Tags the stylesheet so Prettier formats it; String.raw returns it unchanged.
const css = String.raw;

const STYLE = css`
  ha-card {
    display: block;
    overflow: hidden;
    /* The theme's colour is for the station and what is picked; the map stays neutral. */
    --adsb-water: #4a90c8;
    --adsb-coverage: var(--primary-text-color);
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .side-by-side .layout.with-sky {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  }
  .side-by-side .layout.with-sky .sky {
    border-right: 1px solid var(--divider-color);
    border-bottom: none;
  }
  .sky {
    padding: 12px 12px 8px;
    border-bottom: 1px solid var(--divider-color);
  }
  .sky[hidden] {
    display: none;
  }
  .radar {
    display: block;
    width: 100%;
    max-height: 440px;
    margin: 0 auto;
  }
  .radar .scope {
    fill: var(--secondary-background-color, rgba(127, 127, 127, 0.08));
    stroke: var(--divider-color);
  }
  .radar .ring {
    fill: none;
    stroke: var(--divider-color);
  }
  .radar .near {
    fill: none;
    stroke: var(--primary-color);
    stroke-dasharray: 4 4;
    opacity: 0.7;
  }
  .radar text {
    fill: var(--secondary-text-color);
    font-size: 11px;
    font-family: inherit;
  }
  .radar .compass {
    text-anchor: middle;
    font-weight: 500;
  }
  .radar .quiet {
    text-anchor: middle;
    font-size: 13px;
  }
  .radar .home {
    fill: var(--primary-color);
    stroke: var(--card-background-color, #fff);
    stroke-width: 2;
  }
  .radar .trails line {
    stroke-width: 2;
    stroke-linecap: round;
    opacity: 0.65;
  }
  .radar .plane {
    cursor: pointer;
  }
  .radar .plane path {
    stroke: var(--card-background-color, #000);
    stroke-width: 0.8;
  }
  .radar .callsign {
    fill: var(--primary-text-color);
    font-size: 10.5px;
    font-weight: 500;
    paint-order: stroke;
    stroke: var(--card-background-color, #fff);
    stroke-width: 3px;
  }
  .radar .route polyline {
    fill: none;
    stroke: var(--primary-text-color);
    stroke-width: 1.8;
    stroke-linejoin: round;
  }
  .radar .route .flown {
    opacity: 0.55;
  }
  .radar .route .ahead {
    stroke-dasharray: 5 4;
    opacity: 0.85;
  }
  .radar .heading line {
    stroke: var(--primary-text-color);
    stroke-width: 1.4;
    stroke-dasharray: 2 3;
    opacity: 0.8;
  }
  .radar .heading .closest {
    fill: var(--card-background-color, #fff);
    stroke: var(--primary-color);
    stroke-width: 2;
  }
  .radar .fields circle {
    fill: var(--secondary-text-color);
  }
  .radar .fields text {
    fill: var(--secondary-text-color);
    font-size: 9.5px;
    paint-order: stroke;
    stroke: var(--card-background-color, #fff);
    stroke-width: 3px;
  }
  .radar .airport circle {
    fill: var(--card-background-color, #fff);
    stroke: var(--primary-text-color);
    stroke-width: 2;
  }
  .radar .airport text {
    fill: var(--primary-text-color);
    font-size: 11px;
    font-weight: 600;
    paint-order: stroke;
    stroke: var(--card-background-color, #fff);
    stroke-width: 3px;
  }
  .radar .halo {
    fill: none;
    stroke: var(--primary-text-color);
    stroke-width: 1.5;
    opacity: 0.6;
  }
  .radar .land {
    fill: var(--secondary-background-color, #eee);
  }
  .radar.streets .ring {
    stroke: var(--primary-text-color);
    stroke-opacity: 0.35;
  }
  .radar .basemap path {
    fill: none;
    vector-effect: non-scaling-stroke;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .radar .basemap .water {
    fill: var(--adsb-water);
    fill-opacity: 0.34;
  }
  .radar .basemap .river {
    stroke: var(--adsb-water);
    stroke-opacity: 0.5;
  }
  .radar .basemap .motorway {
    stroke: var(--secondary-text-color);
    stroke-opacity: 0.4;
    stroke-width: 1.2;
  }
  .radar .basemap .road {
    stroke: var(--secondary-text-color);
    stroke-opacity: 0.25;
    stroke-width: 0.8;
  }
  .radar .basemap .country {
    stroke: var(--primary-text-color);
    stroke-opacity: 0.45;
    stroke-width: 1.2;
  }
  .radar .basemap .state {
    stroke: var(--primary-text-color);
    stroke-opacity: 0.18;
  }
  .radar .basemap .place {
    font-size: 10px;
    text-anchor: middle;
    dominant-baseline: middle;
    fill: var(--secondary-text-color);
    paint-order: stroke;
    stroke: var(--secondary-background-color, #eee);
    stroke-width: 3px;
    stroke-linejoin: round;
  }
  .radar .basemap .place.big {
    fill: var(--primary-text-color);
    fill-opacity: 0.75;
  }
  .radar.streets .distance {
    fill: var(--primary-text-color);
    paint-order: stroke;
    stroke: var(--card-background-color, #fff);
    stroke-width: 3px;
  }
  .radar.streets .trails line {
    opacity: 0.85;
    stroke-width: 2.5;
  }
  .scope-box {
    position: relative;
    max-width: 440px;
    margin: 0 auto;
  }
  .attribution {
    position: absolute;
    right: 8px;
    bottom: 8px;
    padding: 0 4px;
    border-radius: var(--ha-border-radius-sm, 4px);
    font-size: var(--ha-font-size-xs, 10px);
    color: var(--secondary-text-color);
    background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #fff)) 85%, transparent);
  }
  .attribution a {
    color: inherit;
  }
  .radar .coverage {
    fill: var(--adsb-coverage);
    fill-opacity: 0.07;
    stroke: var(--adsb-coverage);
    stroke-opacity: 0.35;
    stroke-linejoin: round;
  }
  .kinds {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    margin: var(--ha-space-3, 12px) 0 var(--ha-space-2, 8px);
  }
  .kind {
    font: inherit;
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 var(--ha-space-3, 12px);
    border-radius: var(--ha-border-radius-md, 8px);
    border: 1px solid var(--divider-color);
    background: none;
    color: var(--primary-text-color);
    cursor: pointer;
    --mdc-icon-size: 18px;
  }
  .kind[aria-pressed="true"] {
    padding-inline-start: var(--ha-space-2, 8px);
    border-color: transparent;
    background: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.15);
  }
  .kind .count {
    font-weight: var(--ha-font-weight-normal, 400);
    color: var(--secondary-text-color);
  }
  .kind.none {
    opacity: 0.5;
  }
  .unplaced {
    font-size: var(--ha-font-size-m, 14px);
    padding: 0 var(--ha-space-1, 4px);
    color: var(--secondary-text-color);
  }
  .legend {
    position: absolute;
    left: 8px;
    bottom: 8px;
    width: min(50%, 230px);
    padding: 6px var(--ha-space-2, 8px) 2px;
    border-radius: var(--ha-border-radius-md, 8px);
    font-size: var(--ha-font-size-xs, 10px);
    color: var(--secondary-text-color);
    background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #fff)) 90%, transparent);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }
  .legend .keys {
    display: flex;
    flex-wrap: wrap;
    gap: 2px var(--ha-space-2, 8px);
    margin-bottom: 4px;
  }
  .legend .key {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }
  .legend .dot.ground {
    background: ${GROUND_COLOR};
  }
  .legend .area {
    width: 10px;
    height: 8px;
    border: 1px solid color-mix(in srgb, var(--adsb-coverage) 35%, transparent);
    background: color-mix(in srgb, var(--adsb-coverage) 7%, transparent);
    border-radius: 2px;
  }
  .legend .bar {
    height: 4px;
    border-radius: 2px;
  }
  .legend .ticks {
    position: relative;
    height: 1.4em;
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }
  .legend .ticks span {
    position: absolute;
    white-space: nowrap;
  }
  .whole {
    white-space: nowrap;
  }
  .picked {
    padding: var(--ha-space-2, 8px) 0 var(--ha-space-3, 12px);
  }
  .picked .head {
    display: flex;
    align-items: center;
    gap: var(--ha-space-3, 12px);
  }
  .badge-icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    color: var(--tint);
    background: color-mix(in srgb, var(--tint) 20%, transparent);
    --mdc-icon-size: 24px;
  }
  .picked .names {
    flex: 1;
    min-width: 0;
  }
  .picked .title {
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: 1.25;
  }
  .picked .sub,
  .picked .mark,
  .picked .failed,
  .picked .fine,
  .picked .route-line {
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
  }
  .picked .sub {
    margin-top: 2px;
  }
  .picked .mark,
  .picked .failed,
  .picked .route-line {
    margin-top: var(--ha-space-2, 8px);
  }
  .picked .route {
    display: flex;
    align-items: center;
    gap: var(--ha-space-3, 12px);
    margin-top: var(--ha-space-4, 16px);
  }
  .picked .airport b {
    display: block;
    font-size: var(--ha-font-size-xl, 20px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: 1.2;
  }
  .picked .airport span {
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
  }
  .picked .airport.to {
    text-align: end;
  }
  .picked .route .line {
    flex: 1;
    position: relative;
    height: 2px;
    background: repeating-linear-gradient(90deg, var(--divider-color) 0 6px, transparent 6px 10px);
  }
  .picked .route .line ha-icon {
    position: absolute;
    left: 50%;
    top: 50%;
    padding: 0 var(--ha-space-1, 4px);
    transform: translate(-50%, -50%) rotate(45deg);
    color: var(--secondary-text-color);
    background: var(--ha-card-background, var(--card-background-color, #fff));
    --mdc-icon-size: 18px;
  }
  .picked .stats {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    gap: var(--ha-space-2, 8px);
    margin-top: var(--ha-space-4, 16px);
  }
  .picked .stat,
  .picked .tip {
    border-radius: var(--ha-border-radius-lg, 12px);
    background: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.05);
  }
  .picked .stat {
    padding: 10px var(--ha-space-3, 12px);
  }
  .picked .stat .caption {
    display: block;
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
  }
  .picked .stat b {
    font-size: var(--ha-font-size-xl, 20px);
    font-weight: var(--ha-font-weight-medium, 500);
    white-space: nowrap;
  }
  .picked .stat small {
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
  }
  .picked .tip {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: var(--ha-space-2, 8px);
    padding: 10px var(--ha-space-3, 12px);
    font-size: var(--ha-font-size-m, 14px);
    --mdc-icon-size: 20px;
  }
  .picked .tip ha-icon {
    color: var(--primary-color);
  }
  .picked .fine {
    margin-top: 10px;
  }
  .empty {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    color: var(--secondary-text-color);
  }
  .overhead {
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px);
  }
  .label {
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
  }
  .details {
    display: flex;
    align-items: center;
    gap: var(--ha-space-3, 12px);
    cursor: pointer;
  }
  .details .photo,
  .details .badge-icon {
    flex: none;
  }
  .photo img {
    display: block;
    width: 56px;
    height: 56px;
    object-fit: cover;
    border-radius: var(--ha-border-radius-md, 8px);
  }
  .details .badge-icon {
    width: 56px;
    height: 56px;
    border-radius: var(--ha-border-radius-md, 8px);
    --mdc-icon-size: 28px;
  }
  .lines {
    flex: 1;
    min-width: 0;
  }
  .primary {
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: 1.4;
  }
  .secondary {
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
    white-space: pre-wrap;
  }
  .lines .primary,
  .lines .secondary {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .aside {
    flex: none;
    text-align: end;
    font-size: var(--ha-font-size-s, 12px);
    line-height: 1.6;
    color: var(--secondary-text-color);
    font-variant-numeric: tabular-nums;
  }
  .credit {
    margin-top: var(--ha-space-1, 4px);
    font-size: var(--ha-font-size-xs, 10px);
    color: var(--secondary-text-color);
  }
  .credit a {
    color: inherit;
  }
  .nearby {
    padding: 8px 16px;
    border-top: 1px solid var(--divider-color);
  }
  .row {
    display: grid;
    grid-template-columns: 24px auto 1fr auto auto;
    gap: 8px;
    align-items: center;
    padding: 4px 0;
    cursor: pointer;
  }
  .row ha-icon {
    --mdc-icon-size: 20px;
  }
  .flight {
    font-weight: 500;
  }
  .what {
    color: var(--secondary-text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .figure {
    color: var(--secondary-text-color);
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .table {
    padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px);
  }
  .table[hidden],
  .table-title[hidden] {
    display: none;
  }
  .table-title {
    display: flex;
    align-items: baseline;
    padding: var(--ha-space-1, 4px) 0 var(--ha-space-3, 12px);
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
  }
  .table-title .count {
    margin-inline-start: auto;
    font-size: var(--ha-font-size-s, 12px);
    font-weight: var(--ha-font-weight-normal, 400);
    color: var(--secondary-text-color);
  }
  .table input {
    box-sizing: border-box;
    width: 100%;
    height: 40px;
    margin-bottom: var(--ha-space-2, 8px);
    padding: 0 var(--ha-space-3, 12px);
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-border-radius-md, 8px);
    background: var(--ha-card-background, var(--card-background-color));
    color: var(--primary-text-color);
    font: inherit;
    font-size: var(--ha-font-size-m, 14px);
  }
  /* The header and eight whole rows; faded at the foot while more follow. */
  .scroll {
    max-height: calc(33px + 8 * 41px);
    overflow-y: auto;
  }
  .scroll.more {
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 40px), transparent);
    mask-image: linear-gradient(to bottom, #000 calc(100% - 40px), transparent);
  }
  .table table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--ha-font-size-m, 14px);
  }
  .table th {
    position: sticky;
    top: 0;
    height: 32px;
    background: var(--ha-card-background, var(--card-background-color));
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s, 12px);
    font-weight: var(--ha-font-weight-medium, 500);
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
  }
  .table th,
  .table td {
    padding: 0 var(--ha-space-2, 8px);
    white-space: nowrap;
  }
  .table td {
    height: 40px;
    border-top: 1px solid var(--divider-color);
  }
  .table .number {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .table tbody tr {
    cursor: pointer;
  }
  .radar .distress,
  .radar .watch {
    fill: none;
    stroke-width: 2.5;
  }
  .radar .distress,
  .picked .distress {
    stroke: var(--error-color, #db4437);
    color: var(--error-color, #db4437);
  }
  .radar .watch,
  .picked .watch {
    stroke: var(--primary-color);
    color: var(--primary-color);
  }
  .watch-button {
    flex: none;
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border: none;
    border-radius: 50%;
    background: none;
    color: var(--secondary-text-color);
    cursor: pointer;
    --mdc-icon-size: 24px;
  }
  .watch-button:hover {
    background: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.08);
  }
  .watch-button[disabled] {
    opacity: 0.5;
  }
  .picked .failed {
    color: var(--error-color, #db4437);
  }
  .table tr.distress td {
    background: color-mix(in srgb, var(--error-color, #db4437) 12%, transparent);
  }
  .table tr.watch td {
    background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  }
  .table tbody tr:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: -2px;
  }
  dialog.passage {
    width: min(420px, calc(100% - 32px));
    max-height: calc(100% - 32px);
    padding: 0;
    border: none;
    border-radius: var(--ha-card-border-radius, 12px);
    background: var(--ha-card-background, var(--card-background-color, #fff));
    color: var(--primary-text-color);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }
  dialog.passage::backdrop {
    background: rgba(0, 0, 0, 0.4);
  }
  .passage-box {
    padding: 12px 16px 16px;
    outline: none;
  }
  .passage-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
  }
  .passage .close {
    border: none;
    background: none;
    color: var(--secondary-text-color);
    font-size: 1.6em;
    line-height: 1;
    padding: 4px 8px;
    cursor: pointer;
  }
  .passage-photo:empty {
    display: none;
  }
  .passage dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 16px;
    margin: 12px 0 0;
  }
  .passage dt {
    color: var(--secondary-text-color);
  }
  .passage dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  .table tr.selected td {
    background: var(--secondary-background-color);
  }
  .table .none {
    color: var(--secondary-text-color);
    text-align: center;
  }
  .narrow .table .wide {
    display: none;
  }
  .status-box[hidden] {
    display: none;
  }
  /* Wrapped and centred; on a phone one row that scrolls sideways rather
     than taking three lines. */
  .status {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--ha-space-2, 8px);
    padding: var(--ha-space-3, 12px) var(--ha-space-3, 12px) 0;
  }
  .narrow .status {
    flex-wrap: nowrap;
    justify-content: normal;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .status::-webkit-scrollbar {
    display: none;
  }
  /* Centred while it fits, without hiding the start once it does not. */
  .narrow .status > :first-child {
    margin-inline-start: auto;
  }
  .narrow .status > :last-child {
    margin-inline-end: auto;
  }
  /* Home Assistant's badge: a pill with an icon, its text medium and small. */
  .badge {
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    height: 36px;
    padding: 0 var(--ha-space-3, 12px);
    border-radius: 18px;
    flex: none;
    white-space: nowrap;
    border: 1px solid var(--divider-color, #e0e0e0);
    background: var(--ha-card-background, var(--card-background-color, #fff));
    font-size: var(--ha-font-size-s, 12px);
    font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color);
    font-variant-numeric: tabular-nums;
    cursor: pointer;
    --mdc-icon-size: 18px;
  }
  .badge ha-icon {
    color: var(--secondary-text-color);
  }
  .feed.good ha-icon {
    color: var(--success-color, #43a047);
  }
  .feed.warn ha-icon {
    color: var(--warning-color, #ffa600);
  }
  .feed.bad ha-icon {
    color: var(--error-color, #db4437);
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
`;

// The same card with only the table, so it can go anywhere on a dashboard.
class AdsbStationTableCard extends AdsbStationCard {
  constructor() {
    super();
    this._onlyTable = true;
  }

  static getConfigForm() {
    const form = super.getConfigForm();
    const text = strings(window.__adsbStationHass);
    const list = {
      name: "list",
      selector: {
        select: { mode: "dropdown", options: LISTS.map((value) => ({ value, label: text[`list_${value}`] })) },
      },
    };
    return {
      ...form,
      schema: [...form.schema.filter((field) => ["device_id", "title", "palette"].includes(field.name)), list],
    };
  }

  setConfig(config) {
    const list = config && LISTS.includes(config.list) ? config.list : "now";
    // A board reads newest first; the sky nearest first.
    if (list !== (this._config && this._config.list)) {
      this._sort = list === "passages" ? { key: "at", descending: true } : { key: "distance", descending: false };
    }
    super.setConfig({ ...(config || {}), list, map: "none" });
  }

  getCardSize() {
    return 6;
  }
}

if (!customElements.get(TABLE_CARD)) {
  customElements.define(TABLE_CARD, AdsbStationTableCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: TABLE_CARD,
    name: STRINGS.en.table_name,
    description: STRINGS.en.table_description,
    preview: true,
    documentationURL: "https://github.com/mirkin-pixel/ha-adsb-station/blob/main/docs/en/dashboards.md",
  });
}

if (!customElements.get(CARD)) {
  customElements.define(CARD, AdsbStationCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD,
    name: STRINGS.en.name,
    description: STRINGS.en.description,
    preview: true,
    documentationURL: "https://github.com/mirkin-pixel/ha-adsb-station/blob/main/docs/en/dashboards.md",
  });
}
