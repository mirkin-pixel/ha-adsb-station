# ADS-B Station for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/mirkin-pixel/ha-adsb-station?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)

[English](#english) | [Nederlands](#nederlands)

---

## English

Custom integration for [Home Assistant](https://www.home-assistant.io/) that reads **your own ADS-B receiver**. Everything happens on your own network: the integration polls the `aircraft.json` of your decoder and, if you run one, the `monitor.json` status page of `fr24feed` next to it. There is one exception, it is off unless you turn it on, and it has a section of its own: [where a flight is going](#where-a-flight-is-going) is the one thing your antenna cannot hear.

It is not tied to a single network. Anything that serves an `aircraft.json` works, so it does not matter whether you feed Flightradar24, FlightAware, Plane Finder, several of them at once, or nothing at all:

| Decoder | What you get |
|---|---|
| readsb or tar1090 | Every receiver entity, and the most of them; see [Which decoder](#which-decoder) |
| dump1090-fa or SkyAware | Every receiver entity |
| dump1090, dump1090-mutability | The receiver entities its build reports |
| The dump1090 fork bundled with fr24feed | The receiver entities that fork reports |

On top of the decoder it reads the feeders themselves, each of which serves a status page of its own on your network:

| Feeder | Network | Status page |
|---|---|---|
| `fr24feed` | Flightradar24 | `:8754/monitor.json` |
| PiAware | FlightAware | `:8080/status.json` |
| `pfclient` | Plane Finder | `:30053/ajax/stats` |

A station commonly feeds several networks off one decoder, and that is how this is meant to be set up: **one entry per feeder**, each its own device, with the decoder attached to just one of them. The aircraft figures then exist once and every network has its own feed status. A station that feeds nowhere at all works too: set up the receiver on its own.

What you get is a proper device with translated entity names and a config flow, and figures that are awkward to arrive at by hand: the number of aircraft received, the message rate, and the maximum range measured from your antenna.

### Entities

Everything from `aircraft.json`, the part every setup gets:

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
| Overhead flight | Sensor | The one aircraft above you, nearest first and measured through the air. Keeps the last one when the sky empties, so a panel built on it never goes blank. See [when something comes over](#when-something-comes-over) |
| Passages today | Sensor | How many aircraft came over today, with the last twenty of them as attributes, most recent first |
| Emergency squawk | Binary sensor (safety) | On while an aircraft in range squawks 7500, 7600 or 7700 |
| Messages | Sensor (diagnostic) | The total message counter of the receiver |
| Receiver updated | Sensor (diagnostic) | The timestamp inside `aircraft.json` |

The highest and the fastest also count aircraft that never broadcast a position: altitude and speed reach us from Mode S alone, and leaving those out would understate both. Their `distance` attribute is then empty.

"In the last `aircraft.json`" is what the decoder is holding, which is a little more than what is transmitting this second: it keeps an aircraft for about a minute after its last message. That is deliberate, and it is what makes the count agree with the map your decoder serves. The `seen` attribute on each aircraft says how many seconds ago it was last heard.

A position has to be possible before it is believed. ADS-B is line of sight, so an aircraft at 37,000 feet can be heard from roughly 440 km and one at 2,000 feet from roughly 100 km, and this allows 80 km on top of that for an antenna standing high. A position beyond that was mis-decoded rather than received, and is dropped: it would otherwise put an aircraft overhead that was never there, or leave a [sector record](#where-your-antenna-is-blocked) that stands for good. The aircraft still counts as received, because it is real; it just counts as one whose position is unknown.

Those two and the maximum range keep what they last saw rather than blanking when the sky empties, and they survive a restart. A station that hears a couple of aircraft an hour would otherwise report nothing most of the time. The `seen_at` attribute says how long ago it was, and each still follows the sky: a lower aircraft later replaces the reading. That is what separates them from the [sector records](#where-your-antenna-is-blocked), which only ever grow.

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

Those four are green, amber or red rather than on or off, because amber says something neither of the other two can: a feeder reporting an unstable clock is running fine but will never multilaterate. The colour is the state, and the sentence behind it, *"Local clock source is unstable"*, is on the entity as a `message` attribute.

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

pfclient publishes no multilateration flag of its own, but it does count what it has sent, and a station whose clock is too unstable to multilaterate sends nothing at all, so the byte counter is the sensor.

With a feeder, the feeder and the receiver are read independently: if the decoder stops answering, only the aircraft entities become unavailable and the feed entities keep working. Without a feeder the decoder is the only source, so an outage takes everything with it.

#### Where your antenna is blocked

A single maximum range figure hides the shape of your coverage: 250 km to the south and 40 km to the north is a very different station from 145 km all round. Eight sensors keep the furthest an aircraft has ever been heard in each compass sector, spanning 45 degrees centred on their direction, so **Range record north** covers 337.5° to 22.5°.

| Entity | Type | Description |
|---|---|---|
| Range record north … northwest | Sensor (km) | The record for that sector, with `recorded_at`, `flight` and `hex` as attributes |
| Reset range records | Button | Clears all eight |

These are the records; **Maximum range** above is the live figure. It is named for what the hobby calls it and for what your feeder sites report, and it follows the sky: a poll with nothing further away than 40 km puts it at 40 km. These eight only ever go up.

The records only ever grow, and they survive a restart of Home Assistant, because a record that started over every restart would be worth nothing. The sensors also stay readable when nothing is flying, because a record from last month is still a reading.

That same growth makes them wrong the moment the antenna moves or a neighbour puts up a shed, which is what the button is for. Pressing it while aircraft are in view immediately sets fresh records from them, measured from where the antenna is now.

### Which decoder

Every decoder gives you the entities above that it has data for; what it reports is detected when you set it up, so no entity is created that could never have a value. That does mean the decoder you run decides how much you get, and **readsb gives you the most**:

| | fr24feed's dump1090 fork | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Aircraft, range, message rate | Yes | Yes | Yes |
| Signal, noise, signal-to-noise | Yes | Yes | Yes |
| Gain | No | Yes | Yes |
| Antenna position in `receiver.json` | No | Yes | Yes |
| Emitter category, and how the aircraft was heard | No | Yes | Yes |
| Registration, type, description | No | No | Yes, with an aircraft database |
| Interesting, PIA and LADD markers | No | No | Yes, with an aircraft database |

Two of those are worth spelling out. Without a gain figure you are tuning your dongle blind, and without an antenna position in `receiver.json` the range is measured from the home location of your Home Assistant installation instead of from your antenna, which is fine if they are the same place and wrong if your receiver sits elsewhere.

If you already run `fr24feed` and nothing else, replacing its bundled dump1090 with readsb costs you nothing and adds the gain sensor, the aircraft details and a real antenna position. **Run Reconfigure after upgrading your decoder** to pick up what it can do now.

#### The aircraft database

The last two rows need one extra step. readsb only fills in `r`, `t`, `desc` and `dbFlags` when it has been given an aircraft database, and without one the closest aircraft sensor reports a hex code and a callsign but no registration and no type. The military marker is the exception: without a database it is worked out from the address instead, which [the table below](#names-for-the-codes) explains.

On a readsb install, fetch the database and point readsb at it:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Then add the option to `/etc/default/readsb`, in the arguments readsb is started with:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Restart readsb, and the extra fields appear in `aircraft.json` straight away. The integration picks them up on its own: the attributes are added as soon as the decoder sends them, so there is nothing to reconfigure. The database is a snapshot, so refresh it now and then by running the same command again.

#### What else the decoder says

Five more attributes ride along with an aircraft, and like the ones above they are only there when the decoder sends them:

| Attribute | What it says |
|---|---|
| `category` | The emitter category the aircraft broadcasts, `A0` to `D7`. `A7` is a helicopter and `B6` a drone, and this is the only place either of them says so |
| `heard_as` | How the decoder came to know about it: `adsb_icao` heard straight off the aircraft, `mlat` worked out from the timing at several receivers, `mode_s` a bare reply with no position in it at all |
| `interesting` | The aircraft database marks this one as worth a look |
| `pia` | A Privacy ICAO Address: a temporary hex code an operator flies under to stay off the lists |
| `ladd` | The American request to limit where the aircraft is displayed |

`category` comes over the air, so it is there without an aircraft database; the last three are the remaining bits of the same `dbFlags` the military marker is bit 0 of. All three are passed on rather than acted on. An aircraft your receiver heard is one it heard, and whether a dashboard leaves a PIA or LADD flight out is yours to decide, not this integration's.

#### Names for the codes

An aircraft broadcasts `DLH6CH`, `A20N` and `484123`. None of the three is a name, and no decoder can make one of them, because the names are not in the radio signal at all: they are a list somebody keeps. The integration ships those lists, so the aircraft attributes carry a name without anything being asked over the internet:

| Attribute | Read from | Example |
|---|---|---|
| `airline` | The first three letters of the callsign | `DLH6CH` → `Lufthansa` |
| `airline_code` | Those same three letters, whether or not the table names them | `DLH6CH` → `DLH` |
| `description` | The ICAO type code, where the decoder does not describe it itself | `A20N` → `Airbus A-320neo` |
| `country` | The 24 bit address itself, which ICAO handed out in ranges per country | `484123` → `AW` |

A callsign that is not a flight number names no airline. Business jets, gliders and most light aircraft fly under their registration, so `PHABC` is left alone rather than read as an airline code and turned into whatever `PHA` happens to be.

`airline_code` is there even for an airline the table has never heard of, because the aircraft broadcast it and a dashboard looks a logo up by it. `airline` is only there when the table can put a name to it.

A type code covers a family rather than a single aircraft: an A20N is an A320neo but also the corporate version of it, and a BE20 is any of a dozen King Airs and their military cousins. Nothing in the data says which one you are most likely to see, so the name is the one the code itself spells out. That is right for the airliners and can land on an odd variant for general aviation.

`country` is where an aircraft is registered and not where it is: a KLM aircraft over Spain is still `NL`. Not every address falls in a range — some were never handed out, some belong to no single state, and readsb marks an address it worked out rather than heard with a `~` — and an aircraft in one of those carries no country at all rather than a guess.

That same table says which ranges a country keeps for its own military, which is where the **military marker** comes from when the decoder has no aircraft database. It is the coarser of the two answers: it knows the range and not the aircraft, so a civil aircraft flying inside a military range would be marked along with the rest. So a decoder that does have a database has the last word, in both directions. If `dbFlags` says an aircraft is civil, it is civil, even inside a military range; the address is only asked when nothing else can answer.

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
   - **Flightradar24 feeder (fr24feed)**: the address of the machine running it, and the port of its status page, `8754` by default.
   - **FlightAware feeder (PiAware)**: likewise, port `8080` by default. A station whose web server was taken over by something else may serve `status.json` elsewhere; on one running tar1090 behind nginx it is worth trying port 80.
   - **Plane Finder feeder (pfclient)**: likewise, port `30053` by default.
   - **ADS-B receiver only**: for a station that feeds nowhere, or as the entry that carries the decoder.
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

Four settings live under **Configure** on the integration page. The update interval is 15 seconds by default; everything runs on your own network, so a short interval is fine. The nearby radius is 10 km by default and decides what counts as overhead for the **Aircraft nearby** and **Aircraft overhead** entities; ten kilometres is roughly what you can see and hear, while a good receiver reaches many times that. The other two are [aircraft on the map](#aircraft-on-the-map) and [where a flight is going](#where-a-flight-is-going), and both are off. Moved your station to a different address? Use **Reconfigure** instead of adding it again.

Adding a feeder to a station you set up as receiver-only means adding it as a second entry, which is the same thing you do to add a second or third network later.

### Where a flight is going

Your antenna never hears this. An aircraft broadcasts a callsign, `KLM1234`, and nothing about the flight behind it, so where it took off and where it is heading is not in `aircraft.json` and cannot be. Every map that shows you a route, tar1090 included, asks a database on the ground. That makes it the one figure this integration cannot get on your own network, which is why **Look up flight routes** under **Configure** is off until you switch it on.

The source is **routeset**, reached through `adsb.im`, which is what tar1090 itself uses. It asks for no account and no key, and it takes every callsign of a poll in one request.

It is also told where each aircraft was heard, which is what lets it judge. A modern airline callsign is reused across the legs of a day, so knowing the flight number is not the same as knowing where that aircraft is going; routeset drops a route that does not fit the position rather than showing it, because a wrong route in a notification is worse than none.

Only the aircraft inside your nearby radius are ever looked up. Those are the handful an automation acts on, and asking about every aircraft in range would be a stream of requests to someone else's server for a figure nothing displays. Answers are kept for twelve hours, so the airliners that pass over every day are asked about once rather than once per poll, and no more than 25 new callsigns are looked up per poll.

When a route is found it appears on each aircraft in the **Aircraft nearby** and **Aircraft overhead** attributes:

| Attribute | Example |
|---|---|
| `route` | `CDG-AMS` |
| `origin`, `destination` | `CDG`, `AMS` |
| `origin_location`, `destination_location` | `Paris`, `Amsterdam` |
| `origin_name`, `destination_name` | `Charles de Gaulle International Airport` |

The airline is not among them, and does not need to be: it is [there either way](#names-for-the-codes).

Attributes that are not known are left out rather than left empty, so a template can ask whether the key is there at all. Private, military and a good deal of cargo traffic resolves to nothing, and the source being unreachable simply means no route that poll; the aircraft entities themselves never depend on it.

An aircraft that broadcasts no position gets no route either, because the source judges every route it finds against where the aircraft is. In practice nothing is lost: only the aircraft near enough to be looked up are asked about, and being near enough is measured from a position.

### Aircraft on the map

Switch **Aircraft on the map** on under **Configure** and every aircraft inside the nearby radius gets an entity of its own, drawn where it is, for as long as it is there. Nothing extra is read to do it: the positions are in every poll already, next to the distances the proximity sensors are built on.

A map card shows them all:

```yaml
type: map
geo_location_sources:
  - adsb_station
hours_to_show: 0
```

`hours_to_show: 0` is worth having. Anything higher draws a trail from the recorder, and these entities are not kept there.

That is the trade this option makes, and it is worth understanding before you turn it on. **These aircraft are deliberately not registered.** They exist while they are overhead and are gone the moment they fly on, so a week of traffic leaves nothing behind — no thousands of entities in your registry, no `unavailable` aircraft coming back after every restart, nothing to clean up. In exchange they cannot be renamed, hidden or given an area from the interface, they are not listed under the station's device, and their attributes are kept out of the recorder. Their entity IDs are reused, too: `geo_location.klm123` next week is a different flight under the same name. For history there is the passage board and the [passage event](#when-something-comes-over), which are built to be kept.

Each aircraft is named after its callsign, or its hex code when it has not sent one yet, and that name is fixed the moment it appears. A callsign often arrives a few polls late, and renaming then would move the entity ID out from under your dashboard halfway through a passage.

How many there are is whatever your radius holds — usually nought to a handful at the default ten kilometres. If you set a wide radius and would rather your database not see them at all, exclude them wholesale:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```

### When something comes over

**Aircraft overhead** answers one question, and it answers it well: is there anything up there. It cannot tell you that a second aircraft has arrived while the first is still in view, because nothing changed. It was on, and it stays on.

So an aircraft crossing the sky above you fires an event of its own, once, the moment it arrives:

```yaml
automation:
  - alias: "ADS-B: something went over"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {{ trigger.event.data.airline | default('An unknown aircraft') }}
            at {{ trigger.event.data.slant_distance }} km
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}
            {%- endif %}.
```

The event carries the same keys as the aircraft attributes, so everything in the notification above is there: `flight`, `airline`, `description`, `altitude`, `vertical_rate`, the route if you look them up, and `entry_id` and `station` to tell one station from another. It adds one key of its own, `slant_distance`, which is the subject of the next paragraph.

Three things stop it becoming a nuisance.

**The distance counts the height.** Every other distance in this integration is measured across the ground, which is the right answer for how far your antenna reaches and the wrong one for what is above you. An airliner at 37,000 feet passing nine kilometres to the north is inside a ten kilometre radius on the map, and is fourteen kilometres away from you in the sky. It counts as nearby, as it should, and it is not a passage, as it should not be. The `distance` in the event is still the one across the ground; `slant_distance` is the real one.

**An aircraft has to leave before it can arrive again.** Reception drops out, aircraft circle, and one on the edge of the radius flickers in and out. An aircraft that goes and comes back inside ten minutes is the same passage; longer than that and it is a new one. So a helicopter working a field nearby rings once, not once a minute.

**An aircraft has to be flying.** One on the ground reports no altitude, so the distance through the air falls back to the distance across the ground and a taxiing airliner would look exactly like a low pass. If you live near a field that is most of your traffic, so it is left out. It still shows up under **Aircraft nearby**, marked `on_ground`, because it really is an aircraft within your radius.

#### A notification that reads like a panel

The event carries enough to put the whole panel in a notification, and the companion app takes an image with it. Keep the message a literal block, `|-` rather than `>-`, or the lines fold into one sentence:

```yaml
automation:
  - alias: "ADS-B: passage as a panel"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: >-
            {{ trigger.event.data.airline
               | default(trigger.event.data.flight) | default('Unknown aircraft') }}
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Alt {{ trigger.event.data.altitude or '?' }}ft, Spd {{ trigger.event.data.speed | round | int if trigger.event.data.speed else '?' }}kn
            Trk {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Vr {{ trigger.event.data.vertical_rate or 0 }}ft/min
          data:
            subtitle: >-
              {{ trigger.event.data.route
                 | default(trigger.event.data.slant_distance ~ ' km') }}
            tag: adsb-passage
            group: adsb
            image: >-
              /local/airline_logos/{{ trigger.event.data.airline_code
                 | default('unknown') }}.png
```

Which reads as this, and as the right-hand column for something that broadcasts almost nothing:

```
Lufthansa                    PHABC
CDG-AMS                      1.1 km
Airbus A-320neo
Alt 4100ft, Spd 250kn        Alt 2000ft, Spd ?kn
Trk 263deg, Vr -1088ft/min   Trk 90deg, Vr 0ft/min
```

For metres and kilometres per hour, only the message changes, with the same factors as [the cards](#the-panel-and-the-board):

```yaml
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Alt {{ (trigger.event.data.altitude * 0.3048) | round | int }}m, Spd {{ (trigger.event.data.speed * 1.852) | round | int if trigger.event.data.speed else '?' }}km/h
            Trk {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Vr {{ (trigger.event.data.vertical_rate | default(0) * 0.00508) | round(1) }}m/s
```

Which reads as this, with a real flight through it:

```
Delta Air Lines
FRA-JFK
Airbus A-330-200
Alt 8702m, Spd 891km/h
Trk 290deg, Vr 2.9m/s
```

The logo is yours to supply: the app takes a `/local/` path into your `www` folder, so `www/airline_logos/DLH.png` and one `unknown.png` beside it covers every aircraft. Airline logos are trademarks and are not something this integration can ship for you. Give every notification the same `tag` and each aircraft replaces the one before it rather than filling your screen; leave the `tag` out and keep the `group` to see them all.

#### The panel and the board

Two sensors read those passages, and between them they are a departure board for your own roof.

**Overhead flight** is the aircraft above you right now, the nearest one measured through the air, with everything about it as attributes: `airline`, `description`, `altitude`, `speed`, `track`, `vertical_rate`, `slant_distance`, the route if you look them up, and `since`, which is when it arrived. It keeps the last aircraft rather than blanking when the sky empties, because a panel that goes empty between aircraft is not worth looking at. The `overhead` attribute says which of the two you are looking at, and `seen_at` says when it was read.

That is enough for a panel, with nothing but a markdown card:

```yaml
type: markdown
content: |
  {% set plane = states.sensor.ads_b_station_overhead_flight %}
  ## {{ plane.attributes.airline | default(plane.state) }}
  {% if plane.attributes.route is defined %}### {{ plane.attributes.route }}{% endif %}
  {{ plane.attributes.description | default(plane.attributes.aircraft_type) | default('') }}

  `Alt {{ plane.attributes.altitude }}ft  Spd {{ plane.attributes.speed }}kn`
  `Trk {{ plane.attributes.track | round | int }}deg  Vr {{ plane.attributes.vertical_rate or 0 }}ft/min`

  {% if not plane.attributes.overhead %}*Last seen {{ relative_time(plane.last_changed) }} ago*{% endif %}
```

Altitudes are in feet and speeds in knots there, because that is what the aircraft broadcast and how aviation reads them. The entities themselves can be switched to metres and kilometres per hour one by one under **Settings → Entity → Unit of measurement**, but attributes are never converted by Home Assistant, so a card that wants metric does the sum itself:

```jinja
  `Alt {{ (plane.attributes.altitude * 0.3048) | round | int }}m  Spd {{ (plane.attributes.speed * 1.852) | round | int }}km/h`
  `Trk {{ plane.attributes.track | round | int }}deg  Vr {{ (plane.attributes.vertical_rate * 0.00508) | round(1) }}m/s`
```

| From | To | Multiply by |
|---|---|---|
| ft | m | 0.3048 |
| kn | km/h | 1.852 |
| ft/min | m/s | 0.00508 |

`distance` and `slant_distance` are in kilometres already.

**Passages today** is the tally, and the last twenty of them are on it as attributes: the time they arrived, the callsign, the airline, the type, how high and how close they came. Both survive a restart of Home Assistant, so the board is a record rather than a session.

Each entry holds the aircraft at its closest approach rather than at its arrival, because an aircraft is first seen at the edge of the radius and is worth looking up at when it is overhead. It appears on the board as soon as it arrives and is rewritten while it is still in view, so the board is current and ends up correct.

```yaml
type: markdown
content: |
  {% for plane in state_attr('sensor.ads_b_station_passages_today', 'passages') %}
  `{{ as_timestamp(plane.at) | timestamp_custom('%H:%M') }}` **{{ plane.airline | default(plane.flight) | default('?') }}**
  {{ plane.route | default('') }} {{ plane.description | default('') }} · {{ plane.distance }} km
  {% endfor %}
```

One thing to know before you leave that running: twenty entries are written to the database every time an aircraft comes over. On a busy station that is worth keeping out of the recorder, which costs you nothing but the history of a board you read live anyway:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ads_b_station_passages_today
```

#### On your lock screen

The companion app can put a passage on your lock screen and in the Dynamic Island as a [Live Activity](https://companion.home-assistant.io/docs/notifications/live-activities/), which is the closest thing to a flight wall you can carry around.

**This only works on the TestFlight build of the companion app, with Live Activities switched on under Labs**, and it needs Home Assistant 2026.7 or newer. It is not in the App Store release, so treat it as something to try rather than something to build on.

It needs nothing from this integration. A Live Activity is an ordinary notification carrying `live_update: true` and a `tag`, and what starts it is the passage event:

```yaml
automation:
  - alias: "ADS-B: overhead on the lock screen"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "{{ trigger.event.data.airline | default('Overhead') }}"
          message: >-
            {{ trigger.event.data.description | default('') }}
            {{ trigger.event.data.altitude }} ft
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}{% endif %}
          data:
            tag: adsb-overhead
            live_update: true

  - alias: "ADS-B: the sky is empty again"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_aircraft_overhead
        to: "off"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: clear_notification
          data:
            tag: adsb-overhead
```

The same `tag` on the next aircraft replaces the one before it without a banner or a sound, and the second automation takes it off your screen when there is nothing left up there. iOS limits how often an activity may start and how often it may be redrawn, which is why this hangs off the passage event and off a state going to off rather than off the poll: one message per aircraft instead of one every fifteen seconds.

### Asking a question

The entities answer the questions you knew to ask when you built the dashboard. Two services answer the rest, out of the same poll, without going back to the decoder.

**`adsb_station.look_up_aircraft`** takes a hex code or a callsign, in either case, and answers with everything the station knows about that one aircraft:

```yaml
- action: adsb_station.look_up_aircraft
  data:
    aircraft: KLM123
  response_variable: found
- condition: template
  value_template: "{{ found.aircraft is not none }}"
- action: notify.persistent_notification
  data:
    message: >
      {{ found.aircraft.flight }} is {{ found.aircraft.distance }} km to the
      {{ found.aircraft.sector }}, at {{ found.aircraft.altitude }} feet.
```

`aircraft` is `null` when the station is not hearing it, which is an answer and not a failure — that is the ordinary reply to "is it up there".

**`adsb_station.list_aircraft`** answers with everything that matches, nearest first:

```yaml
- action: adsb_station.list_aircraft
  data:
    max_distance: 25
    max_altitude: 10000
  response_variable: low
```

| Filter | |
|---|---|
| `max_distance` | In kilometres |
| `min_altitude`, `max_altitude` | In feet |
| `military` | On for military traffic only, off for everything but |
| `category` | The emitter category, `A7` for a helicopter and `B6` for a drone |

A filter leaves out what it cannot judge: an aircraft heard over Mode S alone has no position and no altitude, so it drops out of a distance or a height filter rather than being counted as nought.

Both reach **everything the decoder is holding**, which is the whole sky your antenna covers and not just the nearby radius. Without a single filter, `list_aircraft` answers with all of it. Both add one thing the attributes do not carry: `sector`, the compass direction to look in.

Try them under **Developer tools → Actions**, with **Return response data** ticked.

If you run several entries — a feeder or two beside the entry that carries your decoder — you can leave the station out. Only the entries that actually have a receiver are considered, so the field is needed only when two of yours are reading antennas.

### Asking out loud

"What is flying over?" is a better question to ask a room than to look up on a dashboard — you ask it while looking out of the window. Assist can answer five of them, from your own receiver, without a single request leaving your network.

| Ask | And it says |
|---|---|
| *What is flying over?* | Which aircraft is overhead, and how high |
| *How many aircraft can you hear?* | How many are nearby, and how many in all |
| *What is the nearest aircraft?* | How far away it is, and in which direction |
| *Are there any helicopters nearby?* | Military traffic, helicopters or drones in range |
| *Where is it going?* | Where the aircraft overhead came from and is heading |

Answers use the names from the [shipped tables](#names-for-the-codes), so it says "KLM 123" and not "kilo lima mike one two three", and they follow the unit system of your Home Assistant rather than the language: metres and kilometres, or feet and miles.

English and Dutch are spoken; a question in any other language is answered in English.

There are two ways to wire this up, and they end at the same five answers.

#### An automation, with no files at all

Home Assistant lets an automation own its sentences. Write them where you can see them, ask this integration for the answer, and say it back:

```yaml
automation:
  triggers:
    - trigger: conversation
      command:
        - "what is flying over"
        - "what is above me"
  actions:
    - action: adsb_station.speak
      data:
        question: overhead
      response_variable: spoken
    - set_conversation_response: "{{ spoken.speech }}"
```

Nothing is written to your configuration directory, nothing needs a restart, and you can edit the sentences in the interface. `question` is one of `overhead`, `count`, `closest`, `traffic` or `route`; the traffic one also takes `kind`, which is `military`, `helicopter` or `drone`.

The wording is still ours. `adsb_station.speak` hands back a finished sentence — the callsign spelled out or the airline named, the height rounded, the units and the decimal point right for the language — so the automation is three lines and not a template full of `round()`.

#### The sentence files, so Assist knows the questions itself

The other way needs no automations: Assist recognises all five out of the box, in both languages, including phrasings you did not think to write down.

The catch is where those sentences have to live. Home Assistant reads them from your **configuration directory alone**, so an integration cannot bring its own; they ship inside it and have to be copied once.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Or let the integration copy them, if you would rather not go looking:

```yaml
- action: adsb_station.install_sentences
```

Be plain about what that does: **it writes two files into your configuration directory** and overwrites them if they are already there. It is the same copy you would make by hand, and nothing else is touched.

Either way Assist reads its sentences at startup, so run `conversation.reload` or restart afterwards. Then try it under **Settings → Voice assistants**, and ask it with an empty sky as well — that is the answer that comes up most often.

If two of your entries read an antenna, the first by name answers. Assist is for a quick question; the [services](#asking-a-question) are there when it has to be exact.

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

- `http://<host>:8080/<path>/aircraft.json`, the aircraft list of your decoder.
- `<path>/stats.json` and `<path>/receiver.json`, found automatically next to `aircraft.json`.
- `http://<host>:8754/monitor.json`, the status page of `fr24feed`.
- `http://<host>:8080/status.json`, the status page of PiAware.
- `http://<host>:30053/ajax/stats`, the statistics of `pfclient`.

The last three are read only by the entry set up for that feeder.

Nothing else is contacted unless you ask for it. The single exception is [looking up a route](#where-a-flight-is-going), which reaches `adsb.im` over HTTPS and sends nothing but a callsign and the position it was heard at. Leave that setting off and the integration never leaves your network.

The integration reads them, it never writes. Ranges are measured from the antenna position in `receiver.json`; when the decoder publishes none, the home location of your Home Assistant installation is used, so make sure that location is correct.

Field names differ between decoders. The fr24feed fork reports `altitude` and `speed` where dump1090-fa and readsb report `alt_baro` and `gs`; the integration accepts both. The message rate is derived from two consecutive polls; after a restart of the receiver, the first value is skipped because its counter starts over.

### Troubleshooting

If entities stay `unknown` or `unavailable`, collect the two things below and attach them to an [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Enable debug logging.** Go to **Settings → Devices & services → ADS-B Station**, click the three dots and choose **Enable debug logging**. Reproduce the problem, then choose **Disable debug logging**, and Home Assistant downloads the log automatically.

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

Working on the integration itself is covered in [CONTRIBUTING.md](CONTRIBUTING.md): how to set up, the three checks that are the whole of what CI can tell you about the code, how the code is laid out, and how a release is cut. It needs Python 3.14 or newer and nothing else: no Home Assistant installation of your own.

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
| readsb of tar1090 | Alle ontvanger-entiteiten, en daarvan de meeste; zie [Welke decoder](#welke-decoder) |
| dump1090-fa of SkyAware | Alle ontvanger-entiteiten |
| dump1090, dump1090-mutability | De ontvanger-entiteiten die deze build meldt |
| De dump1090-fork die fr24feed meelevert | De ontvanger-entiteiten die die fork meldt |

Bovenop de decoder leest de integratie de feeders zelf uit, die elk hun eigen statuspagina op je netwerk aanbieden:

| Feeder | Netwerk | Statuspagina |
|---|---|---|
| `fr24feed` | Flightradar24 | `:8754/monitor.json` |
| PiAware | FlightAware | `:8080/status.json` |
| `pfclient` | Plane Finder | `:30053/ajax/stats` |

Een station voedt vaak meerdere netwerken vanaf één decoder, en zo is dit ook bedoeld: **één entry per feeder**, elk een eigen apparaat, met de decoder aan precies één ervan gekoppeld. Dan bestaan de vliegtuigcijfers één keer en heeft elk netwerk zijn eigen feedstatus. Een station dat nergens aan voedt kan ook: dan zet je alleen de ontvanger op.

Wat je krijgt is een echt apparaat met vertaalde entiteitsnamen en een configuratieflow, en cijfers waar je met de hand lastig aan komt: het aantal ontvangen vliegtuigen, het aantal berichten per seconde en het maximale bereik gemeten vanaf je antenne.

### Entiteiten

Alles uit `aircraft.json`, het deel dat elke opstelling krijgt:

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
| Vlucht overhead | Sensor | Het ene vliegtuig boven je, het dichtstbijzijnde door de lucht gemeten. Houdt de laatste vast als de lucht leegloopt, zodat een paneel erop nooit leeg staat. Zie [als er iets overkomt](#als-er-iets-overkomt) |
| Passages vandaag | Sensor | Hoeveel vliegtuigen er vandaag overkwamen, met de laatste twintig als attributen, meest recente eerst |
| Noodsquawk | Binary sensor (veiligheid) | Aan zolang een vliegtuig in je bereik 7500, 7600 of 7700 squawkt |
| Berichten | Sensor (diagnostisch) | De totale berichtenteller van de ontvanger |
| Ontvanger bijgewerkt | Sensor (diagnostisch) | Het tijdstempel in `aircraft.json` |

Het hoogste en het snelste tellen ook vliegtuigen die nooit een positie uitzenden: hoogte en snelheid komen al via Mode S binnen, en die weglaten zou beide cijfers te laag maken. Hun attribuut `distance` is dan leeg.

"In de laatste `aircraft.json`" is wat de decoder vasthoudt, en dat is iets meer dan wat er op dit moment uitzendt: hij bewaart een vliegtuig nog ongeveer een minuut na het laatste bericht. Dat is met opzet, en het is wat het aantal laat kloppen met de kaart die je decoder zelf toont. Het attribuut `seen` bij elk vliegtuig zegt hoeveel seconden geleden het voor het laatst gehoord is.

Een positie moet mogelijk zijn voordat hij geloofd wordt. ADS-B is zichtlijn, dus een vliegtuig op 37.000 voet is tot ongeveer 440 km te horen en een op 2.000 voet tot ongeveer 100 km, en daar komt 80 km bij voor een antenne die hoog staat. Een positie daarbuiten is verkeerd gedecodeerd in plaats van ontvangen, en vervalt: hij zou anders een vliegtuig boven je zetten dat er nooit was, of een [sectorrecord](#waar-je-antenne-geblokkeerd-zit) achterlaten dat voorgoed blijft staan. Het vliegtuig telt nog steeds als ontvangen, want het bestaat; alleen als een vliegtuig waarvan de positie onbekend is.

Die twee en het maximale bereik houden vast wat ze het laatst zagen in plaats van leeg te lopen zodra de lucht leeg is, en ze overleven een herstart. Een station dat een paar vliegtuigen per uur hoort zou anders het grootste deel van de tijd niets melden. Het attribuut `seen_at` zegt hoe lang geleden dat was, en elk volgt nog steeds de lucht: een lager toestel later vervangt de waarde. Dat is het verschil met de [sectorrecords](#waar-je-antenne-geblokkeerd-zit), die alleen maar groeien.

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

Die vier zijn groen, amber of rood in plaats van aan of uit, want amber zegt iets wat de andere twee niet kunnen: een feeder die een onstabiele klok meldt draait prima, maar zal nooit multilatereren. De kleur is de state, en de zin erachter, *"Local clock source is unstable"*, staat als attribuut `message` op de entiteit.

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

pfclient publiceert zelf geen multilateratie-vlag, maar telt wel wat het verstuurt, en een station waarvan de klok te onstabiel is om te multilatereren verstuurt niets. Die bytesteller is dus de sensor.

Met een feeder worden de feeder en de ontvanger los van elkaar uitgelezen: als de decoder niet meer antwoordt, worden alleen de vliegtuig-entiteiten onbeschikbaar en blijven de feed-entiteiten werken. Zonder feeder is de decoder de enige bron, en neemt een storing alles mee.

#### Waar je antenne geblokkeerd zit

Eén enkel maximumbereik verbergt de vorm van je dekking: 250 km naar het zuiden en 40 km naar het noorden is een heel ander station dan 145 km rondom. Acht sensoren houden per windrichting bij hoe ver een vliegtuig ooit gehoord is, elk over 45 graden gecentreerd op hun richting, dus **Bereikrecord noord** dekt 337,5° tot 22,5°.

| Entiteit | Type | Omschrijving |
|---|---|---|
| Bereikrecord noord … noordwest | Sensor (km) | Het record voor die sector, met `recorded_at`, `flight` en `hex` als attributen |
| Bereikrecords wissen | Knop | Wist alle acht |

Dit zijn de records; **Maximaal bereik** hierboven is het cijfer van nu. Die heet zo omdat de hobby het zo noemt en je feedersites het zo rapporteren, en hij volgt de lucht: een poll waarin niets verder weg is dan 40 km zet hem op 40 km. Deze acht gaan alleen maar omhoog.

De records groeien alleen maar, en ze overleven een herstart van Home Assistant, want een record dat bij elke herstart opnieuw begint is niets waard. De sensoren blijven ook leesbaar als er niets vliegt, want een record van vorige maand is nog steeds een meting.

Datzelfde groeien maakt ze onjuist zodra je antenne verhuist of de buurman een schuur neerzet; daar is de knop voor. Druk je erop terwijl er toestellen in beeld zijn, dan zet hij meteen nieuwe records vanaf de plek waar je antenne nu staat.

### Welke decoder

Elke decoder levert je de entiteiten hierboven waarvoor hij data heeft; wat hij meldt wordt bij het instellen gedetecteerd, zodat er geen entiteit wordt aangemaakt die nooit een waarde kan hebben. Dat betekent wel dat de decoder die je draait bepaalt hoeveel je krijgt, en **readsb levert het meest**:

| | dump1090-fork van fr24feed | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Vliegtuigen, bereik, berichten per seconde | Ja | Ja | Ja |
| Signaal, ruis, signaal-ruisverhouding | Ja | Ja | Ja |
| Gain | Nee | Ja | Ja |
| Antennepositie in `receiver.json` | Nee | Ja | Ja |
| Emittercategorie, en hoe het toestel gehoord is | Nee | Ja | Ja |
| Registratie, type, omschrijving | Nee | Nee | Ja, met vliegtuigdatabase |
| Markeringen interesting, PIA en LADD | Nee | Nee | Ja, met vliegtuigdatabase |

Twee daarvan zijn het benoemen waard. Zonder gain-waarde stem je je dongle blind af, en zonder antennepositie in `receiver.json` wordt het bereik gemeten vanaf de thuislocatie van je Home Assistant-installatie in plaats van vanaf je antenne, wat prima is als dat dezelfde plek is en fout als je ontvanger elders staat.

Draai je nu alleen `fr24feed`, dan kost het vervangen van de meegeleverde dump1090 door readsb je niets en levert het de gain-sensor, de vliegtuigdetails en een echte antennepositie op. **Draai Herconfigureren na een decoder-upgrade** om op te pikken wat hij nu kan.

#### De vliegtuigdatabase

De laatste twee rijen vragen één extra stap. readsb vult `r`, `t`, `desc` en `dbFlags` alleen als hij een vliegtuigdatabase heeft; zonder database meldt de sensor voor het dichtstbijzijnde vliegtuig wel een hex-code en een callsign, maar geen registratie en geen type. De militair-markering is de uitzondering: zonder database wordt die uit het adres afgeleid, wat [de tabel hieronder](#namen-bij-de-codes) uitlegt.

Haal op een readsb-installatie de database op en wijs readsb ernaar:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Voeg daarna de optie toe aan `/etc/default/readsb`, bij de argumenten waarmee readsb start:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Herstart readsb en de extra velden staan meteen in `aircraft.json`. De integratie pikt ze vanzelf op: de attributen verschijnen zodra de decoder ze stuurt, dus je hoeft niets te herconfigureren. De database is een momentopname, dus ververs hem af en toe door hetzelfde commando opnieuw te draaien.

#### Wat de decoder verder meldt

Er reizen nog vijf attributen met een vliegtuig mee, en net als hierboven staan ze er alleen als de decoder ze stuurt:

| Attribuut | Wat het zegt |
|---|---|
| `category` | De emittercategorie die het vliegtuig uitzendt, `A0` tot en met `D7`. `A7` is een helikopter en `B6` een drone, en dit is de enige plek waar dat ergens staat |
| `heard_as` | Hoe de decoder van het toestel af weet: `adsb_icao` rechtstreeks van het vliegtuig gehoord, `mlat` uitgerekend uit de aankomsttijden bij meerdere ontvangers, `mode_s` een kaal antwoord zonder positie erin |
| `interesting` | De vliegtuigdatabase heeft dit toestel gemarkeerd als de moeite waard |
| `pia` | Een Privacy ICAO Address: een tijdelijke hexcode waaronder een operator vliegt om buiten de lijsten te blijven |
| `ladd` | Het Amerikaanse verzoek om te beperken waar het toestel getoond wordt |

`category` komt door de lucht en staat er dus ook zonder vliegtuigdatabase; de laatste drie zijn de overige bits van diezelfde `dbFlags` waarvan de militaire markering bit 0 is. Alle drie worden doorgegeven en niet toegepast. Een toestel dat je ontvanger gehoord heeft, is er een die hij gehoord heeft, en of een dashboard een PIA- of LADD-vlucht weglaat is aan jou en niet aan deze integratie.

#### Namen bij de codes

Een vliegtuig zendt `DLH6CH`, `A20N` en `484123` uit. Geen van drieën is een naam, en geen decoder kan er een van maken, want die namen zitten niet in het radiosignaal: het zijn lijsten die iemand bijhoudt. Die lijsten worden met de integratie meegeleverd, dus de vliegtuigattributen dragen een naam zonder dat er iets over internet gevraagd wordt:

| Attribuut | Afgeleid uit | Voorbeeld |
|---|---|---|
| `airline` | De eerste drie letters van de callsign | `DLH6CH` → `Lufthansa` |
| `airline_code` | Diezelfde drie letters, of de tabel er nu een naam bij heeft of niet | `DLH6CH` → `DLH` |
| `description` | De ICAO-typecode, als de decoder hem zelf niet omschrijft | `A20N` → `Airbus A-320neo` |
| `country` | Het 24-bits adres zelf, dat ICAO per land in reeksen heeft uitgegeven | `484123` → `AW` |

Een callsign die geen vluchtnummer is levert geen maatschappij op. Zakenjets, zweefvliegtuigen en de meeste kleine luchtvaart vliegen onder hun registratie, dus `PHABC` blijft met rust gelaten in plaats van gelezen te worden als een maatschappijcode en te veranderen in wat `PHA` toevallig is.

`airline_code` staat er ook bij een maatschappij die de tabel niet kent, want het vliegtuig zendt hem uit en een dashboard zoekt er een logo mee op. `airline` staat er alleen als de tabel er een naam bij heeft.

Een typecode staat voor een familie en niet voor één vliegtuig: een A20N is een A320neo maar ook de zakenversie ervan, en een BE20 is elk van een stuk of tien King Airs plus hun militaire neven. Niets in de gegevens zegt welke je het vaakst boven je hoofd krijgt, dus de naam is degene die de code zelf spelt. Dat klopt voor de lijnvliegtuigen en kan bij de kleine luchtvaart op een vreemde variant uitkomen.

`country` is waar een toestel geregistreerd staat en niet waar het is: een KLM-toestel boven Spanje blijft `NL`. Niet elk adres valt in een reeks — sommige zijn nooit uitgegeven, sommige horen bij geen enkele staat, en een adres dat readsb heeft uitgerekend in plaats van gehoord krijgt een `~` mee — en een toestel daaruit draagt helemaal geen land in plaats van een gok.

Diezelfde tabel zegt welke reeksen een land voor zijn eigen krijgsmacht apart houdt, en daar komt de **militair-markering** vandaan als de decoder geen vliegtuigdatabase heeft. Het is het grovere van de twee antwoorden: het kent de reeks en niet het toestel, dus een civiel vliegtuig binnen een militaire reeks zou meegemarkeerd worden. Een decoder die wél een database heeft, heeft daarom het laatste woord, en in beide richtingen. Zegt `dbFlags` dat een toestel civiel is, dan is het civiel, ook binnen een militaire reeks; het adres wordt pas gevraagd als niemand anders antwoord geeft.

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
   - **Flightradar24-feeder (fr24feed)**: het adres van de machine waarop hij draait, en de poort van de statuspagina, standaard `8754`.
   - **FlightAware-feeder (PiAware)**: idem, standaard poort `8080`. Staat er een andere webserver op die poort, dan kan `status.json` elders staan; op een station met tar1090 achter nginx is poort 80 het proberen waard.
   - **Plane Finder-feeder (pfclient)**: idem, standaard poort `30053`.
   - **Alleen een ADS-B-ontvanger**: voor een station dat nergens aan voedt, of als de entry die de decoder draagt.
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

Er staan vier instellingen onder **Configureren** op de integratiepagina. De ververstijd is standaard 15 seconden; alles draait op je eigen netwerk, dus een korte tijd kan prima. De straal "dichtbij" is standaard 10 km en bepaalt wat als overhead telt voor de entiteiten **Vliegtuigen dichtbij** en **Vliegtuig overhead**; tien kilometer is ongeveer wat je kunt zien en horen, terwijl een goede ontvanger een veelvoud daarvan haalt. De andere twee zijn [vliegtuigen op de kaart](#vliegtuigen-op-de-kaart) en [waar een vlucht heen gaat](#waar-een-vlucht-heen-gaat), en die staan allebei uit. Station verhuisd naar een ander adres? Gebruik **Herconfigureren** in plaats van hem opnieuw toe te voegen.

Wil je een feeder toevoegen aan een station dat je als alleen-ontvanger hebt ingericht, voeg dan een tweede entry toe, precies wat je later ook doet om een tweede of derde netwerk erbij te zetten.

### Waar een vlucht heen gaat

Je antenne hoort dit nooit. Een vliegtuig zendt een callsign uit, `KLM1234`, en verder niets over de vlucht erachter, dus waar het opgestegen is en waar het heen gaat staat niet in `aircraft.json` en kan daar ook niet staan. Elke kaart die je een route laat zien, ook die van tar1090, vraagt het aan een database op de grond. Daarmee is dit het enige gegeven dat deze integratie niet op je eigen netwerk kan ophalen, en daarom staat **Vluchtroutes opzoeken** onder **Configureren** uit tot je hem aanzet.

De bron is **routeset**, via `adsb.im`, dezelfde bron die tar1090 zelf gebruikt. Hij vraagt niet om een account of een sleutel, en hij neemt alle callsigns van één meting in één verzoek.

Hij krijgt ook te horen waar elk vliegtuig gehoord is, en dat is wat hem laat oordelen. Een moderne callsign van een maatschappij wordt over de benen van een dag hergebruikt, dus het vluchtnummer kennen is niet hetzelfde als weten waar dát toestel heen gaat; routeset laat een route die niet bij de positie past vallen in plaats van hem te tonen, omdat een verkeerde route in een notificatie erger is dan geen.

Alleen de vliegtuigen binnen je straal "dichtbij" worden opgezocht. Dat is het handjevol waar een automatisering iets mee doet, en vragen naar elk vliegtuig in bereik zou een stroom verzoeken aan andermans server zijn voor een gegeven dat nergens getoond wordt. Antwoorden worden twaalf uur bewaard, zodat de lijnvluchten die er dagelijks overkomen één keer opgezocht worden in plaats van elke poll, en er worden nooit meer dan 25 nieuwe callsigns per poll opgezocht.

Wordt er een route gevonden, dan verschijnt die bij elk vliegtuig in de attributen van **Vliegtuigen dichtbij** en **Vliegtuig overhead**:

| Attribuut | Voorbeeld |
|---|---|
| `route` | `CDG-AMS` |
| `origin`, `destination` | `CDG`, `AMS` |
| `origin_location`, `destination_location` | `Paris`, `Amsterdam` |
| `origin_name`, `destination_name` | `Charles de Gaulle International Airport` |

De maatschappij staat er niet bij, en dat hoeft ook niet: die is er [hoe dan ook al](#namen-bij-de-codes).

Attributen die niet bekend zijn worden weggelaten in plaats van leeg gelaten, zodat een template kan vragen of de sleutel er überhaupt is. Privé, militair en een flink deel van het vrachtverkeer levert niets op, en een bron die onbereikbaar is betekent simpelweg geen route die poll; de vliegtuigentiteiten zelf hangen er nooit van af.

Een vliegtuig dat geen positie uitzendt krijgt ook geen route, want de bron toetst elke route die hij vindt aan waar het toestel is. In de praktijk kost dat niets: alleen de vliegtuigen die dichtbij genoeg zijn worden opgezocht, en dichtbij genoeg wordt vanaf een positie gemeten.

### Vliegtuigen op de kaart

Zet **Vliegtuigen op de kaart** aan onder **Configureren** en elk toestel binnen de nabijheidsstraal krijgt een eigen entiteit, getekend waar het is, zolang het er is. Er wordt niets extra's voor gelezen: de posities zitten al in elke poll, naast de afstanden waar de nabijheidssensoren op gebouwd zijn.

Eén kaartkaart laat ze allemaal zien:

```yaml
type: map
geo_location_sources:
  - adsb_station
hours_to_show: 0
```

Die `hours_to_show: 0` is het overwegen waard. Alles daarboven tekent een spoor uit de recorder, en deze entiteiten worden daar niet in bewaard.

Dat is precies de afweging die deze optie maakt, en die is het waard om te kennen voor je hem aanzet. **Deze vliegtuigen worden bewust niet geregistreerd.** Ze bestaan zolang ze boven je zijn en zijn weg zodra ze zijn doorgevlogen, dus een week verkeer laat niets achter — geen duizenden entiteiten in je registratie, geen `unavailable` toestellen die na elke herstart terugkomen, niets om op te ruimen. Daar staat tegenover dat je ze niet kunt hernoemen, verbergen of aan een gebied koppelen vanuit de interface, dat ze niet onder het apparaat van je station staan, en dat hun attributen buiten de recorder blijven. Hun entity-id's worden ook hergebruikt: `geo_location.klm123` is volgende week een andere vlucht onder dezelfde naam. Voor de geschiedenis is er het passagebord en het [passage-event](#als-er-iets-overkomt), en die zijn er wél op gebouwd.

Elk toestel heet naar zijn callsign, of naar zijn hexcode als hij er nog geen heeft gestuurd, en die naam ligt vast op het moment dat hij verschijnt. Een callsign komt vaak een paar polls later binnen, en hernoemen zou dan het entity-id middenin een passage onder je dashboard vandaan trekken.

Hoeveel het er zijn is wat je straal toelaat — bij de standaard tien kilometer meestal nul tot een handvol. Kies je een ruime straal en wil je ze liever helemaal niet in je database, sluit ze dan in één keer uit:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```

### Als er iets overkomt

**Vliegtuig overhead** beantwoordt één vraag, en dat doet hij goed: hangt er iets boven me. Wat hij niet kan vertellen is dat er een tweede toestel is aangekomen terwijl het eerste er nog is, want er verandert niets. Hij stond aan, en hij blijft aan.

Daarom vuurt een vliegtuig dat de lucht boven je oversteekt een eigen event af, één keer, op het moment dat het aankomt:

```yaml
automation:
  - alias: "ADS-B: er kwam iets over"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {{ trigger.event.data.airline | default('Een onbekend vliegtuig') }}
            op {{ trigger.event.data.slant_distance }} km
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}
            {%- endif %}.
```

Het event draagt dezelfde sleutels als de vliegtuigattributen, dus alles uit de melding hierboven zit erin: `flight`, `airline`, `description`, `altitude`, `vertical_rate`, de route als je die opzoekt, en `entry_id` en `station` om het ene station van het andere te onderscheiden. Er komt één sleutel bij, `slant_distance`, en die is het onderwerp van de volgende alinea.

Drie dingen houden het draaglijk.

**De afstand telt de hoogte mee.** Elke andere afstand in deze integratie wordt over de grond gemeten, en dat is het juiste antwoord op hoe ver je antenne reikt en het verkeerde op wat er boven je hangt. Een verkeersvliegtuig op 37.000 voet dat negen kilometer noordelijk passeert zit op de kaart binnen een straal van tien kilometer, en is veertien kilometer bij je vandaan door de lucht. Hij telt als dichtbij, en dat hoort ook, en hij is geen passage, en dat hoort ook. De `distance` in het event is nog steeds die over de grond; `slant_distance` is de echte.

**Een vliegtuig moet eerst weg zijn voor het opnieuw kan aankomen.** De ontvangst valt weg, toestellen draaien rondjes, en eentje op de rand van de straal knippert in en uit. Een vliegtuig dat weggaat en binnen tien minuten terugkomt is dezelfde passage; duurt het langer, dan is het een nieuwe. Een helikopter die vlakbij een perceel afwerkt belt dus één keer aan, niet elke minuut.

**Een vliegtuig moet vliegen.** Eentje op de grond meldt geen hoogte, dus de afstand door de lucht valt terug op die over de grond en een taxiënd verkeersvliegtuig lijkt precies op een lage overkomst. Woon je vlakbij een veld, dan is dat het grootste deel van je verkeer, dus die blijven erbuiten. Ze staan wel gewoon bij **Vliegtuigen dichtbij**, gemarkeerd met `on_ground`, want het is echt een vliegtuig binnen je straal.

#### Een melding die leest als een paneel

Het event draagt genoeg om het hele paneel in een notificatie te zetten, en de companion-app neemt er een afbeelding bij. Houd het bericht een letterlijk blok, `|-` en niet `>-`, anders vouwen de regels tot één zin:

```yaml
automation:
  - alias: "ADS-B: passage als paneel"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_jouw_telefoon
        data:
          title: >-
            {{ trigger.event.data.airline
               | default(trigger.event.data.flight) | default('Onbekend toestel') }}
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Hgt {{ trigger.event.data.altitude or '?' }}ft, Snh {{ trigger.event.data.speed | round | int if trigger.event.data.speed else '?' }}kn
            Krs {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Stg {{ trigger.event.data.vertical_rate or 0 }}ft/min
          data:
            subtitle: >-
              {{ trigger.event.data.route
                 | default(trigger.event.data.slant_distance ~ ' km') }}
            tag: adsb-passage
            group: adsb
            image: >-
              /local/airline_logos/{{ trigger.event.data.airline_code
                 | default('unknown') }}.png
```

Dat leest zo, en de rechterkolom is wat je krijgt van iets dat bijna niets uitzendt:

```
Lufthansa                    PHABC
CDG-AMS                      1,1 km
Airbus A-320neo
Hgt 4100ft, Snh 250kn        Hgt 2000ft, Snh ?kn
Krs 263deg, Stg -1088ft/min  Krs 90deg, Stg 0ft/min
```

Voor meters en kilometers per uur verandert alleen het bericht, met dezelfde factoren als bij [de cards](#het-paneel-en-het-bord):

```yaml
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Hgt {{ (trigger.event.data.altitude * 0.3048) | round | int }}m, Snh {{ (trigger.event.data.speed * 1.852) | round | int if trigger.event.data.speed else '?' }}km/h
            Krs {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Stg {{ (trigger.event.data.vertical_rate | default(0) * 0.00508) | round(1) }}m/s
```

Wat er dan uitkomt, met een echte vlucht erdoorheen:

```
Delta Air Lines
FRA-JFK
Airbus A-330-200
Hgt 8702m, Snh 891km/h
Krs 290deg, Stg 2,9m/s
```

Het logo lever je zelf: de app accepteert een `/local/`-pad naar je `www`-map, dus `www/airline_logos/DLH.png` met een `unknown.png` ernaast dekt elk vliegtuig. Logo's van maatschappijen zijn merken, en die kan deze integratie niet voor je meeleveren. Geef elke melding dezelfde `tag` en elk toestel vervangt het vorige in plaats van je scherm vol te zetten; laat je de `tag` weg en houd je de `group`, dan zie je ze allemaal staan.

#### Het paneel en het bord

Twee sensoren lezen die passages uit, en samen zijn ze een vertrekbord voor je eigen dak.

**Vlucht overhead** is het toestel dat nu boven je hangt, het dichtstbijzijnde door de lucht gemeten, met alles erover als attributen: `airline`, `description`, `altitude`, `speed`, `track`, `vertical_rate`, `slant_distance`, de route als je die opzoekt, en `since`, het moment dat hij aankwam. Hij houdt het laatste toestel vast in plaats van leeg te lopen als de lucht leeg raakt, want een paneel dat tussen twee vliegtuigen door leeg staat is het ophangen niet waard. Het attribuut `overhead` zegt welke van de twee je ziet, en `seen_at` wanneer het gelezen is.

Meer heb je voor een paneel niet nodig, alleen een markdown-card:

```yaml
type: markdown
content: |
  {% set plane = states.sensor.ads_b_station_vlucht_overhead %}
  ## {{ plane.attributes.airline | default(plane.state) }}
  {% if plane.attributes.route is defined %}### {{ plane.attributes.route }}{% endif %}
  {{ plane.attributes.description | default(plane.attributes.aircraft_type) | default('') }}

  `Hgt {{ plane.attributes.altitude }}ft  Snh {{ plane.attributes.speed }}kn`
  `Krs {{ plane.attributes.track | round | int }}deg  Stg {{ plane.attributes.vertical_rate or 0 }}ft/min`

  {% if not plane.attributes.overhead %}*Laatst gezien {{ relative_time(plane.last_changed) }} geleden*{% endif %}
```

Hoogtes staan daar in voet en snelheden in knopen, want zo zendt het vliegtuig ze uit en zo leest de luchtvaart ze. De entiteiten zelf kun je stuk voor stuk omzetten naar meters en kilometers per uur via **Instellingen → Entiteit → Maateenheid**, maar attributen rekent Home Assistant nooit om, dus een kaart die metrisch wil doet de som zelf:

```jinja
  `Hgt {{ (plane.attributes.altitude * 0.3048) | round | int }}m  Snh {{ (plane.attributes.speed * 1.852) | round | int }}km/h`
  `Krs {{ plane.attributes.track | round | int }}deg  Stg {{ (plane.attributes.vertical_rate * 0.00508) | round(1) }}m/s`
```

| Van | Naar | Maal |
|---|---|---|
| ft | m | 0,3048 |
| kn | km/h | 1,852 |
| ft/min | m/s | 0,00508 |

`distance` en `slant_distance` staan al in kilometers.

**Passages vandaag** is de teller, en de laatste twintig staan als attributen op de sensor: hoe laat ze aankwamen, de callsign, de maatschappij, het type, hoe hoog en hoe dichtbij ze kwamen. Allebei overleven ze een herstart van Home Assistant, zodat het bord een verslag is en niet een sessie.

Elke regel houdt het toestel op zijn dichtste punt vast en niet bij aankomst, want je ziet een vliegtuig het eerst aan de rand van de straal en het best als het recht boven je staat. Hij verschijnt op het bord zodra het toestel aankomt en wordt bijgewerkt zolang het in beeld is, dus het bord loopt bij en klopt uiteindelijk.

```yaml
type: markdown
content: |
  {% for plane in state_attr('sensor.ads_b_station_passages_vandaag', 'passages') %}
  `{{ as_timestamp(plane.at) | timestamp_custom('%H:%M') }}` **{{ plane.airline | default(plane.flight) | default('?') }}**
  {{ plane.route | default('') }} {{ plane.description | default('') }} · {{ plane.distance }} km
  {% endfor %}
```

Eén ding om te weten voor je dat laat draaien: er worden twintig regels naar de database geschreven elke keer dat er een vliegtuig overkomt. Op een druk station is het de moeite waard om dat buiten de recorder te houden, wat je niets kost behalve de historie van een bord dat je toch live afleest:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ads_b_station_passages_vandaag
```

#### Op je vergrendelscherm

De companion-app kan een passage op je vergrendelscherm en in het Dynamic Island zetten als [Live Activity](https://companion.home-assistant.io/docs/notifications/live-activities/), en dat is het dichtst bij een flight wall dat je op zak kunt dragen.

**Dit werkt alleen op de TestFlight-versie van de companion-app, met Live Activities aangezet onder Labs**, en je hebt Home Assistant 2026.7 of nieuwer nodig. In de App Store-versie zit het niet, dus zie het als iets om te proberen en niet als iets om op te bouwen.

Van deze integratie vraagt het niets. Een Live Activity is een gewone notificatie met `live_update: true` en een `tag` erin, en wat hem start is het passage-event:

```yaml
automation:
  - alias: "ADS-B: overhead op het vergrendelscherm"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_jouw_telefoon
        data:
          title: "{{ trigger.event.data.airline | default('Overhead') }}"
          message: >-
            {{ trigger.event.data.description | default('') }}
            {{ trigger.event.data.altitude }} ft
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}{% endif %}
          data:
            tag: adsb-overhead
            live_update: true

  - alias: "ADS-B: de lucht is weer leeg"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_vliegtuig_overhead
        to: "off"
    action:
      - service: notify.mobile_app_jouw_telefoon
        data:
          message: clear_notification
          data:
            tag: adsb-overhead
```

Dezelfde `tag` bij het volgende toestel vervangt het vorige zonder banner en zonder geluid, en de tweede automatisering haalt hem van je scherm als er niets meer boven je hangt. iOS beperkt hoe vaak een activity mag starten en hoe vaak hij opnieuw getekend mag worden, en daarom hangt dit aan het passage-event en aan een state die naar off gaat en niet aan de meting: één bericht per vliegtuig in plaats van één per vijftien seconden.

### Iets vragen

De entiteiten beantwoorden de vragen die je wist te stellen toen je je dashboard bouwde. Twee acties beantwoorden de rest, uit diezelfde poll, zonder opnieuw bij de decoder langs te gaan.

**`adsb_station.look_up_aircraft`** neemt een hexcode of een callsign, hoofdletters maken niet uit, en antwoordt met alles wat het station van dat ene toestel weet:

```yaml
- action: adsb_station.look_up_aircraft
  data:
    aircraft: KLM123
  response_variable: found
- condition: template
  value_template: "{{ found.aircraft is not none }}"
- action: notify.persistent_notification
  data:
    message: >
      {{ found.aircraft.flight }} zit {{ found.aircraft.distance }} km naar het
      {{ found.aircraft.sector }}, op {{ found.aircraft.altitude }} voet.
```

`aircraft` is `null` als het station hem niet hoort, en dat is een antwoord en geen fout — het is het gewone antwoord op "hangt hij er?".

**`adsb_station.list_aircraft`** antwoordt met alles wat voldoet, dichtstbij eerst:

```yaml
- action: adsb_station.list_aircraft
  data:
    max_distance: 25
    max_altitude: 10000
  response_variable: low
```

| Filter | |
|---|---|
| `max_distance` | In kilometers |
| `min_altitude`, `max_altitude` | In voet |
| `military` | Aan voor alleen militair verkeer, uit voor alles behalve dat |
| `category` | De emittercategorie, `A7` voor een helikopter en `B6` voor een drone |

Een filter laat weg wat het niet kan beoordelen: een toestel dat alleen over Mode S gehoord is heeft geen positie en geen hoogte, en valt dus uit een afstands- of hoogtefilter in plaats van als nul geteld te worden.

Allebei reiken ze tot **alles wat de decoder vasthoudt**, dus de hele lucht die je antenne dekt en niet alleen de nabijheidsstraal. Zonder één filter antwoordt `list_aircraft` met de complete lijst. Allebei voegen ze één ding toe dat de attributen niet dragen: `sector`, de windrichting waarin je moet kijken.

Probeer ze onder **Ontwikkelhulpmiddelen → Acties**, met **Antwoordgegevens teruggeven** aangevinkt.

Draai je meerdere entries — een feeder of twee naast de entry die je decoder draagt — dan kun je het station weglaten. Alleen de entries die echt een ontvanger hebben tellen mee, dus het veld is pas nodig als er twee van jou een antenne lezen.

### Hardop vragen

"Wat vliegt daar over?" is een vraag die je eerder aan de kamer stelt dan opzoekt op een dashboard — je stelt hem terwijl je naar buiten kijkt. Assist beantwoordt er vijf, uit je eigen ontvanger, zonder dat er één verzoek je netwerk verlaat.

| Vraag | En hij zegt |
|---|---|
| *Wat vliegt er over?* | Welk toestel boven je hangt, en hoe hoog |
| *Hoeveel vliegtuigen hoor je?* | Hoeveel er dichtbij zijn, en hoeveel in totaal |
| *Wat is het dichtstbijzijnde vliegtuig?* | Hoe ver weg het is, en in welke richting |
| *Zijn er helikopters in de buurt?* | Militair verkeer, helikopters of drones in bereik |
| *Waar gaat hij heen?* | Waar het toestel boven je vandaan komt en heen gaat |

De antwoorden gebruiken de namen uit de [meegeleverde tabellen](#namen-bij-de-codes), dus hij zegt "KLM 123" en niet "kilo lima mike één twee drie", en ze volgen het eenhedenstelsel van je Home Assistant en niet de taal: meters en kilometers, of voet en mijl.

Engels en Nederlands worden gesproken; een vraag in een andere taal wordt in het Engels beantwoord.

Er zijn twee manieren om dit aan te sluiten, en ze komen bij dezelfde vijf antwoorden uit.

#### Een automatisering, zonder enig bestand

Home Assistant laat een automatisering zijn eigen zinnen bezitten. Schrijf ze waar je ze kunt zien, vraag deze integratie om het antwoord, en zeg het terug:

```yaml
automation:
  triggers:
    - trigger: conversation
      command:
        - "wat vliegt er over"
        - "wat hangt er boven me"
  actions:
    - action: adsb_station.speak
      data:
        question: overhead
      response_variable: spoken
    - set_conversation_response: "{{ spoken.speech }}"
```

Er wordt niets in je configuratiemap geschreven, er hoeft niets herstart, en je kunt de zinnen in de interface aanpassen. `question` is `overhead`, `count`, `closest`, `traffic` of `route`; die laatste-op-een-na neemt ook `kind`, en dat is `military`, `helicopter` of `drone`.

De formulering blijft van ons. `adsb_station.speak` geeft een afgemaakte zin terug — callsign gespeld of maatschappij genoemd, hoogte afgerond, eenheden en decimaalteken passend bij de taal — zodat de automatisering drie regels is en geen template vol `round()`.

#### De zinsbestanden, zodat Assist de vragen zelf kent

De andere weg heeft geen automatiseringen nodig: Assist herkent alle vijf uit zichzelf, in beide talen, ook formuleringen die je zelf niet had bedacht.

De adder zit in waar die zinnen moeten staan. Home Assistant leest ze **alleen uit je configuratiemap**, dus een integratie kan de zijne niet meeleveren; ze zitten erin en moeten één keer gekopieerd worden.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Of laat de integratie ze kopiëren, als je er liever niet naar op zoek gaat:

```yaml
- action: adsb_station.install_sentences
```

Wees helder over wat dat doet: **het schrijft twee bestanden in je configuratiemap** en overschrijft ze als ze er al staan. Het is dezelfde kopie die je met de hand zou maken, en verder wordt er niets aangeraakt.

Hoe dan ook leest Assist zijn zinnen bij het opstarten, dus draai daarna `conversation.reload` of herstart. Probeer het vervolgens onder **Instellingen → Spraakassistenten**, en vraag het ook eens met een lege lucht — dat is het antwoord dat het vaakst voorkomt.

Lezen twee van je entries een antenne, dan antwoordt de eerste op naam. Assist is voor een snelle vraag; de [acties](#iets-vragen) zijn er als het precies moet.

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

De entity-ID's hierboven volgen de apparaatnaam: `ads_b_station` voor een station zonder feeder, je feed-alias voor een station met. Die apparaatnaam wordt niet vertaald, de entiteitsnaam erachter wel, dus noem je het apparaat in Home Assistant anders, dan veranderen de entity-ID's mee.

### Over de endpoints

Alle endpoints zijn gewone HTTP-adressen zonder authenticatie op je lokale netwerk:

- `http://<host>:8080/<pad>/aircraft.json`, de vliegtuiglijst van je decoder.
- `<pad>/stats.json` en `<pad>/receiver.json`, die automatisch naast `aircraft.json` gevonden worden.
- `http://<host>:8754/monitor.json`, de statuspagina van `fr24feed`.
- `http://<host>:8080/status.json`, de statuspagina van PiAware.
- `http://<host>:30053/ajax/stats`, de statistieken van `pfclient`.

Die laatste drie worden alleen gelezen door de entry die voor die feeder is ingericht.

Verder wordt er niets benaderd tenzij je erom vraagt. De enige uitzondering is [een route opzoeken](#waar-een-vlucht-heen-gaat), wat via HTTPS `adsb.im` aanspreekt en niets meegeeft behalve een callsign en de positie waar hij gehoord is. Laat je die instelling uit, dan verlaat de integratie je netwerk nooit.

De integratie leest ze alleen uit en schrijft nooit. Afstanden worden gemeten vanaf de antennepositie in `receiver.json`; publiceert de decoder die niet, dan wordt de thuislocatie van je Home Assistant-installatie gebruikt, dus zorg dat die locatie klopt.

Veldnamen verschillen per decoder. De fr24feed-fork meldt `altitude` en `speed` waar dump1090-fa en readsb `alt_baro` en `gs` melden; de integratie begrijpt beide. Het aantal berichten per seconde komt uit twee opeenvolgende metingen; na een herstart van de ontvanger wordt de eerste waarde overgeslagen omdat de teller dan opnieuw begint.

### Problemen oplossen

Blijven entiteiten op `unknown` of `unavailable` staan? Verzamel dan de twee onderstaande zaken en voeg ze toe aan een [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Debug-logging aanzetten.** Ga naar **Instellingen → Apparaten & diensten → ADS-B Station**, klik op de drie puntjes en kies **Debug-logging aanzetten**. Reproduceer het probleem en kies daarna **Debug-logging uitzetten**, en Home Assistant downloadt de log automatisch.

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

Werken aan de integratie zelf staat in [CONTRIBUTING.md](CONTRIBUTING.md) (Engels): hoe je het opzet, de drie controles die alles zijn wat CI je over de code kan vertellen, hoe de code is ingedeeld en hoe een release eruit gaat. Je hebt Python 3.14 of nieuwer nodig en verder niets: geen eigen Home Assistant-installatie.

```bash
pip install -r requirements_test.txt
scripts/check.sh          # of scripts\check.ps1
```

### Disclaimer

Dit is een onofficiële integratie en is niet gelieerd aan Flightradar24, FlightAware of Plane Finder. Gebruik op eigen risico.
