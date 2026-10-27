/*
 * ADS-B Station card.
 *
 * Served by the integration itself and loaded on every dashboard, so there is
 * nothing to download or add as a resource. It finds the station's entities by
 * what they are rather than by their IDs, which are in whatever language Home
 * Assistant was set to when they were made: every entity of this integration
 * carries a fixed translation key, and hass.entities says which is which.
 *
 * Plain JavaScript on purpose. There is no build step, so what is in the
 * repository is exactly what runs, and it ships in the integration's zip.
 */

const DOMAIN = "adsb_station";
const CARD = "adsb-station-card";

const STRINGS = {
  en: {
    name: "ADS-B Station",
    description:
      "The aircraft overhead with its photo, the others nearby, and how the station is doing.",
    overhead: "Overhead now",
    last_overhead: "Last overhead",
    nothing: "Nothing overhead right now",
    no_station: "No ADS-B station with a receiver was found.",
    nearby: "Also nearby",
    on_ground: "on the ground",
    photo: "Photo",
    received: "received",
    station: "Station",
    show_nearby: "Show the aircraft nearby",
    max_nearby: "How many nearby to show at most",
    show_status: "Show how the station is doing",
    title: "Title",
  },
  nl: {
    name: "ADS-B Station",
    description:
      "Het vliegtuig overhead met foto, de andere dichtbij, en hoe het station ervoor staat.",
    overhead: "Nu overhead",
    last_overhead: "Laatst overhead",
    nothing: "Er is nu niets overhead",
    no_station: "Er is geen ADS-B-station met een ontvanger gevonden.",
    nearby: "Ook dichtbij",
    on_ground: "aan de grond",
    photo: "Foto",
    received: "ontvangen",
    station: "Station",
    show_nearby: "Toestellen dichtbij tonen",
    max_nearby: "Hoeveel toestellen dichtbij maximaal",
    show_status: "Tonen hoe het station ervoor staat",
    title: "Titel",
  },
};

// Climbing or descending faster than this, in feet per minute, gets an arrow.
// The same line the map icons draw.
const CLIMB_RATE_SHOWN = 500;
const DEFAULT_MAX_NEARBY = 5;

function strings(hass) {
  const language = (hass && hass.locale && hass.locale.language) || "en";
  return STRINGS[language.split("-")[0]] || STRINGS.en;
}

function el(tag, attributes, ...children) {
  // Everything that reaches the page goes through textContent or a property,
  // never through innerHTML: the attributes come from aircraft and from other
  // people's servers, and none of it is markup.
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
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

// Only an https address is put on the page as a link or an image. Everything
// the photo lookup hands over is, and anything else is left out rather than
// followed.
function safeUrl(value) {
  return typeof value === "string" && value.startsWith("https://") ? value : null;
}

class AdsbStationCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "device_id", selector: { device: { integration: DOMAIN } } },
        { name: "title", selector: { text: {} } },
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

  setConfig(config) {
    this._config = {
      show_nearby: true,
      show_status: true,
      max_nearby: DEFAULT_MAX_NEARBY,
      ...(config || {}),
    };
    this._signature = undefined;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // The config form has no hass of its own to read the language from.
    window.__adsbStationHass = hass;
    if (this._config) this._render();
  }

  getCardSize() {
    return 6;
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
      feeds,
    };
  }

  _state(entry) {
    return entry ? this._hass.states[entry.entity_id] : undefined;
  }

  _render() {
    const found = this._find();
    const watched = found
      ? [found.overhead, found.nearby, found.received, found.rate, found.range, ...found.feeds]
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

    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const text = strings(this._hass);
    const card = el("ha-card", { header: this._config.title || undefined });
    if (!found) {
      card.append(el("div", { class: "empty" }, text.no_station));
    } else {
      card.append(this._overhead(found, text));
      if (this._config.show_nearby) {
        const nearby = this._nearby(found, text);
        if (nearby) card.append(nearby);
      }
      if (this._config.show_status) card.append(this._status(found, text));
    }
    this.shadowRoot.replaceChildren(el("style", {}, STYLE), card);
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
      el("ha-icon", { icon: aircraftIcon(plane) }),
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
          el("ha-icon", { icon: aircraftIcon(plane) }),
          el("span", { class: "flight" }, plane.flight || plane.hex),
          el("span", { class: "what" }, plane.airline || plane.description || ""),
          el("span", { class: "figure" }, this._distance(plane.distance) || ""),
          el("span", { class: "figure" }, this._height(plane, text) || "")
        )
      )
    );
  }

  _status(found, text) {
    const shown = (entry) => {
      const state = this._state(entry);
      if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
      return this._hass.formatEntityState ? this._hass.formatEntityState(state) : state.state;
    };
    const figures = [
      found.received && shown(found.received) && `${shown(found.received)} ${text.received}`,
      shown(found.rate),
      shown(found.range),
    ].filter(Boolean);
    const line = el("div", { class: "status" });
    if (figures.length) {
      line.append(
        el(
          "span",
          { class: "figures", role: "button", tabindex: "0", onclick: this._moreInfo(found.received) },
          figures.join(" · ")
        )
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
  ha-card { overflow: hidden; }
  .empty { display: flex; align-items: center; gap: 12px; padding: 16px; color: var(--secondary-text-color); }
  .overhead { padding: 16px 16px 8px; }
  .label { font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; color: var(--secondary-text-color); margin-bottom: 8px; }
  .photo img { display: block; width: 100%; max-height: 240px; object-fit: cover; border-radius: var(--ha-card-border-radius, 12px); }
  .credit { font-size: 0.8em; color: var(--secondary-text-color); margin: 4px 0 12px; }
  .credit a { color: inherit; }
  .details { display: flex; gap: 12px; align-items: flex-start; cursor: pointer; }
  .details ha-icon { color: var(--state-icon-color, var(--primary-color)); margin-top: 2px; }
  .lines { min-width: 0; }
  .primary { font-size: 1.1em; font-weight: 500; }
  .secondary { color: var(--secondary-text-color); white-space: pre-wrap; }
  .nearby { padding: 8px 16px; border-top: 1px solid var(--divider-color); }
  .row { display: grid; grid-template-columns: 24px auto 1fr auto auto; gap: 8px; align-items: center; padding: 4px 0; cursor: pointer; }
  .row ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .flight { font-weight: 500; }
  .what { color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .figure { color: var(--secondary-text-color); text-align: right; font-variant-numeric: tabular-nums; }
  .status { display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 12px 16px; border-top: 1px solid var(--divider-color); color: var(--secondary-text-color); font-size: 0.9em; }
  .figures, .feed { cursor: pointer; }
  .feed { display: inline-flex; align-items: center; gap: 6px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--error-color, #db4437); }
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
