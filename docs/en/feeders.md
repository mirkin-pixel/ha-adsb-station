# Feeders

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

## Where your antenna is blocked

A single maximum range figure hides the shape of your coverage: 250 km to the south and 40 km to the north is a very different station from 145 km all round. Eight sensors keep the furthest an aircraft has ever been heard in each compass sector, spanning 45 degrees centred on their direction, so **Range record north** covers 337.5° to 22.5°.

| Entity | Type | Description |
|---|---|---|
| Range record north … northwest | Sensor (km) | The record for that sector, with `recorded_at`, `flight` and `hex` as attributes |
| Reset range records | Button | Clears all eight |

These are the records; **Maximum range** above is the live figure. It is named for what the hobby calls it and for what your feeder sites report, and it follows the sky: a poll with nothing further away than 40 km puts it at 40 km. These eight only ever go up.

The records only ever grow, and they survive a restart of Home Assistant, because a record that started over every restart would be worth nothing. The sensors also stay readable when nothing is flying, because a record from last month is still a reading.

That same growth makes them wrong the moment the antenna moves or a neighbour puts up a shed, which is what the button is for. Pressing it while aircraft are in view immediately sets fresh records from them, measured from where the antenna is now.
