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
    assert.match(root.querySelector(".status").textContent, /468 received · 75\.0 msg\/s · 67\.9 km/);
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
    const before = card.shadowRoot.querySelector("ha-card");
    card.hass = { ...hass, states: { ...hass.states, "sensor.unrelated": { state: "2", attributes: {}, last_updated: "u" } } };
    assert.equal(card.shadowRoot.querySelector("ha-card"), before);
    card.hass = { ...hass, states: { ...hass.states, "sensor.t_etur47_vliegtuigen_ontvangen": { state: "470", attributes: {}, last_updated: "u" } } };
    assert.notEqual(card.shadowRoot.querySelector("ha-card"), before);
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
    assert.equal(JSON.stringify(form.schema.map((s) => s.name)), JSON.stringify(["device_id", "title", "show_nearby", "max_nearby", "show_status"]));
    w.__adsbStationHass = { locale: { language: "nl" } };
    assert.equal(form.computeLabel({ name: "device_id" }), "Station");
    assert.equal(form.computeLabel({ name: "show_nearby" }), "Toestellen dichtbij tonen");
    assert.equal(JSON.stringify(Card.getStubConfig()), "{}");
  },
};

let failed = 0;
for (const [name, test] of Object.entries(tests)) {
  try {
    test();
    console.log(`ok   ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${name}\n     ${error.message.split("\n").join("\n     ")}`);
  }
}
console.log(`${Object.keys(tests).length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
