# Over de endpoints

Alle endpoints zijn gewone HTTP-adressen zonder authenticatie op je lokale netwerk:

- `http://<host>:8080/<pad>/aircraft.json`, de vliegtuiglijst van je decoder.
- `<pad>/stats.json` en `<pad>/receiver.json`, die automatisch naast `aircraft.json` gevonden worden.
- `http://<host>:8754/monitor.json`, de statuspagina van `fr24feed`.
- `http://<host>:8080/status.json`, de statuspagina van PiAware.
- `http://<host>:30053/ajax/stats`, de statistieken van `pfclient`.

Die laatste drie worden alleen gelezen door de entry die voor die feeder is ingericht.

Verder wordt er niets benaderd tenzij je erom vraagt. De enige uitzondering is [een route opzoeken](routes.md), wat via HTTPS `adsb.im` aanspreekt en niets meegeeft behalve een callsign en de positie waar hij gehoord is. Laat je die instelling uit, dan verlaat de integratie je netwerk nooit.

De integratie leest ze alleen uit en schrijft nooit. Afstanden worden gemeten vanaf de antennepositie in `receiver.json`; publiceert de decoder die niet, dan wordt de thuislocatie van je Home Assistant-installatie gebruikt, dus zorg dat die locatie klopt.

Veldnamen verschillen per decoder. De fr24feed-fork meldt `altitude` en `speed` waar dump1090-fa en readsb `alt_baro` en `gs` melden; de integratie begrijpt beide. Het aantal berichten per seconde komt uit twee opeenvolgende metingen; na een herstart van de ontvanger wordt de eerste waarde overgeslagen omdat de teller dan opnieuw begint.
