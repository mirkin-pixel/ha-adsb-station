# Entities

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
| Aircraft nearby | Sensor | How many aircraft are inside the nearby radius, with all of them as attributes, nearest first. These are the two that can carry [where the flight is going](routes.md) |
| Aircraft overhead | Binary sensor | On while at least one aircraft is inside that radius |
| Overhead flight | Sensor | The one aircraft above you, nearest first and measured through the air. Keeps the last one when the sky empties, so a panel built on it never goes blank. See [when something comes over](passages.md) |
| Passages today | Sensor | How many aircraft came over today, with the last twenty of them as attributes, most recent first |
| Heard today | Sensor | How many different aircraft the station heard today, at any distance |
| Watchlist in range | Binary sensor | On while an aircraft from your [watchlist](watchlist.md) is in the air. Only there when you have set one |
| Emergency squawk | Binary sensor (safety) | On while an aircraft in range squawks 7500, 7600 or 7700 |
| Messages | Sensor (diagnostic) | The total message counter of the receiver |
| Receiver updated | Sensor (diagnostic) | The timestamp inside `aircraft.json` |

The highest and the fastest also count aircraft that never broadcast a position: altitude and speed reach us from Mode S alone, and leaving those out would understate both. Their `distance` attribute is then empty.

"In the last `aircraft.json`" is what the decoder is holding, which is a little more than what is transmitting this second: it keeps an aircraft for about a minute after its last message. That is deliberate, and it is what makes the count agree with the map your decoder serves. The `seen` attribute on each aircraft says how many seconds ago it was last heard.

A position has to be possible before it is believed. ADS-B is line of sight, so an aircraft at 37,000 feet can be heard from roughly 440 km and one at 2,000 feet from roughly 100 km, and this allows 80 km on top of that for an antenna standing high. A position beyond that was mis-decoded rather than received, and is dropped: it would otherwise put an aircraft overhead that was never there, or leave a [sector record](feeders.md#where-your-antenna-is-blocked) that stands for good. The aircraft still counts as received, because it is real; it just counts as one whose position is unknown.

Those two and the maximum range keep what they last saw rather than blanking when the sky empties, and they survive a restart. A station that hears a couple of aircraft an hour would otherwise report nothing most of the time. The `seen_at` attribute says how long ago it was, and each still follows the sky: a lower aircraft later replaces the reading. That is what separates them from the [sector records](feeders.md#where-your-antenna-is-blocked), which only ever grow.

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
