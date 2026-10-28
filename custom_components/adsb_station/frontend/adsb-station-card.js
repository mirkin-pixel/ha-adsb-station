/*
 * ADS-B Station card.
 *
 * Served by the integration itself and loaded on every dashboard, so there is
 * nothing to download or add as a resource. It finds the station's entities by
 * what they are rather than by their IDs, which are in whatever language Home
 * Assistant was set to when they were made: every entity of this integration
 * carries a fixed translation key, and hass.entities says which is which.
 *
 * The sky on top is not an entity. The integration sends every aircraft with a
 * position over a websocket subscription while the card is open, and the card
 * remembers where each one has been for the trail behind it. Nothing of either
 * is recorded.
 *
 * Plain JavaScript on purpose. There is no build step, so what is in the
 * repository is exactly what runs, and it ships in the integration's zip.
 */

const DOMAIN = "adsb_station";
const CARD = "adsb-station-card";
const SUBSCRIBE = `${DOMAIN}/subscribe_aircraft`;
const LOOK_UP_ROUTE = `${DOMAIN}/look_up_route`;
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
    no_positions: "No aircraft with a position",
    compass: ["N", "E", "S", "W"],
    sky: "Aircraft around the station",
    show_nearby: "Show the aircraft nearby",
    max_nearby: "How many nearby to show at most",
    show_status: "Show how the station is doing",
    title: "Title",
    map: "Map",
    map_radar: "Radar",
    map_streets: "Map with streets",
    map_none: "No map",
    map_scale: "Radar scale",
    scale_aircraft: "Automatic, to fit the aircraft",
    scale_coverage: "Automatic, to fit the range records",
    scale_fixed: "Fixed",
    map_range: "Fixed range in km",
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
    no_positions: "Geen toestellen met een positie",
    compass: ["N", "O", "Z", "W"],
    sky: "Toestellen rond het station",
    show_nearby: "Toestellen dichtbij tonen",
    max_nearby: "Hoeveel toestellen dichtbij maximaal",
    show_status: "Tonen hoe het station ervoor staat",
    title: "Titel",
    map: "Kaart",
    map_radar: "Radar",
    map_streets: "Landkaart",
    map_none: "Geen kaart",
    map_scale: "Schaal van de radar",
    scale_aircraft: "Automatisch, passend bij de toestellen",
    scale_coverage: "Automatisch, passend bij de bereikrecords",
    scale_fixed: "Vast",
    map_range: "Vast bereik in km",
  },
};

// Climbing or descending faster than this, in feet per minute, gets an arrow.
// The same line the map icons draw.
const CLIMB_RATE_SHOWN = 500;
const DEFAULT_MAX_NEARBY = 5;
const MAP_STYLES = ["radar", "map", "none"];

// How long a trail is, and how long an aircraft that stopped being sent is
// remembered before its trail goes as well.
const TRAIL_SECONDS = 300;
const FORGET_SECONDS = 60;
// The radar's outer ring snaps to one of these, in kilometres, unless it is
// fixed: to the aircraft in the sky now, or to the range records as well.
const RANGE_STEPS = [5, 10, 25, 50, 100, 150, 200, 300, 400, 500];
const SCALES = ["aircraft", "coverage", "fixed"];
const DEFAULT_FIXED_RANGE = 100;
// The compass sectors the station keeps a range record for, clockwise from
// north, each centred on its direction.
const SECTORS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"];
const KILOMETRES = { km: 1, m: 0.001, mi: 1.609344, ft: 0.0003048, nmi: 1.852 };

// From the ground up: warm and low, cool and high, so a glance tells an
// approach from an overflight. Hue by altitude in feet, in between linear,
// in steps that follow the phases of a flight: the circuit, the approach,
// the climb, and cruise.
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

// Drawn pointing north in a box of 24 around the origin, and turned to the
// track. Three outlines are enough to tell the sky apart: an airliner, a light
// aircraft with straight wings, and a helicopter with its rotor.
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
  // Everything that reaches the page goes through textContent or a property,
  // never through innerHTML: the attributes come from aircraft and from other
  // people's servers, and none of it is markup.
  const node = document.createElement(tag);
  return fill(node, attributes, children);
}

