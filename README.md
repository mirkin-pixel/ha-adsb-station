# ADS-B Station for Home Assistant

[![Validate](https://img.shields.io/github/actions/workflow/status/mirkin-pixel/ha-adsb-station/validate.yml?branch=main&style=for-the-badge&label=Validate)](https://github.com/mirkin-pixel/ha-adsb-station/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/mirkin-pixel/ha-adsb-station?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)
[![License](https://img.shields.io/github/license/mirkin-pixel/ha-adsb-station?style=for-the-badge)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/mirkin-pixel/ha-adsb-station/total?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)

[English](#english) | [Nederlands](#nederlands)

---

## English

Custom integration for [Home Assistant](https://www.home-assistant.io/) that reads **your own ADS-B receiver**. Everything happens on your own network: the integration polls the `aircraft.json` of your decoder and, if you run one, the `monitor.json` status page of `fr24feed` next to it.

It is not tied to a single network. Anything that serves an `aircraft.json` works, so it does not matter whether you feed Flightradar24, FlightAware, Plane Finder, several of them at once, or nothing at all:

| Setup | Works | What you get |
|---|---|---|
| readsb or tar1090 | Yes | Every receiver entity, and the most of them — see [Which decoder](#which-decoder) |
| dump1090-fa, PiAware or SkyAware (FlightAware) | Yes | Every receiver entity |
| dump1090, dump1090-mutability | Yes | The receiver entities its build reports |
| pfclient (Plane Finder) alongside a decoder | Yes | The receiver entities of that decoder |
| fr24feed (Flightradar24) | Yes | The receiver entities **plus** the feed status of the feeder |

Only the feed status entities need `fr24feed`; everything else comes from the decoder. Plane Finder's own client is not read directly, but pfclient runs next to a decoder, and that decoder is what the integration reads.

This replaces a handful of hand-written `platform: rest` sensors with a proper device, translated entity names, a config flow, and figures the REST sensors could not give you: the number of aircraft received, the message rate, and the maximum range measured from your antenna.

### Entities

Everything from `aircraft.json` — the part every setup gets:

| Entity | Type | Description |
|---|---|---|
| Aircraft received | Sensor | Aircraft in the last `aircraft.json` |
| Aircraft with position | Sensor | Of those, the number with a known position |
| Maximum range | Sensor (km) | Distance to the furthest aircraft |
| Message rate | Sensor (msg/s) | Mode S messages per second, computed between two polls |
| Closest aircraft | Sensor (km) | Distance to the nearest aircraft, with its callsign, altitude, speed, heading and signal strength as attributes. A decoder with an aircraft database adds registration, type and a military marker |
| Highest aircraft | Sensor (ft) | Altitude of the highest aircraft in range, with the same attributes |
| Fastest aircraft | Sensor (kn) | Ground speed of the fastest aircraft in range, with the same attributes |
| Aircraft nearby | Sensor | How many aircraft are inside the nearby radius, with all of them as attributes, nearest first |
| Aircraft overhead | Binary sensor | On while at least one aircraft is inside that radius |
| Emergency squawk | Binary sensor (safety) | On while an aircraft in range squawks 7500, 7600 or 7700 |
| Messages | Sensor (diagnostic) | The total message counter of the receiver |
| Receiver updated | Sensor (diagnostic) | The timestamp inside `aircraft.json` |

The highest and the fastest also count aircraft that never broadcast a position: altitude and speed reach us from Mode S alone, and leaving those out would understate both. Their `distance` attribute is then empty.

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

The reception figures come from the shortest measurement window that has actually measured a signal, normally `last1min`. The window a value came from is on the entity as a `period` attribute.

Everything from `monitor.json` — **only when you run `fr24feed`**:

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
| CPU temperature | Sensor (diagnostic) | The SoC temperature of the host |

With a feeder, the feeder and the receiver are read independently: if the decoder stops answering, only the aircraft entities become unavailable and the feed entities keep working. Without a feeder the decoder is the only source, so an outage takes everything with it.

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
3. Choose what your station runs:
   - **ADS-B receiver only** — enter the address of the machine running your decoder, for example `192.168.5.7`. The integration looks for its `aircraft.json` and shows you what it found.
   - **Flightradar24 feeder (fr24feed)** — enter the address of the machine running `fr24feed` and the port of its status page (`8754` by default). The receiver is asked for in a second step and may be left empty.

These paths are probed automatically, on port 8080 where fr24feed and PiAware serve them and on port 80 where readsb with tar1090 does:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

All candidates are probed at the same time, and the first one in that order that answers wins. If yours is somewhere else, type the full URL yourself.

Two settings live under **Configure** on the integration page. The update interval is 15 seconds by default; everything runs on your own network, so a short interval is fine. The nearby radius is 10 km by default and decides what counts as overhead for the **Aircraft nearby** and **Aircraft overhead** entities — ten kilometres is roughly what you can see and hear, while a good receiver reaches many times that. Moved your station to a different address? Use **Reconfigure** instead of adding it again.

Adding `fr24feed` to a station you set up as receiver-only means adding it as a second integration entry, or removing the entry and adding it again through the feeder path.

### Replacing the REST sensors

If you configured an `fr24feed` station with `platform: rest` sensors before, you can remove that YAML after setting up the integration. The mapping is:

| REST sensor | Entity |
|---|---|
| `value_json.feed_alias` | `sensor.<feeder>_feed_alias` |
| `rx_connected` | `binary_sensor.<feeder>_receiver` |
| `feed_status` | `binary_sensor.<feeder>_feed` and `sensor.<feeder>_feed_status` |
| `d11_map_size` | `sensor.<feeder>_map_size` |
| `feed_num_ac_tracked` | `sensor.<feeder>_aircraft_tracked` |
| `build_version` | The firmware version on the device page |
| `value_json.messages` | `sensor.<feeder>_messages` |
| `aircraft` | `sensor.<feeder>_aircraft_received` and `sensor.<feeder>_aircraft_with_position` |
| `now` | `sensor.<feeder>_receiver_updated` |

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
- `http://<host>:8754/monitor.json` — the status page of `fr24feed`, when you run one.

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

Tests run with [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) and require Python 3.14 or newer on Linux or macOS; the Home Assistant test harness does not run on Windows.

```bash
pip install -r requirements_test.txt
pytest --cov
```

Releases follow the standard HACS flow: bump `version` in `manifest.json`, merge to the default branch, then publish a GitHub release with a matching tag (for example `v0.2.0` for version `0.2.0`). The release workflow verifies that the tag matches the manifest version and attaches a zip of the integration to the release.

### Disclaimer

This is an unofficial integration and is not affiliated with Flightradar24, FlightAware or Plane Finder. Use at your own risk.

---

## Nederlands

Custom integration voor [Home Assistant](https://www.home-assistant.io/) die **je eigen ADS-B-ontvanger** uitleest. Alles gebeurt op je eigen netwerk: de integratie leest de `aircraft.json` van je decoder uit en, als je die draait, de statuspagina `monitor.json` van `fr24feed` ernaast.

De integratie zit niet vast aan één netwerk. Alles wat een `aircraft.json` aanbiedt werkt, dus het maakt niet uit of je aan Flightradar24, FlightAware of Plane Finder voedt, aan meerdere tegelijk, of aan niets:

| Opstelling | Werkt | Wat je krijgt |
|---|---|---|
| readsb of tar1090 | Ja | Alle ontvanger-entiteiten, en daarvan de meeste — zie [Welke decoder](#welke-decoder) |
| dump1090-fa, PiAware of SkyAware (FlightAware) | Ja | Alle ontvanger-entiteiten |
| dump1090, dump1090-mutability | Ja | De ontvanger-entiteiten die deze build meldt |
| pfclient (Plane Finder) naast een decoder | Ja | De ontvanger-entiteiten van die decoder |
| fr24feed (Flightradar24) | Ja | De ontvanger-entiteiten **plus** de feedstatus van de feeder |

Alleen de feedstatus-entiteiten hebben `fr24feed` nodig; al het andere komt uit de decoder. De eigen client van Plane Finder wordt niet direct uitgelezen, maar pfclient draait naast een decoder, en die decoder is wat de integratie leest.

Hiermee vervang je een handvol handgeschreven `platform: rest`-sensoren door een echt apparaat, vertaalde entiteitsnamen, een configuratieflow, en cijfers die de REST-sensoren je niet konden geven: het aantal ontvangen vliegtuigen, het aantal berichten per seconde en het maximale bereik gemeten vanaf je antenne.

### Entiteiten

Alles uit `aircraft.json` — het deel dat elke opstelling krijgt:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Vliegtuigen ontvangen | Sensor | Vliegtuigen in de laatste `aircraft.json` |
| Vliegtuigen met positie | Sensor | Daarvan het aantal met een bekende positie |
| Maximaal bereik | Sensor (km) | Afstand tot het verste vliegtuig |
| Berichten per seconde | Sensor (msg/s) | Mode S-berichten per seconde, berekend tussen twee metingen |
| Dichtstbijzijnde vliegtuig | Sensor (km) | Afstand tot het dichtstbijzijnde vliegtuig, met callsign, hoogte, snelheid, koers en signaalsterkte als attributen. Een decoder met vliegtuigdatabase voegt registratie, type en een militair-markering toe |
| Hoogste vliegtuig | Sensor (ft) | Hoogte van het hoogste vliegtuig in bereik, met dezelfde attributen |
| Snelste vliegtuig | Sensor (kn) | Grondsnelheid van het snelste vliegtuig in bereik, met dezelfde attributen |
| Vliegtuigen dichtbij | Sensor | Hoeveel vliegtuigen binnen de straal "dichtbij" zitten, met ze allemaal als attributen, dichtstbijzijnde eerst |
| Vliegtuig overhead | Binary sensor | Aan zolang er minstens één vliegtuig binnen die straal zit |
| Noodsquawk | Binary sensor (veiligheid) | Aan zolang een vliegtuig in je bereik 7500, 7600 of 7700 squawkt |
| Berichten | Sensor (diagnostisch) | De totale berichtenteller van de ontvanger |
| Ontvanger bijgewerkt | Sensor (diagnostisch) | Het tijdstempel in `aircraft.json` |

Het hoogste en het snelste tellen ook vliegtuigen die nooit een positie uitzenden: hoogte en snelheid komen al via Mode S binnen, en die weglaten zou beide cijfers te laag maken. Hun attribuut `distance` is dan leeg.

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

De ontvangstcijfers komen uit het kortste meetvenster dat daadwerkelijk een signaal gemeten heeft, normaal `last1min`. Uit welk venster een waarde komt, staat als attribuut `period` op de entiteit.

Alles uit `monitor.json` — **alleen als je `fr24feed` draait**:

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
| CPU-temperatuur | Sensor (diagnostisch) | De SoC-temperatuur van de host |

Met een feeder worden de feeder en de ontvanger los van elkaar uitgelezen: als de decoder niet meer antwoordt, worden alleen de vliegtuig-entiteiten onbeschikbaar en blijven de feed-entiteiten werken. Zonder feeder is de decoder de enige bron, en neemt een storing alles mee.

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
3. Kies wat er op je station draait:
   - **Alleen een ADS-B-ontvanger** — vul het adres in van de machine waarop je decoder draait, bijvoorbeeld `192.168.5.7`. De integratie zoekt de `aircraft.json` en laat zien wat ze gevonden heeft.
   - **Flightradar24-feeder (fr24feed)** — vul het adres in van de machine waarop `fr24feed` draait en de poort van de statuspagina (standaard `8754`). De ontvanger wordt in een tweede stap gevraagd en mag leeg blijven.

Deze paden worden automatisch geprobeerd, op poort 8080 waar fr24feed en PiAware ze aanbieden en op poort 80 waar readsb met tar1090 dat doet:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

Alle kandidaten worden tegelijk geprobeerd, en de eerste in die volgorde die antwoordt wint. Staat die van jou elders, vul dan zelf de volledige URL in.

Er staan twee instellingen onder **Configureren** op de integratiepagina. De ververstijd is standaard 15 seconden; alles draait op je eigen netwerk, dus een korte tijd kan prima. De straal "dichtbij" is standaard 10 km en bepaalt wat als overhead telt voor de entiteiten **Vliegtuigen dichtbij** en **Vliegtuig overhead** — tien kilometer is ongeveer wat je kunt zien en horen, terwijl een goede ontvanger een veelvoud daarvan haalt. Station verhuisd naar een ander adres? Gebruik **Herconfigureren** in plaats van hem opnieuw toe te voegen.

Wil je `fr24feed` toevoegen aan een station dat je als alleen-ontvanger hebt ingericht, voeg dan een tweede integratie-item toe, of verwijder het item en voeg het opnieuw toe via het feeder-pad.

### De REST-sensoren vervangen

Had je een `fr24feed`-station eerder met `platform: rest`-sensoren ingericht, dan kan die YAML weg zodra de integratie draait. De vertaling is:

| REST-sensor | Entiteit |
|---|---|
| `value_json.feed_alias` | `sensor.<feeder>_feed_alias` |
| `rx_connected` | `binary_sensor.<feeder>_ontvanger` |
| `feed_status` | `binary_sensor.<feeder>_feed` en `sensor.<feeder>_feedstatus` |
| `d11_map_size` | `sensor.<feeder>_kaartgrootte` |
| `feed_num_ac_tracked` | `sensor.<feeder>_vliegtuigen_gevolgd` |
| `build_version` | De firmwareversie op de apparaatpagina |
| `value_json.messages` | `sensor.<feeder>_berichten` |
| `aircraft` | `sensor.<feeder>_vliegtuigen_ontvangen` en `sensor.<feeder>_vliegtuigen_met_positie` |
| `now` | `sensor.<feeder>_ontvanger_bijgewerkt` |

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
- `http://<host>:8754/monitor.json` — de statuspagina van `fr24feed`, als je die draait.

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

Tests draaien met [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) en vereisen Python 3.14 of nieuwer op Linux of macOS; de testharness van Home Assistant draait niet op Windows.

```bash
pip install -r requirements_test.txt
pytest --cov
```

Releases volgen de standaard HACS-werkwijze: verhoog `version` in `manifest.json`, merge naar de default branch en publiceer daarna een GitHub-release met een bijpassende tag (bijvoorbeeld `v0.2.0` voor versie `0.2.0`). De release-workflow controleert of de tag overeenkomt met de manifest-versie en voegt een zip van de integratie toe aan de release.

### Disclaimer

Dit is een onofficiële integratie en is niet gelieerd aan Flightradar24, FlightAware of Plane Finder. Gebruik op eigen risico.
