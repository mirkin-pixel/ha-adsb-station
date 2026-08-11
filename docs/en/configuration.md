# Configuration

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

Five settings live under **Configure** on the integration page. The update interval is 15 seconds by default; everything runs on your own network, so a short interval is fine. The nearby radius is 10 km by default and decides what counts as overhead for the **Aircraft nearby** and **Aircraft overhead** entities; ten kilometres is roughly what you can see and hear, while a good receiver reaches many times that. Beside it is the [overhead ceiling](#what-counts-as-overhead), which is empty. The last two are [aircraft on the map](dashboards.md#aircraft-on-the-map) and [where a flight is going](routes.md), and both are off. Moved your station to a different address? Use **Reconfigure** instead of adding it again.

Adding a feeder to a station you set up as receiver-only means adding it as a second entry, which is the same thing you do to add a second or third network later.

## Running the feeder as an add-on

If your decoder runs as a Home Assistant add-on rather than on a machine of its own — [MaxWinterstein's ADS-B Multi Portal Feeder](https://github.com/MaxWinterstein/homeassistant-addons) is the common one — there is no IP address to fill in. Add-ons reach each other by hostname, and the add-on's own **Info** page shows what its hostname is: the slug with the repository's prefix in front of it, as in `1a2b3c4d-adsb-multi-portal-feeder`. Use that where the flow asks for a host.

## What counts as overhead

A radius is a circle drawn on the ground. An airliner at 36,000 feet passing over your street is inside a ten kilometre circle, and it is nothing anybody would look up at — the height is already counted for the distance, but a wide radius lets it in anyway.

**Overhead ceiling** under **Configure** is the answer, in feet, and it is empty until you set it. Ten thousand feet is a reasonable place to start: below it is traffic on approach, helicopters, and anything with a reason to be low.

What it changes is deliberately narrow:

| | With a ceiling set |
|---|---|
| **Aircraft nearby**, **Aircraft overhead**, passages, the passage event, the map | Only aircraft under it |
| **Aircraft received**, the range records, **Maximum range**, the highest and the fastest | Unchanged — those are about what your station heard |
| **Emergency squawk** | Unchanged, at any height. An aircraft squawking 7700 is worth hearing about from 37,000 feet |

An aircraft that says it is **on the ground** stays nearby whatever the ceiling is. It reports no altitude precisely because it is on the ground, so comparing the figure would throw out the traffic a ceiling was never aimed at. An aircraft that reports no altitude for any other reason — heard over bare Mode S, say — cannot be judged and drops out, the same way a height filter on the [services](services.md) leaves out what it cannot measure.
