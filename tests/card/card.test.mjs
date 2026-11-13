// The dashboard card, run in a simulated browser against a Home Assistant
// that has the entities this integration makes, under Dutch entity IDs so the
// card is seen to find them by translation key rather than by name.
//
//   cd tests/card && npm ci && npm test
//
// CI runs it as the Card job. pytest does not see it: the card is JavaScript.
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const source = readFileSync(process.argv[2], "utf8");

function browser() {
  const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only" });
  dom.window.eval(source);
  return dom.window;
}

const DEVICE = "dev-fr24";
const PIAWARE = "dev-piaware";

function entity(id, key, device = DEVICE) {
  return { entity_id: id, platform: "adsb_station", translation_key: key, device_id: device };
}

function hassWith({ overhead, nearby = [], language = "en", extraStates = {} } = {}) {
  const entities = {
    "sensor.t_etur47_vlucht_overhead": entity("sensor.t_etur47_vlucht_overhead", "overhead_flight"),
    "sensor.t_etur47_vliegtuigen_dichtbij": entity("sensor.t_etur47_vliegtuigen_dichtbij", "aircraft_nearby"),
    "sensor.t_etur47_vliegtuigen_ontvangen": entity("sensor.t_etur47_vliegtuigen_ontvangen", "aircraft_received"),
    "sensor.t_etur47_berichten_per_seconde": entity("sensor.t_etur47_berichten_per_seconde", "message_rate"),
    "sensor.t_etur47_maximaal_bereik": entity("sensor.t_etur47_maximaal_bereik", "max_range"),
    "sensor.t_etur47_signaal_ruis": entity("sensor.t_etur47_signaal_ruis", "signal_to_noise"),
    "binary_sensor.t_etur47_feed": entity("binary_sensor.t_etur47_feed", "feed"),
    "sensor.piaware_feeder_feed": entity("sensor.piaware_feeder_feed", "piaware_feed", PIAWARE),
    "sensor.t_etur47_passages_vandaag": entity("sensor.t_etur47_passages_vandaag", "passages_today"),
    "sensor.unrelated": { entity_id: "sensor.unrelated", platform: "other" },
  };
  const st = (state, attributes = {}) => ({ state, attributes, last_updated: "t" });
  const states = {
    "sensor.t_etur47_vlucht_overhead": overhead ?? st("unknown"),
    "sensor.t_etur47_vliegtuigen_dichtbij": st(String(nearby.length), { aircraft: nearby }),
    "sensor.t_etur47_vliegtuigen_ontvangen": st("468"),
    "sensor.t_etur47_berichten_per_seconde": st("75.0", { unit_of_measurement: "msg/s" }),
    "sensor.t_etur47_maximaal_bereik": st("67.9", { unit_of_measurement: "km" }),
    "sensor.t_etur47_signaal_ruis": st("18.7", { unit_of_measurement: "dB" }),
    "binary_sensor.t_etur47_feed": st("on"),
    "sensor.piaware_feeder_feed": st("amber"),
    "sensor.unrelated": st("1"),
    ...extraStates,
  };
  return {
    entities,
    states,
    locale: { language },
    formatEntityState: (s) =>
      s.attributes.unit_of_measurement ? `${s.state} ${s.attributes.unit_of_measurement}` : s.state,
  };
}

function render(window, hass, config = {}) {
  const card = window.document.createElement("adsb-station-card");
  window.document.body.append(card);
  card.setConfig(config);
  card.hass = hass;
  return card;
}

const KLM = {
  hex: "484506",
  flight: "KLM1234",
  airline: "KLM",
  description: "Boeing 737-800",
  registration: "PH-BXA",
  origin: "AMS",
  destination: "LHR",
  altitude: 3200,
  vertical_rate: 1500,
  distance: 1.1,
  overhead: true,
  photo: "https://t.plnspttrs.net/1/1_280.jpg",
  photo_link: "https://www.planespotters.net/photo/1/ph-bxa",
  photographer: "Jan Seler",
};
const overheadState = (attributes, state = attributes.flight) => ({ state, attributes, last_updated: "t" });

// A websocket that hands the card's subscription to the test, which then
// plays the integration and sends it the sky.
function renderTable(window, hass, config = {}) {
  const card = window.document.createElement("adsb-station-table-card");
  window.document.body.append(card);
  card.setConfig(config);
  card.hass = hass;
  return card;
}

function connect(hass) {
  const link = { subscriptions: [], unsubscribed: 0 };
  hass.connection = {
    subscribeMessage(callback, message) {
      link.subscriptions.push({ callback, message });
      return Promise.resolve(() => {
        link.unsubscribed += 1;
      });
    },
  };
  link.send = (sky) => link.subscriptions[link.subscriptions.length - 1].callback(sky);
  return link;
}

const SKY = (aircraft) => ({ latitude: 52.0, longitude: 5.0, radius: 10, aircraft });
const LOW = {
  hex: "484506",
  flight: "KLM1234",
  latitude: 52.02,
  longitude: 5.0,
  altitude: 1500,
  track: 90,
  distance: 2.2,
  speed: 160,
  description: "Boeing 737-800",
  registration: "PH-BXA",
};
const HIGH = {
  hex: "4ca123",
  flight: "RYR5",
  latitude: 52.4,
  longitude: 5.3,
  altitude: 37000,
  track: 270,
  distance: 49.0,
};
const ROTOR = {
  hex: "4851a7",
  flight: "LIFE01",
  latitude: 51.98,
  longitude: 4.98,
  altitude: 900,
  category: "A7",
  distance: 2.6,
};

