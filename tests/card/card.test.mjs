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
  hex: "484506", flight: "KLM1234", airline: "KLM", description: "Boeing 737-800",
  registration: "PH-BXA", origin: "AMS", destination: "LHR", altitude: 3200,
  vertical_rate: 1500, distance: 1.1, overhead: true,
  photo: "https://t.plnspttrs.net/1/1_280.jpg",
  photo_link: "https://www.planespotters.net/photo/1/ph-bxa",
  photographer: "Jan Seler",
};
const overheadState = (attributes, state = attributes.flight) => ({ state, attributes, last_updated: "t" });

// A websocket that hands the card's subscription to the test, which then
// plays the integration and sends it the sky.
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
  hex: "484506", flight: "KLM1234", latitude: 52.02, longitude: 5.0, altitude: 1500, track: 90,
  distance: 2.2, speed: 160, description: "Boeing 737-800", registration: "PH-BXA",
};
const HIGH = { hex: "4ca123", flight: "RYR5", latitude: 52.4, longitude: 5.3, altitude: 37000, track: 270, distance: 49.0 };
const ROTOR = { hex: "4851a7", flight: "LIFE01", latitude: 51.98, longitude: 4.98, altitude: 900, category: "A7", distance: 2.6 };

const hue = (color) => Number(/hsl\((\d+)/.exec(color)[1]);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const tests = {
  "registers itself for the card picker"() {
    const w = browser();
    assert.ok(w.customElements.get("adsb-station-card"));
    assert.equal(w.customCards.length, 1);
    assert.equal(w.customCards[0].type, "adsb-station-card");
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
    assert.deepEqual(rows.map((r) => r.querySelector(".flight").textContent), ["TRA45", "LIFE01"]);
    assert.equal(rows[1].querySelector("ha-icon").getAttribute("icon"), "mdi:helicopter");
    // The status line, with a dot per network.
    const figures = [...root.querySelectorAll(".status .figures")].map((f) => f.textContent);
    assert.equal(JSON.stringify(figures), JSON.stringify(["468 received", "75.0 msg/s", "67.9 km", "S/N 18.7 dB"]));
    const feeds = [...root.querySelectorAll(".feed")].map((f) => [f.textContent, f.className]);
    assert.deepEqual(feeds, [["Flightradar24", "feed good"], ["FlightAware", "feed warn"]]);
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
      })
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
    card.hass = { ...hass, states: { ...hass.states, "sensor.unrelated": { state: "2", attributes: {}, last_updated: "u" } } };
    assert.equal(card.shadowRoot.querySelector(".body").firstElementChild, before);
    card.hass = { ...hass, states: { ...hass.states, "sensor.t_etur47_vliegtuigen_ontvangen": { state: "470", attributes: {}, last_updated: "u" } } };
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
    assert.equal(JSON.stringify(form.schema.map((s) => s.name)), JSON.stringify(["device_id", "title", "map", "map_scale", "map_range", "show_nearby", "max_nearby", "show_status"]));
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
      JSON.stringify({ type: "adsb_station/subscribe_aircraft", device_id: DEVICE })
    );

    link.send(SKY([LOW, HIGH, ROTOR]));
    const root = card.shadowRoot;
    const planes = [...root.querySelectorAll(".radar .plane")];
    // Low ones first, so the one at cruising height is drawn on top.
    assert.deepEqual(planes.map((p) => p.querySelector(".callsign").textContent), ["LIFE01", "KLM1234", "RYR5"]);
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
    for (const [sector, km] of [["n", 40], ["e", 30], ["s", 20], ["w", 25]]) {
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
    assert.ok(tiles.every((href) => /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/.test(href)), tiles[0]);
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
    assert.match(radar.querySelector('.plane[data-hex="484506"] title').textContent, /KLM1234 · Boeing 737-800 · 1,500 ft/);
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
    link.send(SKY([
      { ...LOW, hex: "n1", latitude: 52.2, longitude: 5.0, distance: 22.2 },
      { ...LOW, hex: "e1", latitude: 52.0, longitude: 5.2, distance: 13.7 },
    ]));
    const at = (hex) =>
      /translate\(([-\d.]+) ([-\d.]+)\)/.exec(card.shadowRoot.querySelector(`.plane[data-hex="${hex}"]`).getAttribute("transform")).slice(1).map(Number);
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
    assert.match(layer.querySelector("image").getAttribute("href"), /^\/api\/map_tiles\/raster\/\d+\/\d+\/\d+\.png\?token=t0k%2Fen$/);
    // Asked once, not on every poll.
    link.send(SKY([{ ...LOW, latitude: 52.03 }]));
    assert.equal(JSON.stringify(asked), JSON.stringify(["map_tiles/access_token"]));
    // OpenStreetMap has no dark tiles: they are inverted for a dark theme.
    assert.equal(layer.getAttribute("class"), "tiles dark");
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
    assert.match(card.shadowRoot.querySelector(".tiles image").getAttribute("href"), /^https:\/\/tile\.openstreetmap\.org\//);
    assert.equal(card.shadowRoot.querySelector(".tiles").getAttribute("class"), "tiles");
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
    for (const [sector, km] of [["n", 140], ["e", 60], ["s", 40], ["w", 90]]) {
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