function svg(tag, attributes, ...children) {
  return fill(document.createElementNS(SVG, tag), attributes, children);
}

function fill(node, attributes, children) {
  for (const [key, value] of Object.entries(attributes || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.setAttribute("class", value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
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

function altitudeColor(altitude, onGround) {
  if (onGround || typeof altitude !== "number") return GROUND_COLOR;
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

// Only an https address is put on the page as a link or an image. Everything
// the photo lookup hands over is, and anything else is left out rather than
// followed.
function safeUrl(value) {
  return typeof value === "string" && value.startsWith("https://") ? value : null;
}

function numeric(state) {
  if (!state) return null;
  const value = Number.parseFloat(state.state);
  return Number.isFinite(value) ? value : null;
}

// The map under the sky, in the projection web map tiles are drawn in. The
// zoom is whatever puts the radar's range at its reach, between whole zoom
// levels too: the tiles of the level below are drawn larger to make up the
// difference.
const TILE_SIZE = 256;
const EQUATOR_METRES_PER_PIXEL = 156543.03392;
// OpenStreetMap's raster tiles stop here.
const MAX_TILE_ZOOM = 19;
// Home Assistant serves OpenStreetMap's tiles itself since 2026.9, behind a
// token that its frontend asks for over the websocket and that is good for
// half an hour. Before that there is no proxy, and the tiles come from
// OpenStreetMap directly, as Home Assistant's own demo has them.
const PROXY_TILES = (z, x, y, token) => `/api/map_tiles/raster/${z}/${x}/${y}.png?token=${encodeURIComponent(token)}`;
const UPSTREAM_TILES = (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`;
const TOKEN_REFRESH = 20 * 60 * 1000;

function mercatorView(origin, range, reach, centre, size) {
  const [latitude, longitude] = origin;
  const shrink = Math.cos((latitude * Math.PI) / 180);
  const zoom = Math.min(
    MAX_TILE_ZOOM,
    Math.max(1, Math.log2((EQUATOR_METRES_PER_PIXEL * shrink * reach) / (range * 1000)))
  );
  const world = TILE_SIZE * 2 ** zoom;
  const toWorld = (lat, lon) => {
    const phi = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
    return [
      ((lon + 180) / 360) * world,
      ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * world,
    ];
  };
  const [cx, cy] = toWorld(latitude, longitude);
  const project = (lat, lon) => {
    const [x, y] = toWorld(lat, lon);
    return [centre + x - cx, centre + y - cy];
  };
  const perKm = 1000 / ((EQUATOR_METRES_PER_PIXEL * shrink) / 2 ** zoom);

  // One level deeper than the zoom, drawn smaller, so the map stays sharp on
  // a screen with more pixels than points: there are no @2x tiles.
  const tiles = (url) => {
    const level = Math.min(MAX_TILE_ZOOM, Math.floor(zoom) + 1);
    const side = TILE_SIZE * 2 ** (zoom - level);
    const count = 2 ** level;
    const left = cx - centre;
    const top = cy - centre;
    const found = [];
    for (let ty = Math.floor(top / side); ty <= Math.floor((top + size) / side); ty++) {
      if (ty < 0 || ty >= count) continue;
      for (let tx = Math.floor(left / side); tx <= Math.floor((left + size) / side); tx++) {
        const wrapped = ((tx % count) + count) % count;
        found.push({
          href: url(level, wrapped, ty),
          // A hair larger than the tile, so no seam shows between two.
          x: +(tx * side - left).toFixed(2),
          y: +(ty * side - top).toFixed(2),
          size: +(side + 0.5).toFixed(2),
        });
      }
    }
    return found;
  };
  return { perKm, project, tiles, key: `${zoom}|${cx}|${cy}` };
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
              options: MAP_STYLES.map((value) => ({ value, label: text[`map_${value === "map" ? "streets" : value}`] })),
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
          selector: { number: { min: 5, max: 500, mode: "box", unit_of_measurement: "km" } },
        },
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
    // hex → the points it was seen at, oldest first, and when it was last sent.
    this._trails = new Map();
    this._lastSent = new Map();
    this._sky = null;
    this._selected = null;
    // hex → the route asked for when it was tapped: its points, or null when
    // there is none, or pending while the answer is on its way.
    this._routes = new Map();
  }

  setConfig(config) {
    this._config = {
      map: "radar",
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
    const entities = Object.values(this._hass.entities || {}).filter(
      (entry) => entry.platform === DOMAIN
    );
    const overhead = entities.filter(
      (entry) =>
        entry.translation_key === "overhead_flight" &&
        (!this._config.device_id || entry.device_id === this._config.device_id)
    );
    if (!overhead.length) return null;
    const device = overhead[0].device_id;
    const on = (key) =>
      entities.find((entry) => entry.device_id === device && entry.translation_key === key);
    // A station commonly feeds several networks, each its own device, and the
    // feed status of every one of them belongs in the status line.
    const feeds = entities.filter(
      (entry) => entry.translation_key === "feed" || entry.translation_key === "piaware_feed"
    );
    return {
      device,
      overhead: overhead[0],
      nearby: on("aircraft_nearby"),
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
      this._card.append(el("div", { class: "layout" }, this._skyBox, this._body));
      this.shadowRoot.replaceChildren(el("style", {}, STYLE), this._card);
    }
    if (this._config.title) this._card.setAttribute("header", this._config.title);
    else this._card.removeAttribute("header");

    const showSky = Boolean(found) && this._config.map !== "none";
    this._card.querySelector(".layout").classList.toggle("with-sky", showSky);
    this._skyBox.hidden = !showSky;

    const body = [];
    if (!found) {
      body.push(el("div", { class: "empty" }, text.no_station));
    } else {
      body.push(this._overhead(found, text));
      if (this._config.show_nearby) body.push(this._nearby(found, text));
      if (this._config.show_status) body.push(this._status(found, text));
    }
    this._body.replaceChildren(...body.filter(Boolean));
    if (showSky) this._drawSky();
  }

  _moreInfo(entry) {
    return () => {
      if (!entry) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: entry.entity_id },
          bubbles: true,
          composed: true,
        })
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
      found && this._config.map !== "none" && this.isConnected && this._hass.connection
        ? found.device
        : null;
    if (wanted === this._following) return;
    this._unsubscribe();
    if (!wanted) return;
    this._following = wanted;
    this._sky = null;
    this._trails.clear();
    this._lastSent.clear();
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
    const subscription = this._subscription;
    this._subscription = null;
    this._following = null;
    if (subscription) subscription.then((unsubscribe) => unsubscribe()).catch(() => {});
  }

  _receive(sky) {
    this._sky = sky;
    const now = Date.now() / 1000;
    // The first sky brings where every aircraft has been lately, kept by the
    // integration, so a card that just opened does not start from nothing.
    if (sky.trails) {
      this._trails.clear();
      for (const [hex, points] of Object.entries(sky.trails)) {
        this._trails.set(
          hex,
          points.map(([lat, lon, altitude, t]) => ({ lat, lon, color: altitudeColor(altitude, altitude === null), t }))
        );
        this._lastSent.set(hex, now);
      }
    }
    for (const plane of sky.aircraft || []) {
      this._lastSent.set(plane.hex, now);
      const trail = this._trails.get(plane.hex) || [];
      const last = trail[trail.length - 1];
      if (!last || last.lat !== plane.latitude || last.lon !== plane.longitude) {
        trail.push({
          lat: plane.latitude,
          lon: plane.longitude,
          color: altitudeColor(plane.altitude, plane.on_ground),
          t: now,
        });
      }
      while (trail.length && trail[0].t < now - TRAIL_SECONDS) trail.shift();
      this._trails.set(plane.hex, trail);
    }
    for (const [hex, seen] of this._lastSent) {
      if (seen < now - FORGET_SECONDS) {
        this._lastSent.delete(hex);
        this._trails.delete(hex);
      }
    }
    if (this._skyBox && !this._skyBox.hidden) this._drawSky();
  }

  // --- The sky --------------------------------------------------------------

  _drawSky() {
    const text = strings(this._hass);
    const streets = this._config.map === "map";
    this._skyBox.replaceChildren(
      ...[
        this._radar(text, streets),
        streets ? this._attribution() : null,
        this._legend(text),
        this._picked(text),
      ].filter(Boolean)
    );
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
    if (mode === "fixed") return Number(this._config.map_range) > 0 ? Number(this._config.map_range) : DEFAULT_FIXED_RANGE;
    const furthest = Math.max(
      sky ? sky.radius || 0 : 0,
      ...((sky && sky.aircraft) || []).map((plane) => plane.distance || 0),
      // The records as well, so the whole shape of the coverage fits.
      ...(mode === "coverage" ? this._coverage() || [] : [])
    );
    // Held until the sky clearly fits a smaller ring, so one aircraft at the
    // edge coming and going does not make the whole radar breathe.
    if (this._range && furthest <= this._range && furthest > this._range * 0.6) return this._range;
    this._range = RANGE_STEPS.find((step) => step >= furthest) || RANGE_STEPS[RANGE_STEPS.length - 1];
    return this._range;
  }

  // The same drawing either way: on the radar's own scope, or with map
  // tiles under it. Home Assistant's map element can only draw entities and
  // dotted lines, so the outlines, the labels and the coverage would all be
  // lost on it; here the tiles are just the background of what is drawn
  // anyway, and everything sits exactly where it belongs on them.
  _radar(text, streets) {
    const sky = this._sky;
    const size = 400;
    const centre = size / 2;
    const reach = 184;
    const range = this._scale(sky);
    const origin = sky ? [sky.latitude, sky.longitude] : null;

    // Kilometres to pixels, and a position to a point in the drawing. On the
    // radar a plain flat projection around the station; on the map the one
    // the tiles are drawn in, so the two line up.
    let perKm = reach / range;
    let project = (lat, lon) => {
      const east = (lon - origin[1]) * 111.32 * Math.cos((origin[0] * Math.PI) / 180);
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

    const scope = svg("svg", {
      class: streets ? "radar streets" : "radar",
      viewBox: `0 0 ${size} ${size}`,
      role: "img",
      "aria-label": text.sky,
    });
    const shape = streets
      ? svg("rect", { x: 0, y: 0, width: size, height: size, rx: 12 })
      : svg("circle", { cx: centre, cy: centre, r: reach });
    scope.append(svg("defs", {}, svg("clipPath", { id: "scope" }, shape)));
    if (streets) {
      scope.append(svg("rect", { class: "land", x: 0, y: 0, width: size, height: size, "clip-path": "url(#scope)" }));
      if (tiles) scope.append(tiles);
    } else {
      scope.append(svg("circle", { class: "scope", cx: centre, cy: centre, r: reach }));
    }
    scope.append(
      svg("g", { "clip-path": "url(#scope)" },
        svg("circle", { class: "ring", cx: centre, cy: centre, r: (range / 2) * perKm }),
        svg("circle", { class: "ring", cx: centre, cy: centre, r: range * perKm }),
        streets ? null : svg("line", { class: "ring", x1: centre - reach, y1: centre, x2: centre + reach, y2: centre }),
        streets ? null : svg("line", { class: "ring", x1: centre, y1: centre - reach, x2: centre, y2: centre + reach })
      ),
      svg("text", { class: "distance", x: centre + 4, y: centre - (range / 2) * perKm - 4 }, `${this._number(range / 2, 1)} km`),
      svg("text", { class: "distance", x: centre + 4, y: centre - range * perKm + 14 }, `${this._number(range, 1)} km`)
    );
    const coverage = this._coverage();
    if (coverage) {
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
        svg("text", { class: "compass", x: centre - reach - 9, y: centre + 4 }, west)
      );
    }

    if (origin) {
      const trails = svg("g", { class: "trails", "clip-path": "url(#scope)" });
      for (const trail of this._trails.values()) {
        for (let i = 1; i < trail.length; i++) {
          const [x1, y1] = project(trail[i - 1].lat, trail[i - 1].lon);
          const [x2, y2] = project(trail[i].lat, trail[i].lon);
          trails.append(svg("line", { x1, y1, x2, y2, stroke: trail[i].color }));
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
          .map(([lat, lon]) => project(lat, lon).map((value) => value.toFixed(1)).join(","))
          .join(" ");
      const ends = [route.origin, route.destination];
      scope.append(
        svg(
          "g",
          { class: "route", "clip-path": "url(#scope)" },
          svg("polyline", { class: "flown", points: line([route.origin.latitude, route.origin.longitude], here) }),
          svg("polyline", { class: "ahead", points: line(here, [route.destination.latitude, route.destination.longitude]) }),
          ends.map((airport) => {
            const [x, y] = project(airport.latitude, airport.longitude);
            return svg(
              "g",
              { class: "airport", transform: `translate(${x.toFixed(1)} ${y.toFixed(1)})` },
              svg("circle", { r: 4 }),
              svg("text", { x: 7, y: 4 }, airport.code || "")
            );
          })
        )
      );
    }

    const planes = ((sky && sky.aircraft) || [])
      .map((plane) => ({ plane, at: project(plane.latitude, plane.longitude) }))
      .filter(({ at }) => inView(at));

    // Around the station the aircraft crowd together, and callsigns written
    // over each other read as none at all. The picked one is labelled first,
    // then the nearest; a label that would cover one already placed is left
    // off, and that aircraft can still be tapped for it.
    const labelled = new Set();
    const placed = [];
    const ranked = [...planes].sort(
      (a, b) =>
        (b.plane.hex === this._selected) - (a.plane.hex === this._selected) ||
        (a.plane.distance || 0) - (b.plane.distance || 0)
    );
    for (const { plane, at: [x, y] } of ranked) {
      const box = [x + 11, y - 18, x + 13 + 6.4 * String(plane.flight || plane.hex).length, y - 5];
      const covers = (other) => box[0] < other[2] && other[0] < box[2] && box[1] < other[3] && other[1] < box[3];
      if (placed.some(covers)) continue;
      placed.push(box);
      labelled.add(plane.hex);
    }

    // The highest drawn last, so the one overhead at cruising height is not
    // hidden under a trail far below it.
    for (const { plane, at: [x, y] } of [...planes].sort((a, b) => (a.plane.altitude || 0) - (b.plane.altitude || 0))) {
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
        svg("path", {
          d: path,
          fill: altitudeColor(plane.altitude, plane.on_ground),
          transform: `rotate(${Math.round(plane.track || 0)}) scale(${scale})`,
        }),
        labelled.has(plane.hex) ? svg("text", { class: "callsign", x: 12, y: -8 }, plane.flight || plane.hex) : null
      );
      scope.append(marker);
    }
    if (sky && !planes.length) {
      scope.append(svg("text", { class: "quiet", x: centre, y: centre + 30 }, text.no_positions));
    }
    return scope;
  }

  // The map tiles for a view, as one group that is kept while the view, the
  // token and the theme stay the same: drawn afresh on every poll, they would
  // load again every time. Nothing until it is known where they come from.
  _tiles(view) {
    const token = this._tileToken();
    if (token === undefined) return null;
    const dark = Boolean(this._hass.themes && this._hass.themes.darkMode);
    const key = `${view.key}|${token}|${dark}`;
    if (this._tileLayer && this._tileLayer.key === key) return this._tileLayer.node;
    const url = token ? (z, x, y) => PROXY_TILES(z, x, y, token) : UPSTREAM_TILES;
    const node = svg(
      "g",
      { class: dark ? "tiles dark" : "tiles", "clip-path": "url(#scope)" },
      view.tiles(url).map((tile) =>
        svg("image", { href: tile.href, x: tile.x, y: tile.y, width: tile.size, height: tile.size, preserveAspectRatio: "none" })
      )
    );
    this._tileLayer = { key, node };
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
      " contributors"
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

  // The furthest the station has ever heard an aircraft in each of the eight
  // sectors, in kilometres, clockwise from north: the shape of what the
  // antenna can see, and where a roof or a hill is in the way. A sector
  // without a record yet is drawn at the centre; with fewer than three
  // records there is no shape to draw.
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
    if (this._selected) this._lookUpRoute(this._selected);
    this._drawSky();
  }

  // Both ends of an aircraft's route with where they are, if known: sent
  // along for the nearby ones, asked for on a tap for the rest.
  _routeOf(plane) {
    if (plane.route_points) return plane.route_points;
    const asked = this._routes.get(plane.hex);
    return asked && asked !== "pending" ? asked : null;
  }

  _lookUpRoute(hex) {
    const plane = this._sky && (this._sky.aircraft || []).find((p) => p.hex === hex);
    if (!plane || plane.route_points || this._routes.has(hex) || !this._following || !this._hass.callWS) return;
    this._routes.set(hex, "pending");
    this._hass
      .callWS({ type: LOOK_UP_ROUTE, device_id: this._following, hex })
      .then((answer) => this._routes.set(hex, (answer && answer.route_points) || null))
      .catch(() => this._routes.set(hex, null))
      .finally(() => {
        if (this._selected === hex) this._drawSky();
      });
  }

  _legend(text) {
    const stops = ALTITUDE_HUES.map(
      ([feet]) => `${altitudeColor(feet)} ${((feet / ALTITUDE_TOP) * 100).toFixed(1)}%`
    );
    return el(
      "div",
      { class: "legend" },
      el(
        "div",
        { class: "keys" },
        el("span", { class: "key" }, el("span", { class: "dot ground" }), text.on_ground),
        this._coverage() ? el("span", { class: "key" }, el("span", { class: "area" }), text.coverage) : null
      ),
      el(
        "div",
        { class: "scale" },
        el("div", { class: "bar", style: `background: linear-gradient(to right, ${stops.join(", ")})` }),
        el(
          "div",
          { class: "ticks" },
          [0, 15000, 30000].map((feet) => el("span", {}, this._number(feet, 0))),
          el("span", {}, `${this._number(ALTITUDE_TOP, 0)} ft`)
        )
      )
    );
  }

  _picked(text) {
    const plane =
      this._selected && this._sky && (this._sky.aircraft || []).find((p) => p.hex === this._selected);
    if (!plane) return null;
    return el(
      "div",
      { class: "picked" },
      el(
        "div",
        { class: "primary" },
        el("span", { class: "swatch", style: `background: ${altitudeColor(plane.altitude, plane.on_ground)}` }),
        plane.flight || plane.hex,
        plane.airline ? ` · ${plane.airline}` : ""
      ),
      el(
        "div",
        { class: "secondary" },
        [plane.description || plane.aircraft_type, plane.registration].filter(Boolean).join(" · ")
      ),
      this._routeLine(plane),
      el(
        "div",
        { class: "secondary" },
        [
          this._height(plane, text),
          typeof plane.speed === "number" ? `${this._number(plane.speed, 0)} kt` : null,
          this._distance(plane.distance),
        ]
          .filter(Boolean)
          .join("   ")
      )
    );
  }

  // Where it comes from and goes to, in words, under the aircraft's name.
  _routeLine(plane) {
    const route = this._routeOf(plane);
    if (!route) return null;
    const end = (airport) => [airport.code, airport.location].filter(Boolean).join(" ");
    return el("div", { class: "secondary route-line" }, `${end(route.origin)} → ${end(route.destination)}`);
  }

  // --- Overhead and nearby -------------------------------------------------

  _overhead(found, text) {
    const state = this._state(found.overhead);
    const plane = state ? state.attributes : {};
    const known =
      state && !["unknown", "unavailable"].includes(state.state) && (plane.flight || plane.hex);
    if (!known) {
      return el("div", { class: "empty" }, el("ha-icon", { icon: "mdi:airplane-off" }), text.nothing);
    }

    const section = el("div", { class: "overhead" });
    section.append(
      el("div", { class: "label" }, plane.overhead === false ? text.last_overhead : text.overhead)
    );

    // The photo leads to its page and names who took it, as Planespotters asks
    // of anyone showing one. Without all three it is not shown at all.
    const photo = safeUrl(plane.photo);
    const link = safeUrl(plane.photo_link);
    if (photo && link && plane.photographer) {
      section.append(
        el(
          "a",
          { class: "photo", href: link, target: "_blank", rel: "noopener" },
          el("img", { src: photo, alt: plane.flight || plane.hex, loading: "lazy" })
        ),
        el(
          "div",
          { class: "credit" },
          `${text.photo}: ${plane.photographer} / `,
          el("a", { href: link, target: "_blank", rel: "noopener" }, "Planespotters.net")
        )
      );
    }

    const name = plane.flight || state.state;
    const details = el(
      "div",
      { class: "details", role: "button", tabindex: "0", onclick: this._moreInfo(found.overhead) },
      el("ha-icon", {
        icon: aircraftIcon(plane),
        style: `color: ${altitudeColor(plane.altitude, plane.on_ground)}`,
      }),
      el(
        "div",
        { class: "lines" },
        el("div", { class: "primary" }, name, plane.airline ? ` · ${plane.airline}` : ""),
        el(
          "div",
          { class: "secondary" },
          [plane.description || plane.aircraft_type, plane.registration].filter(Boolean).join(" · ")
        ),
        el(
          "div",
          { class: "secondary" },
          [plane.origin && plane.destination ? `${plane.origin} → ${plane.destination}` : null, this._height(plane, text), this._distance(plane.distance)]
            .filter(Boolean)
            .join("   ")
        )
      )
    );
    section.append(details);
    return section;
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
    return `${arrow}${this._number(plane.altitude, 0)} ft`;
  }

  _distance(km) {
    return typeof km === "number" ? `${this._number(km, 1)} km` : null;
  }

  _nearby(found, text) {
    const state = this._state(found.nearby);
    const list = state && Array.isArray(state.attributes.aircraft) ? state.attributes.aircraft : [];
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
            style: `color: ${altitudeColor(plane.altitude, plane.on_ground)}`,
          }),
          el("span", { class: "flight" }, plane.flight || plane.hex),
          el("span", { class: "what" }, plane.airline || plane.description || ""),
          el("span", { class: "figure" }, this._distance(plane.distance) || ""),
          el("span", { class: "figure" }, this._height(plane, text) || "")
        )
      )
    );
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
      [found.received, found.received && shown(found.received) && `${shown(found.received)} ${text.received}`],
      [found.rate, shown(found.rate)],
      [found.range, shown(found.range)],
      // How far the aircraft stand above the noise, in one figure: what a
      // change to the gain or the antenna is judged by.
      [found.snr, found.snr && shown(found.snr) && `S/N ${shown(found.snr)}`],
    ].filter(([, value]) => value);
    figures.forEach(([entry, value], i) => {
      if (i) line.append(el("span", { class: "sep" }, "·"));
      line.append(el("span", { class: "figures", role: "button", tabindex: "0", onclick: this._moreInfo(entry) }, value));
    });
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
            class: `feed ${good ? "good" : warn ? "warn" : "bad"}`,
            role: "button",
            tabindex: "0",
            title: this._hass.formatEntityState ? this._hass.formatEntityState(state) : state.state,
            onclick: this._moreInfo(entry),
          },
          el("span", { class: "dot" }),
          network
        )
      );
    }
    return line;
  }
}

const STYLE = `
  ha-card { display: block; overflow: hidden; container-type: inline-size; }
  .layout { display: grid; grid-template-columns: minmax(0, 1fr); }
  @container (min-width: 720px) {
    .layout.with-sky { grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); }
    .layout.with-sky .sky { border-right: 1px solid var(--divider-color); border-bottom: none; }
  }
  .sky { padding: 12px 12px 8px; border-bottom: 1px solid var(--divider-color); }
  .sky[hidden] { display: none; }
  .radar { display: block; width: 100%; max-height: 440px; margin: 0 auto; }
  .radar .scope { fill: var(--secondary-background-color, rgba(127, 127, 127, 0.08)); stroke: var(--divider-color); }
  .radar .ring { fill: none; stroke: var(--divider-color); }
  .radar .near { fill: none; stroke: var(--primary-color); stroke-dasharray: 4 4; opacity: 0.7; }
  .radar text { fill: var(--secondary-text-color); font-size: 11px; font-family: inherit; }
  .radar .compass { text-anchor: middle; font-weight: 500; }
  .radar .quiet { text-anchor: middle; font-size: 13px; }
  .radar .home { fill: var(--primary-color); stroke: var(--card-background-color, #fff); stroke-width: 2; }
  .radar .trails line { stroke-width: 2; stroke-linecap: round; opacity: 0.65; }
  .radar .plane { cursor: pointer; }
  .radar .plane path { stroke: var(--card-background-color, #000); stroke-width: 0.8; }
  .radar .callsign { fill: var(--primary-text-color); font-size: 10.5px; font-weight: 500; paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 3px; }
  .radar .route polyline { fill: none; stroke: var(--primary-text-color); stroke-width: 1.8; stroke-linejoin: round; }
  .radar .route .flown { opacity: 0.55; }
  .radar .route .ahead { stroke-dasharray: 5 4; opacity: 0.85; }
  .radar .airport circle { fill: var(--card-background-color, #fff); stroke: var(--primary-text-color); stroke-width: 2; }
  .radar .airport text { fill: var(--primary-text-color); font-size: 11px; font-weight: 600; paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 3px; }
  .radar .halo { fill: none; stroke: var(--primary-text-color); stroke-width: 1.5; opacity: 0.6; }
  .radar .land { fill: var(--secondary-background-color, #eee); }
  /* OpenStreetMap has no dark tiles; Home Assistant inverts them the same way. */
  .radar .tiles.dark { filter: invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.9); }
  .radar.streets .ring { stroke: rgba(0, 0, 0, 0.3); }
  .radar.streets .distance { fill: var(--primary-text-color); paint-order: stroke; stroke: var(--card-background-color, #fff); stroke-width: 3px; }
  .radar.streets .trails line { opacity: 0.85; stroke-width: 2.5; }
  .attribution { text-align: right; font-size: 0.7em; color: var(--secondary-text-color); margin-top: 2px; }
  .attribution a { color: inherit; }
  .radar .coverage { fill: var(--primary-color); fill-opacity: 0.1; stroke: var(--primary-color); stroke-opacity: 0.45; stroke-linejoin: round; }
  .legend { display: flex; align-items: flex-end; gap: 16px; margin-top: 8px; font-size: 0.75em; color: var(--secondary-text-color); }
  .legend .keys { display: flex; flex-direction: column; gap: 2px; }
  .legend .key { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
  .legend .dot.ground { background: ${GROUND_COLOR}; }
  .legend .area { width: 10px; height: 8px; border: 1px solid var(--primary-color); background: rgba(3, 169, 244, 0.15); border-radius: 2px; }
  .legend .scale { flex: 1; min-width: 0; }
  .legend .bar { height: 6px; border-radius: 3px; }
  .legend .ticks { display: flex; justify-content: space-between; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .picked { margin-top: 10px; padding: 8px 10px; border-radius: 8px; background: var(--secondary-background-color, rgba(127, 127, 127, 0.08)); }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
  .empty { display: flex; align-items: center; gap: 12px; padding: 16px; color: var(--secondary-text-color); }
  .overhead { padding: 16px 16px 8px; }
  .label { font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; color: var(--secondary-text-color); margin-bottom: 8px; }
  .photo img { display: block; width: 100%; max-height: 240px; object-fit: cover; border-radius: var(--ha-card-border-radius, 12px); }
  .credit { font-size: 0.8em; color: var(--secondary-text-color); margin: 4px 0 12px; }
  .credit a { color: inherit; }
  .details { display: flex; gap: 12px; align-items: flex-start; cursor: pointer; }
  .details ha-icon { margin-top: 2px; }
  .lines { min-width: 0; }
  .primary { font-size: 1.1em; font-weight: 500; }
  .secondary { color: var(--secondary-text-color); white-space: pre-wrap; }
  .nearby { padding: 8px 16px; border-top: 1px solid var(--divider-color); }
  .row { display: grid; grid-template-columns: 24px auto 1fr auto auto; gap: 8px; align-items: center; padding: 4px 0; cursor: pointer; }
  .row ha-icon { --mdc-icon-size: 20px; }
  .flight { font-weight: 500; }
  .what { color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .figure { color: var(--secondary-text-color); text-align: right; font-variant-numeric: tabular-nums; }
  .status { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 6px; padding: 12px 16px; border-top: 1px solid var(--divider-color); color: var(--secondary-text-color); font-size: 0.9em; }
  .figures { cursor: pointer; font-variant-numeric: tabular-nums; }
  .feed { margin-left: 10px; }
  .feed { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--error-color, #db4437); }
  .good .dot { background: var(--success-color, #43a047); }
  .warn .dot { background: var(--warning-color, #ffa600); }
`;

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
