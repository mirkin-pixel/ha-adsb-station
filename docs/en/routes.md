# Where a flight is going

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

The airline is not among them, and does not need to be: it is [there either way](decoders.md#names-for-the-codes).

Attributes that are not known are left out rather than left empty, so a template can ask whether the key is there at all. Private, military and a good deal of cargo traffic resolves to nothing, and the source being unreachable simply means no route that poll; the aircraft entities themselves never depend on it.

An aircraft that broadcasts no position gets no route either, because the source judges every route it finds against where the aircraft is. In practice nothing is lost: only the aircraft near enough to be looked up are asked about, and being near enough is measured from a position.
