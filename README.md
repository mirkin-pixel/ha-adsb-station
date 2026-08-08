# ADS-B Station for Home Assistant

[![Validate](https://img.shields.io/github/actions/workflow/status/mirkin-pixel/ha-adsb-station/validate.yml?branch=main&style=for-the-badge&label=Validate)](https://github.com/mirkin-pixel/ha-adsb-station/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/mirkin-pixel/ha-adsb-station?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)
[![License](https://img.shields.io/github/license/mirkin-pixel/ha-adsb-station?style=for-the-badge)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/mirkin-pixel/ha-adsb-station/total?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)

[English](#english) | [Nederlands](#nederlands)

---

## English

Custom integration for [Home Assistant](https://www.home-assistant.io/) that reads **your own ADS-B receiver**. Everything happens on your own network: the integration polls the `aircraft.json` of your decoder and, if you run one, the `monitor.json` status page of `fr24feed` next to it. There is one exception, it is off unless you turn it on, and it has a section of its own: [where a flight is going](#where-a-flight-is-going) is the one thing your antenna cannot hear.

It is not tied to a single network. Anything that serves an `aircraft.json` works, so it does not matter whether you feed Flightradar24, FlightAware, Plane Finder, several of them at once, or nothing at all:

| Decoder | What you get |
|---|---|
| readsb or tar1090 | Every receiver entity, and the most of them — see [Which decoder](#which-decoder) |
| dump1090-fa or SkyAware | Every receiver entity |
| dump1090, dump1090-mutability | The receiver entities its build reports |
| The dump1090 fork bundled with fr24feed | The receiver entities that fork reports |

On top of the decoder it reads the feeders themselves, each of which serves a status page of its own on your network:

| Feeder | Network | Status page |
|---|---|---|
| `fr24feed` | Flightradar24 | `:8754/monitor.json` |
| PiAware | FlightAware | `:8080/status.json` |
| `pfclient` | Plane Finder | `:30053/ajax/stats` |

A station commonly feeds several networks off one decoder, and that is how this is meant to be set up: **one entry per feeder**, each its own device, with the decoder attached to just one of them. The aircraft figures then exist once and every network has its own feed status. A station that feeds nowhere at all works too — set up the receiver on its own.

What you get is a proper device with translated entity names and a config flow, and figures that are awkward to arrive at by hand: the number of aircraft received, the message rate, and the maximum range measured from your antenna.

### Entities

Everything from `aircraft.json` — the part every setup gets:

| Entity | Type | Description |
|---|---|---|
| Aircraft received | Sensor | Aircraft in the last `aircraft.json` |
| Aircraft with position | Sensor | Of those, the number with a known position |
| Maximum range | Sensor (km) | Distance to the furthest aircraft heard |
| Message rate | Sensor (msg/s) | Mode S messages per second, computed between two polls |
| Closest aircraft | Sensor (km) | Distance to the nearest aircraft, with its callsign, altitude, speed, heading, rate of climb, airline and signal strength as attributes. A decoder with an aircraft database adds registration, type and a military marker |
| Highest aircraft | Sensor (ft) | Altitude of the highest aircraft in range, with the same attributes |
| Fastest aircraft | Sensor (kn) | Ground speed of the fastest aircraft in range, with the same attributes |
| Aircraft nearby | Sensor | How many aircraft are inside the nearby radius, with all of them as attributes, nearest first. These are the two that can carry [where the flight is going](#where-a-flight-is-going) |
| Aircraft overhead | Binary sensor | On while at least one aircraft is inside that radius |
| Emergency squawk | Binary sensor (safety) | On while an aircraft in range squawks 7500, 7600 or 7700 |
| Messages | Sensor (diagnostic) | The total message counter of the receiver |
| Receiver updated | Sensor (diagnostic) | The timestamp inside `aircraft.json` |

The highest and the fastest also count aircraft that never broadcast a position: altitude and speed reach us from Mode S alone, and leaving those out would understate both. Their `distance` attribute is then empty.

Those two and the maximum range keep what they last saw rather than blanking when the sky empties, and they survive a restart. A station that hears a couple of aircraft an hour would otherwise report nothing most of the time. The `seen_at` attribute says how long ago it was, and each still follows the sky — a lower aircraft later replaces the reading. That is what separates them from the [sector records](#where-your-antenna-is-blocked), which only ever grow.

And, when your receiver also serves `stats.json`, the health of your reception:

| Entity | Type | Description |
|---|---|---|
| Signal level | Sensor (dBFS) | The mean signal level of the received messages |
| Signal-to-noise ratio | Sensor (dB) | Signal minus noise; the single best measure of how well you are hearing |
| Noise level | Sensor (dBFS, diagnostic) | The noise floor |
| Peak signal level | Sensor (dBFS, diagnostic) | The strongest message in the window |
| Strong signals | Sensor (diagnostic) | Messages that were too loud. Structurally above zero means your gain is too high |
| Samples dropped | Sensor (diagnostic) | Samples the host could not keep up with. Anything but zero means you are silently losing messages |
| Messages accepted | Sensor (diagnostic) | Accepted messages in the window, summed over all error correction levels |
| Tracks | Sensor (diagnostic) | Aircraft tracks started in the window |
| Single-message tracks | Sensor (diagnostic) | Tracks that never got a second message; a high share points at poor decoding |
| Demodulator load | Sensor (%, diagnostic) | How much CPU time the decoder spent demodulating |
| Gain | Sensor (dB) | The gain the dongle is running at. Only created when the decoder reports one |
| Message error rate | Sensor (%, diagnostic) | Share of Mode S messages that failed to decode. Unknown during a minute with no traffic, because there is nothing to take a share of |
| Aircraft via ADS-B | Sensor | Aircraft heard broadcasting their own position |
| Aircraft via MLAT | Sensor | Aircraft located by multilateration instead |
| Aircraft via Mode S | Sensor (diagnostic) | Aircraft heard, but never giving a position |
| Frequency error | Sensor (ppm, diagnostic) | How far the dongle's clock sits off its nominal frequency |
| Positions decoded | Sensor (diagnostic) | Positions accepted in the window |
| Positions rejected | Sensor (diagnostic) | Positions thrown out by the sanity checks. A rising share points at a noisy signal |

Altitudes are in feet, ground speeds in knots and distances in kilometres, which is how aviation reads them. Every one of those carries a device class, so you can switch an individual entity to metres, miles, km/h or mph under **Settings → Entity → Unit of measurement**, and history and statistics follow.

The reception figures come from the shortest measurement window that has actually measured a signal, normally `last1min`. The window a value came from is on the entity as a `period` attribute.

### Feeders

Each feeder adds its own entities, on its own device. Which of these you see depends on which feeder that entry was set up for.

**Flightradar24**, from the `monitor.json` of `fr24feed`:

| Entity | Type | Description |
|---|---|---|
| Aircraft tracked | Sensor | Aircraft the feeder is currently tracking |
| Aircraft tracked via ADS-B | Sensor | Of those, the number tracked via ADS-B |
| Aircraft uploaded | Sensor | Aircraft in the last upload to Flightradar24 |
| Feed status | Sensor | The raw status text of the feed |
| Receiver | Binary sensor (connectivity) | On while `fr24feed` sees the dongle |
| Feed | Binary sensor (connectivity) | On while the feed reaches Flightradar24 |
| MLAT | Binary sensor (connectivity, diagnostic) | On while multilateration works |
| Feed mode | Sensor (diagnostic) | The current feed mode, for example MLAT |
| Feed alias | Sensor (diagnostic) | Your feeder ID, for example T-EHXX23 |
| Map size | Sensor (diagnostic) | The `d11_map_size` of the feeder |
| Resets | Sensor (diagnostic) | The number of resets since the start |
| Last connected | Sensor (diagnostic) | When the feed last connected |
| CPU temperature | Sensor (diagnostic) | The SoC temperature of the host. Only on the single board computer builds |
| Clock drift | Sensor (s, diagnostic) | How far the feeder's clock drifted. Multilateration needs this small |
| Timing source | Sensor (diagnostic) | What the feeder synchronises its clock against, for example NTP |
| Feed server | Sensor (diagnostic) | The Flightradar24 server this feeder talks to |
| Resyncs | Sensor (diagnostic) | How often the feeder had to resynchronise |

**FlightAware**, from the `status.json` of PiAware:

| Entity | Type | Description |
|---|---|---|
| Radio | Sensor | Whether the decoder is being heard |
| Feed | Sensor | The connection to FlightAware |
| MLAT | Sensor | Multilateration |
| PiAware service | Sensor (diagnostic) | The feeder itself |
| CPU load | Sensor (%, diagnostic) | Load on the host |
| Uptime | Sensor (h, diagnostic) | How long the host has been up |
| CPU temperature | Sensor (diagnostic) | Only created on a host that reads one |

Those four are green, amber or red rather than on or off, because amber says something neither of the other two can: a feeder reporting an unstable clock is running fine but will never multilaterate. The colour is the state and the sentence behind it — *"Local clock source is unstable"* — is on the entity as a `message` attribute.

**Plane Finder**, from the `/ajax/stats` of `pfclient`:

| Entity | Type | Description |
|---|---|---|
| Message rate | Sensor (msg/s) | Mode S packets per second, as pfclient counts them |
| MLAT | Binary sensor (connectivity) | On while multilateration data is being uploaded |
| Mode S messages | Sensor (diagnostic) | Total packets since the client started |
| Mode A/C messages | Sensor (diagnostic) | Of those, the Mode A/C ones |
| CRC errors | Sensor (diagnostic) | Packets that failed their checksum |
| Uploaded | Sensor (MB, diagnostic) | Sent to Plane Finder |
| MLAT uploaded | Sensor (kB, diagnostic) | Of that, the multilateration share |
| Receiver data rate | Sensor (B/s, diagnostic) | Coming in from the decoder |

pfclient publishes no multilateration flag of its own, but it does count what it has sent, and a station whose clock is too unstable to multilaterate sends nothing at all — so the byte counter is the sensor.

With a feeder, the feeder and the receiver are read independently: if the decoder stops answering, only the aircraft entities become unavailable and the feed entities keep working. Without a feeder the decoder is the only source, so an outage takes everything with it.

#### Where your antenna is blocked

A single maximum range figure hides the shape of your coverage: 250 km to the south and 40 km to the north is a very different station from 145 km all round. Eight sensors keep the furthest an aircraft has ever been heard in each compass sector, spanning 45 degrees centred on their direction, so **Maximum range north** covers 337.5° to 22.5°.

| Entity | Type | Description |
|---|---|---|
| Maximum range north … northwest | Sensor (km) | The record for that sector, with `recorded_at`, `flight` and `hex` as attributes |
| Reset range records | Button | Clears all eight |

The records only ever grow, and they survive a restart of Home Assistant — a record that started over every restart would be worth nothing. The sensors also stay readable when nothing is flying, because a record from last month is still a reading.

That same growth makes them wrong the moment the antenna moves or a neighbour puts up a shed, which is what the button is for. Pressing it while aircraft are in view immediately sets fresh records from them, measured from where the antenna is now.

### Which decoder

Every decoder gives you the entities above that it has data for; what it reports is detected when you set it up, so no entity is created that could never have a value. That does mean the decoder you run decides how much you get, and **readsb gives you the most**:

| | fr24feed's dump1090 fork | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Aircraft, range, message rate | Yes | Yes | Yes |
| Signal, noise, signal-to-noise | Yes | Yes | Yes |
| Gain | No | Yes | Yes |
| Antenna position in `receiver.json` | No | Yes | Yes |
| Registration, type, description | No | No | Yes, with an aircraft database |
| Military marker | No | No | Yes, with an aircraft database |

Two of those are worth spelling out. Without a gain figure you are tuning your dongle blind, and without an antenna position in `receiver.json` the range is measured from the home location of your Home Assistant installation instead of from your antenna — fine if they are the same place, wrong if your receiver sits elsewhere.

If you already run `fr24feed` and nothing else, replacing its bundled dump1090 with readsb costs you nothing and adds the gain sensor, the aircraft details and a real antenna position. **Run Reconfigure after upgrading your decoder** to pick up what it can do now.

#### The aircraft database

The last two rows need one extra step. readsb only fills in `r`, `t`, `desc` and `dbFlags` when it has been given an aircraft database, and without one the closest aircraft sensor reports a hex code and a callsign but no registration, type or military marker.

On a readsb install, fetch the database and point readsb at it:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Then add the option to `/etc/default/readsb`, in the arguments readsb is started with:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Restart readsb, and the extra fields appear in `aircraft.json` straight away. The integration picks them up on its own — the attributes are added as soon as the decoder sends them, so there is nothing to reconfigure. The database is a snapshot, so refresh it now and then by running the same command again.

#### Names for the codes

An aircraft broadcasts `DLH6CH` and `A20N`. Neither is a name, and no decoder can make one of them, because the names are not in the radio signal at all — they are a list somebody keeps. The integration ships that list, so the aircraft attributes carry a name without anything being asked over the internet:

| Attribute | Read from | Example |
|---|---|---|
| `airline` | The first three letters of the callsign | `DLH6CH` → `Lufthansa` |
| `description` | The ICAO type code, where the decoder does not describe it itself | `A20N` → `Airbus A-320neo` |

A callsign that is not a flight number names no airline. Business jets, gliders and most light aircraft fly under their registration, so `PHABC` is left alone rather than read as an airline code and turned into whatever `PHA` happens to be.

A type code covers a family rather than a single aircraft: an A20N is an A320neo but also the corporate version of it, and a BE20 is any of a dozen King Airs and their military cousins. Nothing in the data says which one you are most likely to see, so the name is the one the code itself spells out. That is right for the airliners and can land on an odd variant for general aviation.

Both tables come from the [standing data of Virtual Radar Server](https://github.com/vradarserver/standing-data), which is in the public domain under CC0-1.0. Like the aircraft database above they are a snapshot; `scripts/build_reference.py` regenerates them from the source.

### Installation

Requires Home Assistant 2026.3 or newer.

#### Via HACS

1. Open HACS in Home Assistant.
2. Choose **⋮ → Custom repositories**, add `https://github.com/mirkin-pixel/ha-adsb-station` as an **Integration**.
3. Search for **ADS-B Station** and click **Download**.
4. Restart Home Assistant.

#### Manual

1. Copy the `custom_components/adsb_station` folder into the `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

### Configuration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **ADS-B Station**.
3. Choose what this entry is for:
   - **Flightradar24 feeder (fr24feed)** — the address of the machine running it, and the port of its status page, `8754` by default.
   - **FlightAware feeder (PiAware)** — likewise, port `8080` by default. A station whose web server was taken over by something else may serve `status.json` elsewhere; on one running tar1090 behind nginx it is worth trying port 80.
   - **Plane Finder feeder (pfclient)** — likewise, port `30053` by default.
   - **ADS-B receiver only** — for a station that feeds nowhere, or as the entry that carries the decoder.
4. Every path then offers the receiver. Attach it to one entry and leave it empty on the others, or the aircraft figures are counted several times over.

These paths are probed automatically, on port 8080 where fr24feed and PiAware serve them and on port 80 where readsb with tar1090 does:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

All candidates are probed at the same time, and the first one in that order that answers wins. If yours is somewhere else, type the full URL yourself.

Three settings live under **Configure** on the integration page. The update interval is 15 seconds by default; everything runs on your own network, so a short interval is fine. The nearby radius is 10 km by default and decides what counts as overhead for the **Aircraft nearby** and **Aircraft overhead** entities — ten kilometres is roughly what you can see and hear, while a good receiver reaches many times that. The third is [where a flight is going](#where-a-flight-is-going), which is off. Moved your station to a different address? Use **Reconfigure** instead of adding it again.

Adding a feeder to a station you set up as receiver-only means adding it as a second entry, which is the same thing you do to add a second or third network later.

### Where a flight is going

Your antenna never hears this. An aircraft broadcasts a callsign — `KLM1234` — and nothing about the flight behind it, so where it took off and where it is heading is not in `aircraft.json` and cannot be. Every map that shows you a route, tar1090 included, asks a database on the ground. That makes it the one figure this integration cannot get on your own network, which is why **Look up flight routes** under **Configure** is off until you switch it on.

The source is **routeset**, reached through `adsb.im`, which is what tar1090 itself uses. It needs no account and no key, it takes every callsign of a poll in one request, and it is given the position each aircraft was heard at.

That last part is what makes it worth trusting, and it is the reason it is the only source here. A modern airline callsign is reused across the legs of a day, so a database that answers on the flight number alone hands back whichever leg it has on file — and about as often as not, that is the leg the aircraft has just flown. routeset is told where the aircraft is and drops a route that does not fit it.

The difference is not small. Measured against the track the aircraft themselves were broadcasting, over three samples of around 160 aircraft above the Netherlands:

| | routeset | A source answering per flight number |
|---|---|---|
| Callsigns it answered | 96% | 88% |
| Answers pointing where the aircraft was actually going | **99%** | 73% |
| Answers pointing the opposite way | 1% | **15%** |
| Requests for 160 aircraft | 1 | 142 |

One in seven is a notification telling you the aircraft overhead is going to the airport it took off from an hour ago, and a wrong route is worse than no route.

Only the aircraft inside your nearby radius are ever looked up. Those are the handful an automation acts on, and asking about every aircraft in range would be a stream of requests to someone else's server for a figure nothing displays. Answers are kept for twelve hours, so the airliners that pass over every day are asked about once rather than once per poll, and no more than 25 new callsigns are looked up per poll.

When a route is found it appears on each aircraft in the **Aircraft nearby** and **Aircraft overhead** attributes:

| Attribute | Example |
|---|---|
| `route` | `CDG-AMS` |
| `origin`, `destination` | `CDG`, `AMS` |
| `origin_location`, `destination_location` | `Paris`, `Amsterdam` |
| `origin_name`, `destination_name` | `Charles de Gaulle International Airport` |

The airline is not among them, and does not need to be: it is [there either way](#names-for-the-codes).

Attributes that are not known are left out rather than left empty, so a template can ask whether the key is there at all. Private, military and a good deal of cargo traffic resolves to nothing, and the source being unreachable simply means no route that poll — the aircraft entities themselves never depend on it.

An aircraft that broadcasts no position gets no route either, because the source judges every route it finds against where the aircraft is. In practice nothing is lost: only the aircraft near enough to be looked up are asked about, and being near enough is measured from a position.

### Example automations

Notification when an aircraft in range declares an emergency:

```yaml
automation:
  - alias: "ADS-B: emergency squawk"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_emergency_squawk
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            Emergency squawk from
            {{ state_attr('binary_sensor.ads_b_station_emergency_squawk',
                          'aircraft')[0].flight or 'an unknown aircraft' }}.
```

Notification when something goes over, saying what it is and where it is headed:

```yaml
automation:
  - alias: "ADS-B: aircraft overhead"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_aircraft_overhead
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {% set plane = state_attr(
                 'binary_sensor.ads_b_station_aircraft_overhead',
                 'aircraft')[0] %}
            {{ plane.airline | default(plane.flight or 'An unknown aircraft') }}
            overhead at {{ plane.altitude }} ft
            {%- if plane.description is defined %},
            {{ plane.description }}
            {%- endif %}
            {%- if plane.vertical_rate %},
            {{ 'climbing' if plane.vertical_rate > 0 else 'descending' }}
            {{ plane.vertical_rate | abs }} ft/min
            {%- endif %}
            {%- if plane.origin_location is defined %},
            {{ plane.origin_location }} to {{ plane.destination_location }}
            {%- endif %}.
```

Which reads as *"Lufthansa overhead at 4100 ft, Airbus A-320neo, descending 1088 ft/min, Paris to Amsterdam."*

Every one of those four is a key that can be missing, and each for its own reason, which is why the template asks rather than reads. The airline and the type name are there for the flights the [shipped tables](#names-for-the-codes) recognise, so a business jet under its registration falls back to the callsign. The rate of climb is absent from aircraft on the ground and zero in level flight, where saying nothing is better than saying "climbing 0". The route needs a [source configured](#where-a-flight-is-going) and is only there for the flights it knows.

Keep a daily record of your best range:

```yaml
sensor:
  - platform: statistics
    name: "ADS-B range today"
    entity_id: sensor.ads_b_station_maximum_range
    state_characteristic: value_max
    max_age:
      hours: 24
```

Notification when the Flightradar24 feed drops, for a station that runs `fr24feed`:

```yaml
automation:
  - alias: "FR24: feed offline"
    trigger:
      - platform: state
        entity_id: binary_sensor.t_ehxx23_feed
        to: "off"
        for: "00:05:00"
    action:
      - service: notify.mobile_app
        data:
          message: "The Flightradar24 feed has been offline for 5 minutes."
```

The entity IDs above follow the device name: `ads_b_station` for a station without a feeder, your feed alias for one with. Rename the device in Home Assistant and the entity IDs follow.

### About the endpoints

Every endpoint is plain, unauthenticated HTTP on your local network:

- `http://<host>:8080/<path>/aircraft.json` — the aircraft list of your decoder.
- `<path>/stats.json` and `<path>/receiver.json` — found automatically next to `aircraft.json`.
- `http://<host>:8754/monitor.json` — the status page of `fr24feed`.
- `http://<host>:8080/status.json` — the status page of PiAware.
- `http://<host>:30053/ajax/stats` — the statistics of `pfclient`.

The last three are read only by the entry set up for that feeder.

Nothing else is contacted unless you ask for it. The single exception is [looking up a route](#where-a-flight-is-going), which reaches `adsb.im` over HTTPS and sends nothing but a callsign and the position it was heard at. Leave that setting off and the integration never leaves your network.

The integration reads them, it never writes. Ranges are measured from the antenna position in `receiver.json`; when the decoder publishes none, the home location of your Home Assistant installation is used, so make sure that location is correct.

Field names differ between decoders. The fr24feed fork reports `altitude` and `speed` where dump1090-fa and readsb report `alt_baro` and `gs`; the integration accepts both. The message rate is derived from two consecutive polls; after a restart of the receiver, the first value is skipped because its counter starts over.

### Troubleshooting

If entities stay `unknown` or `unavailable`, collect the two things below and attach them to an [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Enable debug logging.** Go to **Settings → Devices & services → ADS-B Station**, click the three dots and choose **Enable debug logging**. Reproduce the problem, then choose **Disable debug logging** — Home Assistant downloads the log automatically.

To log across a restart, add this to `configuration.yaml` instead:

```yaml
logger:
  default: warning
  logs:
    custom_components.adsb_station: debug
```

Debug logging shows the HTTP status of every poll and any value the integration could not parse.

**Download diagnostics.** On the same page, choose **Download diagnostics**. The file contains the configuration and the last poll, with the address of your receiver and your feed alias redacted.

### Development

Working on the integration itself is covered in [CONTRIBUTING.md](CONTRIBUTING.md): how to set up, the three checks that are the whole of what CI can tell you about the code, how the code is laid out, and how a release is cut. It needs Python 3.14 or newer and nothing else — no Home Assistant installation of your own.

```bash
pip install -r requirements_test.txt
scripts/check.sh          # or scripts\check.ps1
```

### Disclaimer

This is an unofficial integration and is not affiliated with Flightradar24, FlightAware or Plane Finder. Use at your own risk.

---

## Nederlands

Custom integration voor [Home Assistant](https://www.home-assistant.io/) die **je eigen ADS-B-ontvanger** uitleest. Alles gebeurt op je eigen netwerk: de integratie leest de `aircraft.json` van je decoder uit en, als je die draait, de statuspagina `monitor.json` van `fr24feed` ernaast. Er is één uitzondering, die staat uit tenzij je hem aanzet, en die heeft een eigen hoofdstuk: [waar een vlucht heen gaat](#waar-een-vlucht-heen-gaat) is het enige wat je antenne niet kan horen.

De integratie zit niet vast aan één netwerk. Alles wat een `aircraft.json` aanbiedt werkt, dus het maakt niet uit of je aan Flightradar24, FlightAware of Plane Finder voedt, aan meerdere tegelijk, of aan niets:

| Decoder | Wat je krijgt |
|---|---|
| readsb of tar1090 | Alle ontvanger-entiteiten, en daarvan de meeste — zie [Welke decoder](#welke-decoder) |
| dump1090-fa of SkyAware | Alle ontvanger-entiteiten |
| dump1090, dump1090-mutability | De ontvanger-entiteiten die deze build meldt |
| De dump1090-fork die fr24feed meelevert | De ontvanger-entiteiten die die fork meldt |

Bovenop de decoder leest de integratie de feeders zelf uit, die elk hun eigen statuspagina op je netwerk aanbieden:

| Feeder | Netwerk | Statuspagina |
|---|---|---|
| `fr24feed` | Flightradar24 | `:8754/monitor.json` |
| PiAware | FlightAware | `:8080/status.json` |
| `pfclient` | Plane Finder | `:30053/ajax/stats` |

Een station voedt vaak meerdere netwerken vanaf één decoder, en zo is dit ook bedoeld: **één entry per feeder**, elk een eigen apparaat, met de decoder aan precies één ervan gekoppeld. Dan bestaan de vliegtuigcijfers één keer en heeft elk netwerk zijn eigen feedstatus. Een station dat nergens aan voedt kan ook — dan zet je alleen de ontvanger op.

Wat je krijgt is een echt apparaat met vertaalde entiteitsnamen en een configuratieflow, en cijfers waar je met de hand lastig aan komt: het aantal ontvangen vliegtuigen, het aantal berichten per seconde en het maximale bereik gemeten vanaf je antenne.

### Entiteiten

Alles uit `aircraft.json` — het deel dat elke opstelling krijgt:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Vliegtuigen ontvangen | Sensor | Vliegtuigen in de laatste `aircraft.json` |
| Vliegtuigen met positie | Sensor | Daarvan het aantal met een bekende positie |
| Maximaal bereik | Sensor (km) | Afstand tot het verste gehoorde vliegtuig |
| Berichten per seconde | Sensor (msg/s) | Mode S-berichten per seconde, berekend tussen twee metingen |
| Dichtstbijzijnde vliegtuig | Sensor (km) | Afstand tot het dichtstbijzijnde vliegtuig, met callsign, hoogte, snelheid, koers, stijgsnelheid, maatschappij en signaalsterkte als attributen. Een decoder met vliegtuigdatabase voegt registratie, type en een militair-markering toe |
| Hoogste vliegtuig | Sensor (ft) | Hoogte van het hoogste vliegtuig in bereik, met dezelfde attributen |
| Snelste vliegtuig | Sensor (kn) | Grondsnelheid van het snelste vliegtuig in bereik, met dezelfde attributen |
| Vliegtuigen dichtbij | Sensor | Hoeveel vliegtuigen binnen de straal "dichtbij" zitten, met ze allemaal als attributen, dichtstbijzijnde eerst. Dit zijn de twee die [waar de vlucht heen gaat](#waar-een-vlucht-heen-gaat) kunnen dragen |
| Vliegtuig overhead | Binary sensor | Aan zolang er minstens één vliegtuig binnen die straal zit |
| Noodsquawk | Binary sensor (veiligheid) | Aan zolang een vliegtuig in je bereik 7500, 7600 of 7700 squawkt |
| Berichten | Sensor (diagnostisch) | De totale berichtenteller van de ontvanger |
| Ontvanger bijgewerkt | Sensor (diagnostisch) | Het tijdstempel in `aircraft.json` |

Het hoogste en het snelste tellen ook vliegtuigen die nooit een positie uitzenden: hoogte en snelheid komen al via Mode S binnen, en die weglaten zou beide cijfers te laag maken. Hun attribuut `distance` is dan leeg.

Die twee en het maximale bereik houden vast wat ze het laatst zagen in plaats van leeg te lopen zodra de lucht leeg is, en ze overleven een herstart. Een station dat een paar vliegtuigen per uur hoort zou anders het grootste deel van de tijd niets melden. Het attribuut `seen_at` zegt hoe lang geleden dat was, en elk volgt nog steeds de lucht — een lager toestel later vervangt de waarde. Dat is het verschil met de [sectorrecords](#waar-je-antenne-geblokkeerd-zit), die alleen maar groeien.

En, als je ontvanger ook `stats.json` aanbiedt, de gezondheid van je ontvangst:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Signaalniveau | Sensor (dBFS) | Het gemiddelde signaalniveau van de ontvangen berichten |
| Signaal-ruisverhouding | Sensor (dB) | Signaal min ruis; de beste enkele maat voor hoe goed je hoort |
| Ruisniveau | Sensor (dBFS, diagnostisch) | De ruisvloer |
| Piek-signaalniveau | Sensor (dBFS, diagnostisch) | Het sterkste bericht in het venster |
| Te sterke signalen | Sensor (diagnostisch) | Berichten die te luid waren. Structureel boven nul betekent dat je gain te hoog staat |
| Verloren samples | Sensor (diagnostisch) | Samples die de host niet kon bijbenen. Alles boven nul betekent dat je ongemerkt berichten verliest |
| Geaccepteerde berichten | Sensor (diagnostisch) | Geaccepteerde berichten in het venster, opgeteld over alle correctieniveaus |
| Tracks | Sensor (diagnostisch) | Vliegtuigtracks gestart in het venster |
| Tracks met één bericht | Sensor (diagnostisch) | Tracks die nooit een tweede bericht kregen; een hoog aandeel wijst op slechte decodering |
| Demodulatorbelasting | Sensor (%, diagnostisch) | Hoeveel CPU-tijd de decoder aan demoduleren besteedde |
| Gain | Sensor (dB) | De gain waarop de dongle draait. Wordt alleen aangemaakt als de decoder die meldt |
| Foutratio berichten | Sensor (%, diagnostisch) | Aandeel Mode S-berichten dat niet te decoderen was. Onbekend in een minuut zonder verkeer, want dan is er niets om een aandeel van te nemen |
| Vliegtuigen via ADS-B | Sensor | Vliegtuigen die je hun eigen positie hoort uitzenden |
| Vliegtuigen via MLAT | Sensor | Vliegtuigen die via multilateratie bepaald zijn |
| Vliegtuigen via Mode S | Sensor (diagnostisch) | Vliegtuigen die je hoort, maar die nooit een positie geven |
| Frequentieafwijking | Sensor (ppm, diagnostisch) | Hoe ver de klok van je dongle van zijn nominale frequentie af zit |
| Posities gedecodeerd | Sensor (diagnostisch) | Posities die in het venster geaccepteerd zijn |
| Posities verworpen | Sensor (diagnostisch) | Posities die de plausibiliteitscontrole niet haalden. Een stijgend aandeel wijst op een ruizig signaal |

Hoogtes staan in voet, grondsnelheden in knopen en afstanden in kilometers, zoals dat in de luchtvaart gelezen wordt. Elk daarvan heeft een device class, dus je kunt een losse entiteit omzetten naar meters, mijlen, km/h of mph via **Instellingen → Entiteit → Maateenheid**, en historie en statistieken gaan mee.

De ontvangstcijfers komen uit het kortste meetvenster dat daadwerkelijk een signaal gemeten heeft, normaal `last1min`. Uit welk venster een waarde komt, staat als attribuut `period` op de entiteit.

### Feeders

Elke feeder voegt zijn eigen entiteiten toe, op zijn eigen apparaat. Welke je ziet hangt af van de feeder waarvoor die entry is ingericht.

**Flightradar24**, uit de `monitor.json` van `fr24feed`:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Vliegtuigen gevolgd | Sensor | Vliegtuigen die de feeder op dit moment volgt |
| Vliegtuigen gevolgd via ADS-B | Sensor | Daarvan het aantal dat via ADS-B gevolgd wordt |
| Vliegtuigen doorgestuurd | Sensor | Vliegtuigen in de laatste upload naar Flightradar24 |
| Feedstatus | Sensor | De ruwe statustekst van de feed |
| Ontvanger | Binary sensor (verbinding) | Aan zolang `fr24feed` de dongle ziet |
| Feed | Binary sensor (verbinding) | Aan zolang de feed Flightradar24 bereikt |
| MLAT | Binary sensor (verbinding, diagnostisch) | Aan zolang multilateratie werkt |
| Feedmodus | Sensor (diagnostisch) | De huidige feedmodus, bijvoorbeeld MLAT |
| Feed-alias | Sensor (diagnostisch) | Je feeder-ID, bijvoorbeeld T-EHXX23 |
| Kaartgrootte | Sensor (diagnostisch) | De `d11_map_size` van de feeder |
| Herstarts | Sensor (diagnostisch) | Het aantal resets sinds de start |
| Laatst verbonden | Sensor (diagnostisch) | Wanneer de feed voor het laatst verbond |
| CPU-temperatuur | Sensor (diagnostisch) | De SoC-temperatuur van de host. Alleen op de builds voor single board computers |
| Klokafwijking | Sensor (s, diagnostisch) | Hoe ver de klok van de feeder afdreef. Multilateratie heeft dit klein nodig |
| Tijdbron | Sensor (diagnostisch) | Waar de feeder zijn klok mee gelijkzet, bijvoorbeeld NTP |
| Feed-server | Sensor (diagnostisch) | De Flightradar24-server waar deze feeder mee praat |
| Hersynchronisaties | Sensor (diagnostisch) | Hoe vaak de feeder opnieuw moest synchroniseren |

**FlightAware**, uit de `status.json` van PiAware:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Radio | Sensor | Of de decoder gehoord wordt |
| Feed | Sensor | De verbinding met FlightAware |
| MLAT | Sensor | Multilateratie |
| PiAware-dienst | Sensor (diagnostisch) | De feeder zelf |
| CPU-belasting | Sensor (%, diagnostisch) | Belasting van de host |
| Bedrijfstijd | Sensor (u, diagnostisch) | Hoe lang de host draait |
| CPU-temperatuur | Sensor (diagnostisch) | Alleen aangemaakt op een host die er een uitleest |

Die vier zijn groen, amber of rood in plaats van aan of uit, want amber zegt iets wat de andere twee niet kunnen: een feeder die een onstabiele klok meldt draait prima, maar zal nooit multilatereren. De kleur is de state en de zin erachter — *"Local clock source is unstable"* — staat als attribuut `message` op de entiteit.

**Plane Finder**, uit de `/ajax/stats` van `pfclient`:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Berichten per seconde | Sensor (msg/s) | Mode S-pakketten per seconde, zoals pfclient ze telt |
| MLAT | Binary sensor (verbinding) | Aan zolang er multilateratiedata verstuurd wordt |
| Mode S-berichten | Sensor (diagnostisch) | Totaal aantal pakketten sinds de client startte |
| Mode A/C-berichten | Sensor (diagnostisch) | Daarvan de Mode A/C-pakketten |
| CRC-fouten | Sensor (diagnostisch) | Pakketten die hun controlegetal niet haalden |
| Geüpload | Sensor (MB, diagnostisch) | Verstuurd naar Plane Finder |
| MLAT geüpload | Sensor (kB, diagnostisch) | Daarvan het multilateratie-aandeel |
| Datasnelheid ontvanger | Sensor (B/s, diagnostisch) | Wat er van de decoder binnenkomt |

pfclient publiceert zelf geen multilateratie-vlag, maar telt wel wat het verstuurt — en een station waarvan de klok te onstabiel is om te multilatereren verstuurt niets. Die bytesteller is dus de sensor.

Met een feeder worden de feeder en de ontvanger los van elkaar uitgelezen: als de decoder niet meer antwoordt, worden alleen de vliegtuig-entiteiten onbeschikbaar en blijven de feed-entiteiten werken. Zonder feeder is de decoder de enige bron, en neemt een storing alles mee.

#### Waar je antenne geblokkeerd zit

Eén enkel maximumbereik verbergt de vorm van je dekking: 250 km naar het zuiden en 40 km naar het noorden is een heel ander station dan 145 km rondom. Acht sensoren houden per windrichting bij hoe ver een vliegtuig ooit gehoord is, elk over 45 graden gecentreerd op hun richting — **Maximaal bereik noord** dekt dus 337,5° tot 22,5°.

| Entiteit | Type | Omschrijving |
|---|---|---|
| Maximaal bereik noord … noordwest | Sensor (km) | Het record voor die sector, met `recorded_at`, `flight` en `hex` als attributen |
| Bereikrecords wissen | Knop | Wist alle acht |

De records groeien alleen maar, en ze overleven een herstart van Home Assistant — een record dat bij elke herstart opnieuw begint is niets waard. De sensoren blijven ook leesbaar als er niets vliegt, want een record van vorige maand is nog steeds een meting.

Datzelfde groeien maakt ze onjuist zodra je antenne verhuist of de buurman een schuur neerzet; daar is de knop voor. Druk je erop terwijl er toestellen in beeld zijn, dan zet hij meteen nieuwe records vanaf de plek waar je antenne nu staat.

### Welke decoder

Elke decoder levert je de entiteiten hierboven waarvoor hij data heeft; wat hij meldt wordt bij het instellen gedetecteerd, zodat er geen entiteit wordt aangemaakt die nooit een waarde kan hebben. Dat betekent wel dat de decoder die je draait bepaalt hoeveel je krijgt, en **readsb levert het meest**:

| | dump1090-fork van fr24feed | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Vliegtuigen, bereik, berichten per seconde | Ja | Ja | Ja |
| Signaal, ruis, signaal-ruisverhouding | Ja | Ja | Ja |
| Gain | Nee | Ja | Ja |
| Antennepositie in `receiver.json` | Nee | Ja | Ja |
| Registratie, type, omschrijving | Nee | Nee | Ja, met vliegtuigdatabase |
| Militair-markering | Nee | Nee | Ja, met vliegtuigdatabase |

Twee daarvan zijn het benoemen waard. Zonder gain-waarde stem je je dongle blind af, en zonder antennepositie in `receiver.json` wordt het bereik gemeten vanaf de thuislocatie van je Home Assistant-installatie in plaats van vanaf je antenne — prima als dat dezelfde plek is, fout als je ontvanger elders staat.

Draai je nu alleen `fr24feed`, dan kost het vervangen van de meegeleverde dump1090 door readsb je niets en levert het de gain-sensor, de vliegtuigdetails en een echte antennepositie op. **Draai Herconfigureren na een decoder-upgrade** om op te pikken wat hij nu kan.

#### De vliegtuigdatabase

De laatste twee rijen vragen één extra stap. readsb vult `r`, `t`, `desc` en `dbFlags` alleen als hij een vliegtuigdatabase heeft; zonder database meldt de sensor voor het dichtstbijzijnde vliegtuig wel een hex-code en een callsign, maar geen registratie, type of militair-markering.

Haal op een readsb-installatie de database op en wijs readsb ernaar:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Voeg daarna de optie toe aan `/etc/default/readsb`, bij de argumenten waarmee readsb start:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Herstart readsb en de extra velden staan meteen in `aircraft.json`. De integratie pikt ze vanzelf op — de attributen verschijnen zodra de decoder ze stuurt, dus je hoeft niets te herconfigureren. De database is een momentopname, dus ververs hem af en toe door hetzelfde commando opnieuw te draaien.

#### Namen bij de codes

Een vliegtuig zendt `DLH6CH` en `A20N` uit. Geen van beide is een naam, en geen decoder kan er een van maken, want die namen zitten niet in het radiosignaal — het is een lijst die iemand bijhoudt. Die lijst wordt met de integratie meegeleverd, dus de vliegtuigattributen dragen een naam zonder dat er iets over internet gevraagd wordt:

| Attribuut | Afgeleid uit | Voorbeeld |
|---|---|---|
| `airline` | De eerste drie letters van de callsign | `DLH6CH` → `Lufthansa` |
| `description` | De ICAO-typecode, als de decoder hem zelf niet omschrijft | `A20N` → `Airbus A-320neo` |

Een callsign die geen vluchtnummer is levert geen maatschappij op. Zakenjets, zweefvliegtuigen en de meeste kleine luchtvaart vliegen onder hun registratie, dus `PHABC` blijft met rust gelaten in plaats van gelezen te worden als een maatschappijcode en te veranderen in wat `PHA` toevallig is.

Een typecode staat voor een familie en niet voor één vliegtuig: een A20N is een A320neo maar ook de zakenversie ervan, en een BE20 is elk van een stuk of tien King Airs plus hun militaire neven. Niets in de gegevens zegt welke je het vaakst boven je hoofd krijgt, dus de naam is degene die de code zelf spelt. Dat klopt voor de lijnvliegtuigen en kan bij de kleine luchtvaart op een vreemde variant uitkomen.

Beide tabellen komen uit de [standing data van Virtual Radar Server](https://github.com/vradarserver/standing-data), die publiek domein is onder CC0-1.0. Net als de vliegtuigdatabase hierboven zijn het momentopnames; `scripts/build_reference.py` maakt ze opnieuw aan vanuit de bron.

### Installatie

Vereist Home Assistant 2026.3 of nieuwer.

#### Via HACS

1. Open HACS in Home Assistant.
2. Kies **⋮ → Aangepaste repositories** en voeg `https://github.com/mirkin-pixel/ha-adsb-station` toe als **Integratie**.
3. Zoek naar **ADS-B Station** en klik op **Download**.
4. Herstart Home Assistant.

#### Handmatig

1. Kopieer de map `custom_components/adsb_station` naar de map `custom_components` van je Home Assistant-configuratie.
2. Herstart Home Assistant.

### Configuratie

1. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen**.
2. Zoek naar **ADS-B Station**.
3. Kies waar deze entry voor is:
   - **Flightradar24-feeder (fr24feed)** — het adres van de machine waarop hij draait, en de poort van de statuspagina, standaard `8754`.
   - **FlightAware-feeder (PiAware)** — idem, standaard poort `8080`. Staat er een andere webserver op die poort, dan kan `status.json` elders staan; op een station met tar1090 achter nginx is poort 80 het proberen waard.
   - **Plane Finder-feeder (pfclient)** — idem, standaard poort `30053`.
   - **Alleen een ADS-B-ontvanger** — voor een station dat nergens aan voedt, of als de entry die de decoder draagt.
4. Elk pad biedt daarna de ontvanger aan. Koppel die aan één entry en laat hem bij de andere leeg, anders tellen de vliegtuigcijfers dubbel.

Deze paden worden automatisch geprobeerd, op poort 8080 waar fr24feed en PiAware ze aanbieden en op poort 80 waar readsb met tar1090 dat doet:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

Alle kandidaten worden tegelijk geprobeerd, en de eerste in die volgorde die antwoordt wint. Staat die van jou elders, vul dan zelf de volledige URL in.

Er staan drie instellingen onder **Configureren** op de integratiepagina. De ververstijd is standaard 15 seconden; alles draait op je eigen netwerk, dus een korte tijd kan prima. De straal "dichtbij" is standaard 10 km en bepaalt wat als overhead telt voor de entiteiten **Vliegtuigen dichtbij** en **Vliegtuig overhead** — tien kilometer is ongeveer wat je kunt zien en horen, terwijl een goede ontvanger een veelvoud daarvan haalt. De derde is [waar een vlucht heen gaat](#waar-een-vlucht-heen-gaat), en die staat uit. Station verhuisd naar een ander adres? Gebruik **Herconfigureren** in plaats van hem opnieuw toe te voegen.

Wil je een feeder toevoegen aan een station dat je als alleen-ontvanger hebt ingericht, voeg dan een tweede entry toe — precies wat je later ook doet om een tweede of derde netwerk erbij te zetten.

### Waar een vlucht heen gaat

Je antenne hoort dit nooit. Een vliegtuig zendt een callsign uit — `KLM1234` — en verder niets over de vlucht erachter, dus waar het opgestegen is en waar het heen gaat staat niet in `aircraft.json` en kan daar ook niet staan. Elke kaart die je een route laat zien, tar1090 incluis, vraagt het aan een database op de grond. Daarmee is dit het enige gegeven dat deze integratie niet op je eigen netwerk kan ophalen, en daarom staat **Vluchtroutes opzoeken** onder **Configureren** uit tot je hem aanzet.

De bron is **routeset**, via `adsb.im`, en dat is dezelfde bron die tar1090 zelf gebruikt. Hij vraagt niet om een account of een sleutel, hij neemt alle callsigns van één meting in één verzoek, en hij krijgt van elk vliegtuig de positie mee waar het gehoord is.

Dat laatste is waarom hij te vertrouwen is, en meteen de reden dat het de enige bron hier is. Een moderne callsign van een maatschappij wordt over de benen van een dag hergebruikt, dus een database die alleen op het vluchtnummer antwoordt geeft het been terug dat hij toevallig heeft staan — en dat is ongeveer even vaak wel als niet het been dat het toestel net gevlogen heeft. routeset krijgt te horen waar het vliegtuig is en laat een route vallen die daar niet bij past.

Dat verschil is niet klein. Getoetst aan de koers die de toestellen zelf uitzonden, over drie steekproeven van zo'n 160 vliegtuigen boven Nederland:

| | routeset | Een bron die per vluchtnummer antwoordt |
|---|---|---|
| Beantwoorde callsigns | 96% | 88% |
| Antwoorden die wijzen waar het toestel echt heen ging | **99%** | 73% |
| Antwoorden die de omgekeerde kant op wijzen | 1% | **15%** |
| Verzoeken voor 160 vliegtuigen | 1 | 142 |

Eén op de zeven is een melding dat het toestel boven je hoofd op weg is naar het vliegveld waar het een uur geleden vertrok, en een verkeerde route is erger dan geen route.

Alleen de vliegtuigen binnen je straal "dichtbij" worden opgezocht. Dat is het handjevol waar een automatisering iets mee doet, en vragen naar elk vliegtuig in bereik zou een stroom verzoeken aan andermans server zijn voor een gegeven dat nergens getoond wordt. Antwoorden worden twaalf uur bewaard, zodat de lijnvluchten die er dagelijks overkomen één keer opgezocht worden in plaats van elke poll, en er worden nooit meer dan 25 nieuwe callsigns per poll opgezocht.

Wordt er een route gevonden, dan verschijnt die bij elk vliegtuig in de attributen van **Vliegtuigen dichtbij** en **Vliegtuig overhead**:

| Attribuut | Voorbeeld |
|---|---|
| `route` | `CDG-AMS` |
| `origin`, `destination` | `CDG`, `AMS` |
| `origin_location`, `destination_location` | `Paris`, `Amsterdam` |
| `origin_name`, `destination_name` | `Charles de Gaulle International Airport` |

De maatschappij staat er niet bij, en dat hoeft ook niet: die is er [hoe dan ook al](#namen-bij-de-codes).

Attributen die niet bekend zijn worden weggelaten in plaats van leeg gelaten, zodat een template kan vragen of de sleutel er überhaupt is. Privé, militair en een flink deel van het vrachtverkeer levert niets op, en een bron die onbereikbaar is betekent simpelweg geen route die poll — de vliegtuigentiteiten zelf hangen er nooit van af.

Een vliegtuig dat geen positie uitzendt krijgt ook geen route, want de bron toetst elke route die hij vindt aan waar het toestel is. In de praktijk kost dat niets: alleen de vliegtuigen die dichtbij genoeg zijn worden opgezocht, en dichtbij genoeg wordt vanaf een positie gemeten.

### Voorbeeldautomatiseringen

Melding wanneer een vliegtuig in je bereik een noodsituatie meldt:

```yaml
automation:
  - alias: "ADS-B: noodsquawk"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_noodsquawk
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            Noodsquawk van
            {{ state_attr('binary_sensor.ads_b_station_noodsquawk',
                          'aircraft')[0].flight or 'een onbekend vliegtuig' }}.
```

Melding wanneer er iets overkomt, met wat het is en waar het heen gaat:

```yaml
automation:
  - alias: "ADS-B: vliegtuig overhead"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_vliegtuig_overhead
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {% set plane = state_attr(
                 'binary_sensor.ads_b_station_vliegtuig_overhead',
                 'aircraft')[0] %}
            {{ plane.airline | default(plane.flight or 'Een onbekend vliegtuig') }}
            overhead op {{ plane.altitude }} ft
            {%- if plane.description is defined %},
            een {{ plane.description }}
            {%- endif %}
            {%- if plane.vertical_rate %},
            {{ 'stijgend' if plane.vertical_rate > 0 else 'dalend' }} met
            {{ plane.vertical_rate | abs }} ft/min
            {%- endif %}
            {%- if plane.origin_location is defined %},
            {{ plane.origin_location }} naar {{ plane.destination_location }}
            {%- endif %}.
```

Wat er zo uitkomt: *"Lufthansa overhead op 4100 ft, een Airbus A-320neo, dalend met 1088 ft/min, Parijs naar Amsterdam."*

Alle vier zijn sleutels die kunnen ontbreken, elk om een eigen reden, en daarom vraagt de template ernaar in plaats van ze te lezen. De maatschappij en de typenaam staan er voor de vluchten die de [meegeleverde tabellen](#namen-bij-de-codes) herkennen, dus een zakenjet onder zijn registratie valt terug op de callsign. De stijgsnelheid ontbreekt bij vliegtuigen aan de grond en is nul in horizontale vlucht, waar niets zeggen beter is dan "stijgend met 0". De route heeft een [bron nodig](#waar-een-vlucht-heen-gaat) en staat er alleen bij voor de vluchten die hij kent.

Je beste bereik van de dag bijhouden:

```yaml
sensor:
  - platform: statistics
    name: "ADS-B bereik vandaag"
    entity_id: sensor.ads_b_station_maximaal_bereik
    state_characteristic: value_max
    max_age:
      hours: 24
```

Melding wanneer de Flightradar24-feed wegvalt, voor een station dat `fr24feed` draait:

```yaml
automation:
  - alias: "FR24: feed offline"
    trigger:
      - platform: state
        entity_id: binary_sensor.t_ehxx23_feed
        to: "off"
        for: "00:05:00"
    action:
      - service: notify.mobile_app
        data:
          message: "De Flightradar24-feed is al 5 minuten offline."
```

De entity-ID's hierboven volgen de apparaatnaam: `ads_b_station` voor een station zonder feeder, je feed-alias voor een station met. Die apparaatnaam wordt niet vertaald, de entiteitsnaam erachter wel — noem je het apparaat in Home Assistant anders, dan veranderen de entity-ID's mee.

### Over de endpoints

Alle endpoints zijn gewone HTTP-adressen zonder authenticatie op je lokale netwerk:

- `http://<host>:8080/<pad>/aircraft.json` — de vliegtuiglijst van je decoder.
- `<pad>/stats.json` en `<pad>/receiver.json` — worden automatisch naast `aircraft.json` gevonden.
- `http://<host>:8754/monitor.json` — de statuspagina van `fr24feed`.
- `http://<host>:8080/status.json` — de statuspagina van PiAware.
- `http://<host>:30053/ajax/stats` — de statistieken van `pfclient`.

Die laatste drie worden alleen gelezen door de entry die voor die feeder is ingericht.

Verder wordt er niets benaderd tenzij je erom vraagt. De enige uitzondering is [een route opzoeken](#waar-een-vlucht-heen-gaat), wat via HTTPS `adsb.im` aanspreekt en niets meegeeft behalve een callsign en de positie waar hij gehoord is. Laat je die instelling uit, dan verlaat de integratie je netwerk nooit.

De integratie leest ze alleen uit en schrijft nooit. Afstanden worden gemeten vanaf de antennepositie in `receiver.json`; publiceert de decoder die niet, dan wordt de thuislocatie van je Home Assistant-installatie gebruikt, dus zorg dat die locatie klopt.

Veldnamen verschillen per decoder. De fr24feed-fork meldt `altitude` en `speed` waar dump1090-fa en readsb `alt_baro` en `gs` melden; de integratie begrijpt beide. Het aantal berichten per seconde komt uit twee opeenvolgende metingen; na een herstart van de ontvanger wordt de eerste waarde overgeslagen omdat de teller dan opnieuw begint.

### Problemen oplossen

Blijven entiteiten op `unknown` of `unavailable` staan? Verzamel dan de twee onderstaande zaken en voeg ze toe aan een [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Debug-logging aanzetten.** Ga naar **Instellingen → Apparaten & diensten → ADS-B Station**, klik op de drie puntjes en kies **Debug-logging aanzetten**. Reproduceer het probleem en kies daarna **Debug-logging uitzetten** — Home Assistant downloadt de log dan automatisch.

Wil je ook over een herstart heen loggen, zet dan dit in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.adsb_station: debug
```

In de debug-log zie je de HTTP-status van elke poll en elke waarde die de integratie niet kon verwerken.

**Diagnostiek downloaden.** Kies op dezelfde pagina **Diagnostische gegevens downloaden**. Het bestand bevat de configuratie en de laatste meting, met het adres van je ontvanger en je feed-alias weggehaald.

### Ontwikkeling

Werken aan de integratie zelf staat in [CONTRIBUTING.md](CONTRIBUTING.md) (Engels): hoe je het opzet, de drie controles die alles zijn wat CI je over de code kan vertellen, hoe de code is ingedeeld en hoe een release eruit gaat. Je hebt Python 3.14 of nieuwer nodig en verder niets — geen eigen Home Assistant-installatie.

```bash
pip install -r requirements_test.txt
scripts/check.sh          # of scripts\check.ps1
```

### Disclaimer

Dit is een onofficiële integratie en is niet gelieerd aan Flightradar24, FlightAware of Plane Finder. Gebruik op eigen risico.
