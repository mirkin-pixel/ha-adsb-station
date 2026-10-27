# About the endpoints

Every endpoint is plain, unauthenticated HTTP on your local network:

- `http://<host>:8080/<path>/aircraft.json`, the aircraft list of your decoder.
- `<path>/stats.json` and `<path>/receiver.json`, found automatically next to `aircraft.json`.
- `http://<host>:8754/monitor.json`, the status page of `fr24feed`.
- `http://<host>:8080/status.json`, the status page of PiAware.
- `http://<host>:30053/ajax/stats`, the statistics of `pfclient`.

The last three are read only by the entry set up for that feeder.

Nothing else is contacted unless you ask for it. There are two exceptions, each a setting of its own. [Looking up a route](routes.md) reaches `adsb.im` over HTTPS and sends nothing but a callsign and the position it was heard at. [Looking up a photo](photos.md) reaches `api.planespotters.net` over HTTPS and sends nothing but the address the aircraft broadcasts; the photo itself is loaded by your browser or phone when it shows it. Leave both off and the integration never leaves your network.

The integration reads them, it never writes. Ranges are measured from the antenna position in `receiver.json`; when the decoder publishes none, the home location of your Home Assistant installation is used, so make sure that location is correct.

Field names differ between decoders. The fr24feed fork reports `altitude` and `speed` where dump1090-fa and readsb report `alt_baro` and `gs`; the integration accepts both. The message rate is derived from two consecutive reads of the statistics, a minute apart by default; after a restart of the receiver, the first value is skipped because its counter starts over.