const hue = (color) => Number(/hsl\((\d+)/.exec(color)[1]);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

// A vector tile as Home Assistant's proxy serves it, written out by hand in
// Protocol Buffers: layers of features with properties and geometry.
function vectorTile(layers) {
  const varint = (n, out) => {
    while (n > 127) {
      out.push((n % 128) | 0x80);
      n = Math.floor(n / 128);
    }
    out.push(n);
    return out;
  };
  const tag = (number, wire, out) => varint(number * 8 + wire, out);
  const bytes = (number, content, out) => {
    tag(number, 2, out);
    varint(content.length, out);
    for (const byte of content) out.push(byte);
    return out;
  };
  const text = (value) => [...new TextEncoder().encode(value)];
  const packed = (number, values, out) =>
    bytes(
      number,
      values.reduce((acc, value) => varint(value, acc), []),
      out,
    );
  const out = [];
  for (const layer of layers) {
    const body = bytes(1, text(layer.name), []);
    const keys = [];
    const values = [];
    for (const feature of layer.features) {
      const tags = [];
      for (const [key, value] of Object.entries(feature.properties || {})) {
        if (!keys.includes(key)) keys.push(key);
        values.push(value);
        tags.push(keys.indexOf(key), values.length - 1);
      }
      const encoded = packed(2, tags, []);
      varint(feature.type, tag(3, 0, encoded));
      packed(4, feature.geometry, encoded);
      bytes(2, encoded, body);
    }
    for (const key of keys) bytes(3, text(key), body);
    for (const value of values) {
      bytes(4, typeof value === "string" ? bytes(1, text(value), []) : varint(value, tag(5, 0, [])), body);
    }
    varint(layer.extent, tag(5, 0, body));
    varint(2, tag(15, 0, body));
    bytes(3, body, out);
  }
  return new Uint8Array(out);
}

const move = (count) => 1 | (count << 3);
const draw = (count) => 2 | (count << 3);
const zigzag = (n) => (n << 1) ^ (n >> 31);

// Where a position falls in tile z/x/y, in units of the given extent.
function inTile([latitude, longitude], z, x, y, extent) {
  const n = 2 ** z;
  const phi = (latitude * Math.PI) / 180;
  const tx = ((longitude + 180) / 360) * n;
  const ty = ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * n;
  return [Math.round((tx - x) * extent), Math.round((ty - y) * extent)];
}

// Just east of the station, so its name clears the station itself.
const UTRECHT = [52.0, 5.03];

// What one tile holds: water and streets at half the extent of the borders
// and names, as OpenStreetMap's Shortbread tiles have them.
function tileAround(z, x, y, at = UTRECHT) {
  const [px, py] = inTile(at, z, x, y, 4096);
  const line = [move(1), zigzag(100), zigzag(100), draw(1), zigzag(800), zigzag(0)];
  const square = [move(1), zigzag(512), zigzag(512), draw(3), zigzag(1024), 0, 0, zigzag(1024), zigzag(-1024), 0, 15];
  const place = [move(1), zigzag(px), zigzag(py)];
  return vectorTile([
    { name: "water_polygons", extent: 2048, features: [{ type: 3, properties: { kind: "water" }, geometry: square }] },
    {
      name: "streets",
      extent: 2048,
      features: [
        { type: 2, properties: { kind: "motorway" }, geometry: line },
        { type: 2, properties: { kind: "residential" }, geometry: line },
      ],
    },
    { name: "boundaries", extent: 4096, features: [{ type: 2, properties: { admin_level: 2 }, geometry: line }] },
    {
      name: "place_labels",
      extent: 4096,
      features: [
        { type: 1, properties: { kind: "city", name: "Utrecht", population: 361924 }, geometry: place },
        { type: 1, properties: { kind: "hamlet", name: "Nergens" }, geometry: place },
      ],
    },
  ]);
}

function tileFor(url, at) {
  const [z, x, y] = /(\d+)\/(\d+)\/(\d+)\.mvt/.exec(url).slice(1).map(Number);
  return tileAround(z, x, y, at);
}

// A browser whose fetch plays Home Assistant's vector tile proxy.
function vectorBrowser(answer = (url) => ({ ok: true, status: 200, body: tileFor(url) })) {
  const w = browser();
  w.TextDecoder = TextDecoder;
  const asked = [];
  w.fetch = (url, options) => {
    const header = options && options.headers ? options.headers["X-Map-Tiles-Token"] : undefined;
    asked.push({ url, token: header });
    const { ok, status, body } = answer(url, header);
    return Promise.resolve({ ok, status, arrayBuffer: () => Promise.resolve(body && body.buffer) });
  };
  return { w, asked };
}

const settle = async () => {
  for (let i = 0; i < 8; i++) await tick();
};

const tests = {
  "lists what came over today, newest first"() {
    const w = browser();
    const passages = [
      {
        at: "2026-11-13T14:32:00+00:00",
        hex: "484506",
        flight: "KLM1234",
        altitude: 3200,
        distance: 1.8,
        duration: 95,
        aircraft_type: "B738",
      },
      { at: "2026-11-13T09:05:00+00:00", hex: "4851a7", flight: "LIFE01", altitude: 900, distance: 0.4, duration: 600 },
      { at: "2026-11-13T11:47:00+00:00", hex: "484124", altitude: 36000, distance: 6.1, duration: 40 },
    ];
    const hass = hassWith({
      overhead: overheadState(KLM),
      extraStates: { "sensor.t_etur47_passages_vandaag": { state: "3", attributes: { passages }, last_updated: "t" } },
    });
    const link = connect(hass);
    const card = renderTable(w, hass, { list: "passages" });
    assert.equal(link.subscriptions.length, 0, "the board needs no sky");

    const rows = () =>
      [...card.shadowRoot.querySelectorAll(".table tbody tr")].map((row) =>
        [...row.children].map((td) => td.textContent),
      );
    assert.deepEqual(JSON.stringify(rows().map((row) => row[1])), JSON.stringify(["KLM1234", "484124", "LIFE01"]));
    assert.equal(rows()[0][5], "2 min");
    assert.equal(rows()[1][5], "40 s");
    assert.match(
      card.shadowRoot.querySelector(".table thead").textContent,
      /Time.*Flight.*Height.*Distance.*Type.*In view/,
    );

    // Sorted like the other list, and searched the same way
    card.shadowRoot.querySelectorAll(".table th")[3].click();
    assert.equal(rows()[0][1], "LIFE01", "closest first");
    const search = card.shadowRoot.querySelector(".table input");
    search.value = "b738";
    search.dispatchEvent(new w.Event("input"));
    assert.equal(rows().length, 1);
  },

  "says so when nothing came over"() {
    const w = browser();
    const hass = hassWith({
      overhead: overheadState(KLM),
      language: "nl",
      extraStates: {
        "sensor.t_etur47_passages_vandaag": { state: "0", attributes: { passages: [] }, last_updated: "t" },
      },
    });
    const card = renderTable(w, hass, { list: "passages" });
    assert.match(card.shadowRoot.querySelector(".table tbody").textContent, /Er is vandaag nog niets overgekomen/);
  },

  "draws readsb's own outline instead of the eight records"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    // A square 40 km out, as a decoder would send a point per degree
    const outline = [
      [52.36, 5.0],
      [52.0, 5.58],
      [51.64, 5.0],
      [52.0, 4.42],
    ];
    link.send({ ...SKY([LOW]), outline });
    const shape = card.shadowRoot.querySelector(".radar .coverage");
    assert.equal(shape.getAttribute("points").split(" ").length, 4);
    assert.match(card.shadowRoot.querySelector(".legend").textContent, /furthest heard, last 24 h/);

    link.send(SKY([LOW]));
    assert.equal(card.shadowRoot.querySelector(".radar .coverage"), null, "no records in this house either");
    assert.doesNotMatch(card.shadowRoot.querySelector(".legend").textContent, /furthest heard/);
  },

  async "fits the outline when scaled to the coverage"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass, { map_scale: "coverage" });
    link.send({
      ...SKY([LOW]),
      outline: [
        [52.9, 5.0],
        [52.0, 5.1],
        [51.9, 5.0],
      ],
    });
    assert.match(card.shadowRoot.querySelector(".radar").textContent, /100 km/, "100 km out takes the 100 km ring");
  },

  "keeps the table on a card of its own"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    connect(hass);
    assert.ok(render(w, hass).shadowRoot.querySelector(".table").hidden, "not on the station card");

    const card = renderTable(w, hass);
    assert.ok(!card.shadowRoot.querySelector(".table").hidden);
    assert.equal(card.shadowRoot.querySelector(".body").textContent, "", "nothing overhead, nearby or status");
    assert.ok(card.shadowRoot.querySelector(".sky").hidden);
    const form = w.customElements.get("adsb-station-table-card").getConfigForm();
    assert.equal(
      JSON.stringify(form.schema.map((field) => field.name)),
      JSON.stringify(["device_id", "title", "list"]),
    );
  },

  async "lists every aircraft in a table, even without a map"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = renderTable(w, hass);
    assert.equal(link.subscriptions.length, 1, "the table needs the sky too");
    link.send(SKY([{ ...HIGH, bearing: 77 }, { ...LOW, bearing: 0, aircraft_type: "B738", rssi: -12.3 }, ROTOR]));

    const rows = () =>
      [...card.shadowRoot.querySelectorAll(".table tbody tr")].map((row) =>
        [...row.children].map((td) => td.textContent),
      );
    const heads = () => [...card.shadowRoot.querySelectorAll(".table th")];
    // Nearest first, to start with
    assert.deepEqual(
      rows().map((row) => row[0]),
      ["KLM1234", "LIFE01", "RYR5"],
    );
    assert.deepEqual(rows()[0], ["KLM1234", "1,500 ft", "2.2 km", "0°", "B738", "-12.3"]);
    assert.equal(rows()[1][3], "", "a bearing it does not have is left empty");

    // A tap on a heading sorts by it, a second tap turns it round
    heads()[1].click();
    assert.deepEqual(
      rows().map((row) => row[0]),
      ["LIFE01", "KLM1234", "RYR5"],
    );
    heads()[1].click();
    assert.deepEqual(
      rows().map((row) => row[0]),
      ["RYR5", "KLM1234", "LIFE01"],
    );
    assert.equal(heads()[1].getAttribute("aria-sort"), "descending");

    // Unknown last, whichever way round
    heads()[3].click();
    assert.deepEqual(
      rows().map((row) => row[0]),
      ["KLM1234", "RYR5", "LIFE01"],
    );
    heads()[3].click();
    assert.deepEqual(
      rows().map((row) => row[0]),
      ["RYR5", "KLM1234", "LIFE01"],
    );
  },

  "searches without losing the box on the next push"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = renderTable(w, hass);
    link.send(SKY([LOW, HIGH, ROTOR]));

    const search = card.shadowRoot.querySelector(".table input");
    search.value = "ph-bx";
    search.dispatchEvent(new w.Event("input"));
    const flights = () =>
      [...card.shadowRoot.querySelectorAll(".table tbody tr")].map((row) => row.firstChild.textContent);
    assert.deepEqual(flights(), ["KLM1234"], "found by registration");

    link.send(SKY([LOW, HIGH, ROTOR]));
    card.hass = { ...hass };
    assert.equal(card.shadowRoot.querySelector(".table input"), search, "the same box, so it keeps its focus");
    assert.deepEqual(flights(), ["KLM1234"]);

    search.value = "nothing like it";
    search.dispatchEvent(new w.Event("input"));
    assert.match(card.shadowRoot.querySelector(".table tbody").textContent, /No aircraft with a position/);
  },

  "marks the row tapped, as on the radar"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    let asked = 0;
    hass.callWS = () => {
      asked += 1;
      return new Promise(() => {});
    };
    const card = renderTable(w, hass);
    link.send(SKY([LOW, HIGH]));
    card.shadowRoot.querySelector(".table tbody tr").click();
    assert.equal(card.shadowRoot.querySelector(".table tr.selected").firstChild.textContent, "KLM1234");
    assert.equal(asked, 0, "no route asked for without a map to draw it on");
  },

  "speaks Dutch in the table"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM), language: "nl" });
    const link = connect(hass);
    const card = renderTable(w, hass);
    link.send(SKY([LOW]));
    assert.equal(card.shadowRoot.querySelector(".table input").placeholder, "Zoek vlucht, registratie of type");
    assert.match(card.shadowRoot.querySelector(".table thead").textContent, /Vlucht.*Hoogte.*Afstand.*Richting/);
  },

  "registers itself for the card picker"() {
    const w = browser();
    assert.ok(w.customElements.get("adsb-station-card"));
    assert.ok(w.customElements.get("adsb-station-table-card"));
    assert.equal(
      JSON.stringify(w.customCards.map((entry) => entry.type).sort()),
      JSON.stringify(["adsb-station-card", "adsb-station-table-card"]),
    );
  },

  "finds the station by translation key, whatever the IDs are"() {
    const w = browser();
    const nearby = [
      { hex: "484506", flight: "KLM1234", distance: 1.1, altitude: 3200 },
      { hex: "484124", flight: "TRA45", airline: "Transavia", distance: 5.2, altitude: 8000 },
      { hex: "4851a7", flight: "LIFE01", description: "EC135", category: "A7", distance: 7.8, altitude: 1200 },
    ];
    const card = render(w, hassWith({ overhead: overheadState(KLM), nearby }));
    const root = card.shadowRoot;
    const text = root.textContent;
    assert.match(text, /Overhead now/);
    assert.match(text, /KLM1234 · KLM/);
    assert.match(text, /Boeing 737-800 · PH-BXA/);
    assert.match(text, /AMS → LHR/);
    assert.match(text, /↑ 3,200 ft/);
    assert.match(text, /1\.1 km/);
    // The photo, leading to its page, with who took it beside it.
    const link = root.querySelector("a.photo");
    assert.equal(link.getAttribute("href"), KLM.photo_link);
    assert.equal(link.querySelector("img").getAttribute("src"), KLM.photo);
    assert.equal(link.getAttribute("rel"), "noopener");
    assert.match(root.querySelector(".credit").textContent, /Photo: Jan Seler \/ Planespotters\.net/);
    // The one overhead is not listed again among the nearby.
    const rows = [...root.querySelectorAll(".nearby .row")];
    assert.deepEqual(
      rows.map((r) => r.querySelector(".flight").textContent),
      ["TRA45", "LIFE01"],
    );
    assert.equal(rows[1].querySelector("ha-icon").getAttribute("icon"), "mdi:helicopter");
    // The status line, with a dot per network.
    const figures = [...root.querySelectorAll(".status .figures")].map((f) => f.textContent);
    assert.equal(JSON.stringify(figures), JSON.stringify(["468 received", "75.0 msg/s", "67.9 km", "S/N 18.7 dB"]));
    const feeds = [...root.querySelectorAll(".feed")].map((f) => [f.textContent, f.className]);
    assert.deepEqual(feeds, [
      ["Flightradar24", "feed good"],
      ["FlightAware", "feed warn"],
    ]);
  },

  "speaks Dutch where Home Assistant does"() {
    const w = browser();
    const card = render(w, hassWith({ overhead: overheadState(KLM), language: "nl" }));
    const text = card.shadowRoot.textContent;
    assert.match(text, /Nu overhead/);
    assert.match(text, /Foto: Jan Seler/);
    assert.match(text, /3\.200 ft/);
    assert.match(text, /1,1 km/);
    assert.match(text, /468 ontvangen/);
  },

  "says when the last one has flown on"() {
    const w = browser();
    const card = render(w, hassWith({ overhead: overheadState({ ...KLM, overhead: false }) }));
    assert.match(card.shadowRoot.textContent, /Last overhead/);
  },

  "says when nothing has come over yet"() {
    const w = browser();
    const card = render(w, hassWith());
    assert.match(card.shadowRoot.textContent, /Nothing overhead right now/);
  },

  "says when there is no station at all"() {
    const w = browser();
    const hass = hassWith();
    hass.entities = {};
    const card = render(w, hass);
    assert.match(card.shadowRoot.textContent, /No ADS-B station with a receiver was found/);
  },

  "shows no photo without its link, its credit, or over plain http"() {
    for (const broken of [
      { photographer: undefined },
      { photo_link: undefined },
      { photo: "http://t.plnspttrs.net/1.jpg" },
      { photo_link: "javascript:alert(1)" },
    ]) {
      const w = browser();
      const card = render(w, hassWith({ overhead: overheadState({ ...KLM, ...broken }) }));
      assert.equal(card.shadowRoot.querySelector("img"), null, JSON.stringify(broken));
      assert.equal(card.shadowRoot.querySelector(".credit"), null);
    }
  },

  "never turns aircraft data into markup"() {
    const w = browser();
    const evil = '<img src=x onerror="window.hacked=1">';
    const card = render(
      w,
      hassWith({
        overhead: overheadState({ ...KLM, flight: evil, airline: evil, photographer: evil }),
        nearby: [{ hex: "1", flight: evil, airline: evil, distance: 2 }],
      }),
    );
    const root = card.shadowRoot;
    assert.equal(root.querySelectorAll("img").length, 1); // only the photo
    assert.ok(root.textContent.includes(evil));
    assert.equal(w.hacked, undefined);
  },

  "can leave the list and the status out, and cap the list"() {
    const w = browser();
    const nearby = Array.from({ length: 9 }, (_, i) => ({ hex: `h${i}`, flight: `F${i}`, distance: i }));
    let card = render(w, hassWith({ overhead: overheadState(KLM), nearby }), { max_nearby: 3 });
    assert.equal(card.shadowRoot.querySelectorAll(".nearby .row").length, 3);
    card = render(w, hassWith({ overhead: overheadState(KLM), nearby }), { show_nearby: false, show_status: false });
    assert.equal(card.shadowRoot.querySelector(".nearby"), null);
    assert.equal(card.shadowRoot.querySelector(".status"), null);
  },

  "picks the station it was given"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    hass.entities["sensor.other_overhead"] = entity("sensor.other_overhead", "overhead_flight", "dev-other");
    hass.states["sensor.other_overhead"] = overheadState({ hex: "1", flight: "OTHER1", overhead: true });
    const card = render(w, hass, { device_id: "dev-other" });
    assert.match(card.shadowRoot.textContent, /OTHER1/);
    assert.doesNotMatch(card.shadowRoot.textContent, /KLM1234/);
  },

  "does not redraw for a change it does not show"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const card = render(w, hass);
    const before = card.shadowRoot.querySelector(".body").firstElementChild;
    card.hass = {
      ...hass,
      states: { ...hass.states, "sensor.unrelated": { state: "2", attributes: {}, last_updated: "u" } },
    };
    assert.equal(card.shadowRoot.querySelector(".body").firstElementChild, before);
    card.hass = {
      ...hass,
      states: {
        ...hass.states,
        "sensor.t_etur47_vliegtuigen_ontvangen": { state: "470", attributes: {}, last_updated: "u" },
      },
    };
    assert.notEqual(card.shadowRoot.querySelector(".body").firstElementChild, before);
    assert.match(card.shadowRoot.textContent, /470 received/);
  },

  "opens the details of what is clicked"() {
    const w = browser();
    const card = render(w, hassWith({ overhead: overheadState(KLM) }));
    const opened = [];
    card.addEventListener("hass-more-info", (e) => opened.push(e.detail.entityId));
    card.shadowRoot.querySelector(".details").click();
    card.shadowRoot.querySelector(".feed").click();
    assert.deepEqual(opened, ["sensor.t_etur47_vlucht_overhead", "binary_sensor.t_etur47_feed"]);
  },

  "has a form to set it up without YAML"() {
    const w = browser();
    const Card = w.customElements.get("adsb-station-card");
    const form = Card.getConfigForm();
    assert.equal(
      JSON.stringify(form.schema.map((s) => s.name)),
      JSON.stringify([
        "device_id",
        "title",
        "map",
        "map_scale",
        "map_range",
        "show_nearby",
        "max_nearby",
        "show_status",
      ]),
    );
    w.__adsbStationHass = { locale: { language: "nl" } };
    assert.equal(form.computeLabel({ name: "device_id" }), "Station");
    assert.equal(form.computeLabel({ name: "show_nearby" }), "Toestellen dichtbij tonen");
    assert.equal(JSON.stringify(Card.getStubConfig()), "{}");
    const styles = Card.getConfigForm().schema.find((s) => s.name === "map").selector.select.options;
    assert.equal(JSON.stringify(styles.map((o) => o.label)), JSON.stringify(["Radar", "Landkaart", "Geen kaart"]));
  },

  "draws every aircraft the integration sends on the radar"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    assert.equal(link.subscriptions.length, 1);
    assert.equal(
      JSON.stringify(link.subscriptions[0].message),
      JSON.stringify({ type: "adsb_station/subscribe_aircraft", device_id: DEVICE }),
    );

    link.send(SKY([LOW, HIGH, ROTOR]));
    const root = card.shadowRoot;
    const planes = [...root.querySelectorAll(".radar .plane")];
    // Low ones first, so the one at cruising height is drawn on top.
    assert.deepEqual(
      planes.map((p) => p.querySelector(".callsign").textContent),
      ["LIFE01", "KLM1234", "RYR5"],
    );
    const shape = (hex) => root.querySelector(`.plane[data-hex="${hex}"] path`);
    // Warm and low, cool and high.
    assert.ok(hue(shape("484506").getAttribute("fill")) < 40);
    assert.ok(hue(shape("4ca123").getAttribute("fill")) > 200);
    assert.match(shape("484506").getAttribute("transform"), /rotate\(90\)/);
    // A helicopter is drawn as one, not as an airliner.
    assert.notEqual(shape("4851a7").getAttribute("d"), shape("484506").getAttribute("d"));
    // The outer ring fits the furthest aircraft; the nearby radius is dashed.
    assert.match(root.querySelector(".radar").textContent, /50 km/);
    assert.ok(root.querySelector(".radar .near"));
    assert.match(root.querySelector(".legend").textContent, /on the ground/);
  },

  "draws a trail behind an aircraft that moves"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    link.send(SKY([LOW]));
    assert.equal(card.shadowRoot.querySelectorAll(".trails line").length, 0);
    link.send(SKY([{ ...LOW, latitude: 52.03 }]));
    link.send(SKY([{ ...LOW, latitude: 52.04 }]));
    assert.equal(card.shadowRoot.querySelectorAll(".trails line").length, 2);
  },

  "draws the trails the integration kept before the card opened"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    const now = Date.now() / 1000;
    link.send({
      ...SKY([LOW]),
      trails: {
        [LOW.hex]: [
          [52.0, 5.0, 1200, now - 120],
          [52.01, 5.0, 1400, now - 60],
          [52.02, 5.0, 1500, now - 5],
        ],
      },
    });
    const lines = [...card.shadowRoot.querySelectorAll(".trails line")];
    assert.equal(lines.length, 2);
    assert.ok(hue(lines[0].getAttribute("stroke")) < 40);
    // And carries on from there with the next poll.
    link.send(SKY([{ ...LOW, latitude: 52.03 }]));
    assert.equal(card.shadowRoot.querySelectorAll(".trails line").length, 3);
  },

  "draws no trail without the aircraft at the end of it"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    const now = Date.now() / 1000;
    // HIGH is in the trails but no longer in the sky.
    link.send({
      ...SKY([LOW]),
      trails: {
        [LOW.hex]: [
          [52.0, 5.0, 1200, now - 60],
          [52.02, 5.0, 1500, now - 5],
        ],
        [HIGH.hex]: [
          [52.3, 5.5, 37000, now - 200],
          [52.4, 5.3, 37000, now - 90],
        ],
      },
    });
    assert.equal(card.shadowRoot.querySelectorAll(".trails line").length, 1);
    // And one that drops out of the sky takes its trail with it.
    link.send(SKY([{ ...LOW, latitude: 52.03 }, HIGH]));
    link.send(SKY([{ ...HIGH, latitude: 52.41 }]));
    assert.equal(card.shadowRoot.querySelectorAll(".trails line").length, 1);
    assert.equal(card.shadowRoot.querySelectorAll(".plane").length, 1);
  },

  "shows what was tapped on the radar"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    link.send(SKY([LOW, HIGH]));
    const tap = () => card.shadowRoot.querySelector('.plane[data-hex="484506"]').dispatchEvent(new w.Event("click"));
    tap();
    const picked = card.shadowRoot.querySelector(".picked").textContent;
    assert.match(picked, /KLM1234/);
    assert.match(picked, /Boeing 737-800 · PH-BXA/);
    assert.match(picked, /1,500 ft/);
    assert.match(picked, /160 kt/);
    // Still picked after the next poll, and let go of by a second tap.
    link.send(SKY([LOW, HIGH]));
    assert.ok(card.shadowRoot.querySelector(".picked"));
    tap();
    assert.equal(card.shadowRoot.querySelector(".picked"), null);
  },

  "draws the route of a tapped aircraft it was sent"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.callWS = () => assert.fail("a route that came with the sky is not asked for");
    const card = render(w, hass);
    const route_points = {
      origin: { code: "GOT", location: "Gothenburg", latitude: 57.66, longitude: 12.28 },
      destination: { code: "AMS", location: "Amsterdam", latitude: 52.31, longitude: 4.76 },
    };
    link.send(SKY([{ ...LOW, route_points }, HIGH]));
    // Nothing until it is tapped.
    assert.equal(card.shadowRoot.querySelector(".radar .route"), null);
    card.shadowRoot.querySelector('.plane[data-hex="484506"]').dispatchEvent(new w.Event("click"));
    const route = card.shadowRoot.querySelector(".radar .route");
    assert.ok(route.querySelector(".flown").getAttribute("points").split(" ").length > 10);
    assert.ok(route.querySelector(".ahead"));
    const codes = [...route.querySelectorAll(".airport text")].map((t) => t.textContent);
    assert.equal(JSON.stringify(codes), JSON.stringify(["GOT", "AMS"]));
    assert.match(card.shadowRoot.querySelector(".picked").textContent, /GOT Gothenburg → AMS Amsterdam/);
    // The way ahead ends on Schiphol: north-west of the station, so left of
    // and above the centre.
    const last = route.querySelector(".ahead").getAttribute("points").split(" ").pop().split(",").map(Number);
    assert.ok(last[0] < 200 && last[1] < 200, String(last));
  },

  async "asks for the route of a tapped aircraft further out"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const asked = [];
    hass.callWS = (message) => {
      asked.push(message);
      return Promise.resolve({
        route_points: {
          origin: { code: "DUB", location: "Dublin", latitude: 53.42, longitude: -6.27 },
          destination: { code: "BUD", location: "Budapest", latitude: 47.43, longitude: 19.26 },
        },
      });
    };
    const card = render(w, hass);
    link.send(SKY([LOW, HIGH]));
    const tap = () => card.shadowRoot.querySelector('.plane[data-hex="4ca123"]').dispatchEvent(new w.Event("click"));
    tap();
    assert.equal(
      JSON.stringify(asked),
      JSON.stringify([{ type: "adsb_station/look_up_route", device_id: DEVICE, hex: "4ca123" }]),
    );
    await tick();
    await tick();
    assert.ok(card.shadowRoot.querySelector(".radar .route"));
    assert.match(card.shadowRoot.querySelector(".picked").textContent, /DUB Dublin → BUD Budapest/);
    // Asked once: tapped again, it is remembered.
    tap();
    tap();
    assert.equal(asked.length, 1);
  },

  async "says so where nobody knows the route"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.callWS = () => Promise.resolve({ route_points: null, status: "unknown" });
    const card = render(w, hass);
    link.send(SKY([LOW]));
    card.shadowRoot.querySelector('.plane[data-hex="484506"]').dispatchEvent(new w.Event("click"));
    await tick();
    await tick();
    assert.equal(card.shadowRoot.querySelector(".radar .route"), null);
    assert.equal(card.shadowRoot.querySelector(".picked .route-line").textContent, "No route known");
  },

  async "says nothing about routes when they are off"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.callWS = () => Promise.resolve({ route_points: null, status: "off" });
    const card = render(w, hass);
    link.send(SKY([LOW]));
    card.shadowRoot.querySelector('.plane[data-hex="484506"]').dispatchEvent(new w.Event("click"));
    await tick();
    await tick();
    assert.equal(card.shadowRoot.querySelector(".picked .route-line"), null);
  },

  async "says so when a route could not be looked up"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM), language: "nl" });
    const link = connect(hass);
    hass.callWS = () => Promise.resolve({ route_points: null, status: "failed" });
    const card = render(w, hass);
    link.send(SKY([LOW]));
    card.shadowRoot.querySelector('.plane[data-hex="484506"]').dispatchEvent(new w.Event("click"));
    await tick();
    await tick();
    assert.equal(card.shadowRoot.querySelector(".picked .route-line").textContent, "Route opzoeken mislukt");
  },

  async "stops waiting for an answer that does not come"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM), language: "nl" });
    const link = connect(hass);
    const asked = [];
    hass.callWS = (message) => {
      asked.push(message);
      return new Promise(() => {});
    };
    const card = render(w, hass);
    link.send(SKY([LOW, HIGH]));
    const tap = () => card.shadowRoot.querySelector('.plane[data-hex="4ca123"]').dispatchEvent(new w.Event("click"));
    tap();
    assert.match(card.shadowRoot.querySelector(".picked .route-line").textContent, /Route opzoeken/);
    tap();
    tap();
    assert.equal(asked.length, 1);
    const realNow = w.Date.now;
    w.Date.now = () => realNow() + 61_000;
    try {
      link.send(SKY([LOW, HIGH]));
      assert.equal(card.shadowRoot.querySelector(".picked .route-line").textContent, "Route opzoeken mislukt");
      tap();
      tap();
    } finally {
      w.Date.now = realNow;
    }
    assert.equal(asked.length, 2);
  },

  async "says a route is on its way while it is asked for"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM), language: "nl" });
    const link = connect(hass);
    let answer;
    hass.callWS = () => new Promise((resolve) => (answer = resolve));
    const card = render(w, hass);
    link.send(SKY([LOW, HIGH]));
    card.shadowRoot.querySelector('.plane[data-hex="4ca123"]').dispatchEvent(new w.Event("click"));
    assert.match(card.shadowRoot.querySelector(".picked .route-line").textContent, /Route opzoeken/);
    answer({ route_points: null, status: "unknown" });
    await tick();
    await tick();
    assert.equal(card.shadowRoot.querySelector(".picked .route-line").textContent, "Geen route bekend");
  },

  async "asks again for a route it got no answer for"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const asked = [];
    let reply = () => Promise.reject(new Error("connection lost"));
    hass.callWS = (message) => {
      asked.push(message);
      return reply();
    };
    const card = render(w, hass);
    link.send(SKY([LOW, HIGH]));
    const tap = async () => {
      card.shadowRoot.querySelector('.plane[data-hex="4ca123"]').dispatchEvent(new w.Event("click"));
      await tick();
      await tick();
    };
    // A question that failed is asked again on the next tap.
    await tap();
    await tap();
    await tap();
    assert.equal(asked.length, 2);
    // Nobody knew the route: not again straight away, but a minute on.
    reply = () => Promise.resolve({ route_points: null, status: "unknown" });
    await tap();
    await tap();
    assert.equal(asked.length, 3);
    // A second tap takes the selection off, a third puts it back.
    await tap();
    await tap();
    assert.equal(asked.length, 3);
    const realNow = w.Date.now;
    w.Date.now = () => realNow() + 61_000;
    try {
      await tap();
      await tap();
    } finally {
      w.Date.now = realNow;
    }
    assert.equal(asked.length, 4);
  },

  "keeps to the range it was given"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass, { map_range: 25 });
    link.send(SKY([LOW, HIGH]));
    const shown = [...card.shadowRoot.querySelectorAll(".radar .plane")].map((p) => p.getAttribute("data-hex"));
    assert.deepEqual(shown, ["484506"]);
    assert.match(card.shadowRoot.querySelector(".radar").textContent, /25 km/);
  },

  "says when no aircraft has a position"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    link.send(SKY([]));
    assert.match(card.shadowRoot.querySelector(".radar").textContent, /No aircraft with a position/);
  },

  async "subscribes only with a map, and lets go when removed"() {
    const w = browser();
    let hass = hassWith({ overhead: overheadState(KLM) });
    let link = connect(hass);
    let card = render(w, hass, { map: "none" });
    assert.equal(link.subscriptions.length, 0);
    assert.ok(card.shadowRoot.querySelector(".sky").hidden);

    hass = hassWith({ overhead: overheadState(KLM) });
    link = connect(hass);
    card = render(w, hass);
    card.hass = { ...hass };
    assert.equal(link.subscriptions.length, 1, "a new hass is not a new subscription");
    card.remove();
    await tick();
    assert.equal(link.unsubscribed, 1);
  },

  "draws the same sky on map tiles when asked"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    for (const [sector, km] of [
      ["n", 40],
      ["e", 30],
      ["s", 20],
      ["w", 25],
    ]) {
      const id = `sensor.t_etur47_bereik_${sector}`;
      hass.entities[id] = entity(id, `max_range_${sector}`);
      hass.states[id] = { state: String(km), attributes: { unit_of_measurement: "km" }, last_updated: "t" };
    }
    const link = connect(hass);
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW, HIGH, ROTOR]));
    link.send(SKY([{ ...LOW, latitude: 52.03 }, HIGH, ROTOR]));
    const root = card.shadowRoot;
    const radar = root.querySelector(".radar.streets");
    assert.ok(radar);
    // The tiles under it, enough to fill it. This Home Assistant has no tile
    // proxy to ask, so they come from OpenStreetMap itself.
    const tiles = [...radar.querySelectorAll(".tiles image")].map((i) => i.getAttribute("href"));
    assert.ok(tiles.length >= 2);
    assert.ok(
      tiles.every((href) => /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/.test(href)),
      tiles[0],
    );
    // The same tiles again on the next poll, not loaded afresh.
    const layer = radar.querySelector(".tiles");
    link.send(SKY([{ ...LOW, latitude: 52.031 }, HIGH, ROTOR]));
    assert.equal(root.querySelector(".radar .tiles"), layer);
    // On them, everything the radar draws: the outlines with their labels,
    // the trails, and the coverage.
    assert.equal(radar.querySelectorAll(".plane").length, 3);
    assert.ok(radar.querySelector('.plane[data-hex="484506"] .callsign'));
    assert.equal(radar.querySelectorAll(".trails line").length, 1);
    assert.ok(radar.querySelector(".coverage"));
    // A tapped aircraft says what it is in its title as well.
    assert.match(
      radar.querySelector('.plane[data-hex="484506"] title').textContent,
      /KLM1234 · Boeing 737-800 · 1,500 ft/,
    );
    // The compass letters belong to the scope, not to a map.
    assert.equal(radar.querySelector(".compass"), null);
    // Credited as the tiles ask.
    const credit = root.querySelector(".attribution");
    assert.match(credit.textContent, /© OpenStreetMap contributors/);
    assert.equal(credit.querySelector("a").getAttribute("href"), "https://www.openstreetmap.org/copyright");
  },

  "puts everything where it is on the tiles"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass, { map: "map", map_scale: "fixed", map_range: 50 });
    // Due north and due east of the station, 0.2 degrees out.
    link.send(
      SKY([
        { ...LOW, hex: "n1", latitude: 52.2, longitude: 5.0, distance: 22.2 },
        { ...LOW, hex: "e1", latitude: 52.0, longitude: 5.2, distance: 13.7 },
      ]),
    );
    const at = (hex) =>
      /translate\(([-\d.]+) ([-\d.]+)\)/
        .exec(card.shadowRoot.querySelector(`.plane[data-hex="${hex}"]`).getAttribute("transform"))
        .slice(1)
        .map(Number);
    const [nx, ny] = at("n1");
    const [ex, ey] = at("e1");
    assert.equal(nx, 200);
    assert.ok(ny < 200);
    assert.equal(ey, 200);
    assert.ok(ex > 200);
    // 50 km reaches 184 pixels out, as on the radar: 22.2 km north is about
    // 82 of them, give or take what the map's projection stretches.
    assert.ok(Math.abs(200 - ny - 22.2 * (184 / 50)) < 3, String(ny));
    // The outer ring is at 50 km.
    const rings = [...card.shadowRoot.querySelectorAll(".radar .ring")].map((r) => Number(r.getAttribute("r")));
    assert.ok(Math.abs(rings[1] - 184) < 0.5, String(rings));
  },

  async "takes the tiles from Home Assistant's own proxy where it has one"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    hass.themes = { darkMode: true };
    const link = connect(hass);
    const asked = [];
    hass.connection.sendMessagePromise = (message) => {
      asked.push(message.type);
      return Promise.resolve({ token: "t0k/en" });
    };
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW]));
    // Nothing until it is known where the tiles come from.
    assert.equal(card.shadowRoot.querySelector(".tiles"), null);
    await tick();
    await tick();
    const layer = card.shadowRoot.querySelector(".tiles");
    assert.match(
      layer.querySelector("image").getAttribute("href"),
      /^\/api\/map_tiles\/raster\/\d+\/\d+\/\d+\.png\?token=t0k%2Fen$/,
    );
    // Asked once, not on every poll.
    link.send(SKY([{ ...LOW, latitude: 52.03 }]));
    assert.equal(JSON.stringify(asked), JSON.stringify(["map_tiles/access_token"]));
    // OpenStreetMap has no dark tiles: they are inverted for a dark theme.
    assert.equal(layer.getAttribute("class"), "tiles dark");
    // An SVG filter rather than CSS, which WebKit does not apply inside an SVG.
    assert.equal(layer.getAttribute("filter"), "url(#dark)");
    const dark = card.shadowRoot.querySelector(".radar defs filter#dark");
    assert.deepEqual(
      [...dark.children].map((step) => step.tagName),
      ["feComponentTransfer", "feColorMatrix", "feComponentTransfer"],
    );
    assert.ok(![...card.shadowRoot.querySelectorAll("style")].some((style) => /invert\(/.test(style.textContent)));
  },

  async "draws OpenStreetMap's own data in the theme's colours where Home Assistant serves it"() {
    const { w, asked } = vectorBrowser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.resolve({ token: "t0k" });
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW]));
    await settle();
    const root = card.shadowRoot;
    assert.equal(root.querySelector(".tiles"), null);
    assert.ok(asked.length);
    for (const { url, token } of asked) {
      assert.match(url, /^\/api\/map_tiles\/vector\/\d+\/\d+\/\d+\.mvt$/);
      // As a header, so the address and the browser's cache outlast the token.
      assert.equal(token, "t0k");
    }
    // Water is in half the extent of the names: both are drawn in one.
    assert.equal(
      root.querySelector(".basemap path.water").getAttribute("d"),
      "M1024 1024L3072 1024 3072 3072 1024 3072Z",
    );
    assert.ok(root.querySelector(".basemap path.motorway"));
    assert.ok(root.querySelector(".basemap path.country"));
    // A residential street and a hamlet are more than the map needs.
    assert.equal(root.querySelector(".basemap path.road"), null);
    assert.deepEqual(
      [...root.querySelectorAll(".basemap text")].map((t) => t.textContent),
      ["Utrecht"],
    );
  },

  async "leaves a place's name off where an aircraft is"() {
    const { w } = vectorBrowser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.resolve({ token: "t0k" });
    const card = render(w, hass, { map: "map" });
    const above = { ...LOW, hex: "4851a8", flight: "PHX1", latitude: UTRECHT[0], longitude: UTRECHT[1] };
    link.send(SKY([LOW, above]));
    await settle();
    assert.ok(card.shadowRoot.querySelector(".basemap path.water"));
    assert.equal(card.shadowRoot.querySelector(".basemap text"), null);
  },

  async "leaves a place's name off where it would cover a ring's distance"() {
    // Just above the 5 km ring, where its distance is written.
    const under = [52.0 + 5.4 / 110.574, 5.013];
    const { w } = vectorBrowser((url) => ({ ok: true, status: 200, body: tileFor(url, under) }));
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.resolve({ token: "t0k" });
    const card = render(w, hass, { map: "map", map_scale: "fixed", map_range: 10 });
    link.send(SKY([LOW]));
    await settle();
    const root = card.shadowRoot;
    assert.deepEqual(
      [...root.querySelectorAll(".distance")].map((t) => t.textContent),
      ["5 km", "10 km"],
    );
    assert.ok(root.querySelector(".basemap path.water"));
    assert.equal(root.querySelector(".basemap text"), null);
  },

  async "puts the token in the address for Home Assistant 2026.9, which takes no header"() {
    const { w, asked } = vectorBrowser((url, header) =>
      url.includes("?token=t0k") && !header
        ? { ok: true, status: 200, body: tileFor(url) }
        : { ok: false, status: 403 },
    );
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.resolve({ token: "t0k" });
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW]));
    await settle();
    assert.equal(asked[0].token, "t0k");
    assert.match(asked[asked.length - 1].url, /\.mvt\?token=t0k$/);
    assert.ok(card.shadowRoot.querySelector(".basemap path.water"));
  },

  async "keeps to the picture tiles where Home Assistant has no vector tiles"() {
    const { w, asked } = vectorBrowser(() => ({ ok: false, status: 404 }));
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.resolve({ token: "t0k" });
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW]));
    await settle();
    const tried = asked.length;
    assert.ok(tried);
    assert.equal(card.shadowRoot.querySelector(".basemap"), null);
    assert.match(card.shadowRoot.querySelector(".tiles image").getAttribute("href"), /^\/api\/map_tiles\/raster\//);
    // Not asked again on every poll.
    link.send(SKY([LOW]));
    await settle();
    assert.equal(asked.length, tried);
  },

  async "falls back on OpenStreetMap where there is no proxy"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    hass.connection.sendMessagePromise = () => Promise.reject(new Error("unknown_command"));
    const card = render(w, hass, { map: "map" });
    link.send(SKY([LOW]));
    await tick();
    await tick();
    assert.match(
      card.shadowRoot.querySelector(".tiles image").getAttribute("href"),
      /^https:\/\/tile\.openstreetmap\.org\//,
    );
    assert.equal(card.shadowRoot.querySelector(".tiles").getAttribute("class"), "tiles");
    // A light theme keeps the tiles as they are.
    assert.equal(card.shadowRoot.querySelector(".tiles").getAttribute("filter"), null);
  },

  "draws the furthest heard in each direction on the radar"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    // The record sensors, in metres as one of them was set to, and one sector
    // without a record yet.
    const records = { n: 80, ne: 60, e: 40, se: null, s: 20, sw: 30, w: 50, nw: 70 };
    for (const [sector, km] of Object.entries(records)) {
      const id = `sensor.t_etur47_bereik_${sector}`;
      hass.entities[id] = entity(id, `max_range_${sector}`);
      hass.states[id] =
        km === null
          ? { state: "unknown", attributes: {}, last_updated: "t" }
          : sector === "e"
            ? { state: String(km * 1000), attributes: { unit_of_measurement: "m" }, last_updated: "t" }
            : { state: String(km), attributes: { unit_of_measurement: "km" }, last_updated: "t" };
    }
    const link = connect(hass);
    const card = render(w, hass, { map_range: 100 });
    link.send(SKY([LOW]));
    const corners = card.shadowRoot
      .querySelector(".radar .coverage")
      .getAttribute("points")
      .split(" ")
      .map((p) => p.split(",").map(Number));
    assert.equal(corners.length, 8);
    // North is straight up from the centre, at 80 of the 100 km.
    assert.deepEqual(corners[0], [200, 52.8]);
    // East, in metres, is as far out as 40 km.
    assert.deepEqual(corners[2], [273.6, 200]);
    // No record yet: drawn at the centre.
    assert.deepEqual(corners[3], [200, 200]);
    assert.match(card.shadowRoot.querySelector(".legend").textContent, /furthest heard/);
  },

  "scales to the aircraft, to the records, or not at all, as chosen"() {
    const hass = hassWith({ overhead: overheadState(KLM) });
    for (const [sector, km] of [
      ["n", 140],
      ["e", 60],
      ["s", 40],
      ["w", 90],
    ]) {
      const id = `sensor.t_etur47_bereik_${sector}`;
      hass.entities[id] = entity(id, `max_range_${sector}`);
      hass.states[id] = { state: String(km), attributes: { unit_of_measurement: "km" }, last_updated: "t" };
    }
    const outer = (config) => {
      const w = browser();
      const copy = { ...hass };
      const link = connect(copy);
      const card = render(w, copy, config);
      link.send(SKY([LOW, HIGH]));
      return [...card.shadowRoot.querySelectorAll(".radar .distance")].pop().textContent;
    };
    // HIGH is 49 km out, the record to the north 140 km.
    assert.equal(outer({}), "50 km");
    assert.equal(outer({ map_scale: "aircraft" }), "50 km");
    assert.equal(outer({ map_scale: "coverage" }), "150 km");
    assert.equal(outer({ map_scale: "fixed", map_range: 75 }), "75 km");
    assert.equal(outer({ map_scale: "fixed" }), "100 km");
    // A range without a scale, as before there was a choice, is a fixed one.
    assert.equal(outer({ map_range: 25 }), "25 km");
    // And a range is ignored while the scale is automatic.
    assert.equal(outer({ map_scale: "aircraft", map_range: 25 }), "50 km");
  },

  "leaves the shape off until there is one to draw"() {
    const w = browser();
    const hass = hassWith({ overhead: overheadState(KLM) });
    const link = connect(hass);
    const card = render(w, hass);
    link.send(SKY([LOW]));
    assert.equal(card.shadowRoot.querySelector(".radar .coverage"), null);
    assert.doesNotMatch(card.shadowRoot.querySelector(".legend").textContent, /furthest heard/);
  },
};

let failed = 0;
for (const [name, test] of Object.entries(tests)) {
  try {
    await test();
    console.log(`ok   ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${name}\n     ${error.message.split("\n").join("\n     ")}`);
  }
}
console.log(`${Object.keys(tests).length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
