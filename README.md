# ADS-B Station for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/mirkin-pixel/ha-adsb-station?style=for-the-badge)](https://github.com/mirkin-pixel/ha-adsb-station/releases)

[English](#english) | [Nederlands](#nederlands)

---

## English

Custom integration for [Home Assistant](https://www.home-assistant.io/) that reads **your own ADS-B receiver**. Everything happens on your own network: the integration polls the `aircraft.json` of your decoder and, if you run one, the `monitor.json` status page of `fr24feed` next to it. There is one exception, it is off unless you turn it on, and it has a section of its own: [where a flight is going](docs/en/routes.md) is the one thing your antenna cannot hear.

It is not tied to a single network. Anything that serves an `aircraft.json` works, so it does not matter whether you feed Flightradar24, FlightAware, Plane Finder, several of them at once, or nothing at all:

| Decoder | What you get |
|---|---|
| readsb or tar1090 | Every receiver entity, and the most of them; see [Which decoder](docs/en/decoders.md) |
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

### Documentation

Everything else lives in [`docs/en`](docs/en), a page at a time:

| | |
|---|---|
| [Entities](docs/en/entities.md) | Every entity, what it means and where it comes from |
| [Feeders](docs/en/feeders.md) | What each feeder adds, and where your antenna is blocked |
| [Which decoder](docs/en/decoders.md) | What each decoder can tell you, the aircraft database, and the names this integration ships |
| [Configuration](docs/en/configuration.md) | Setting a station up, and what counts as overhead |
| [Where a flight is going](docs/en/routes.md) | The one figure that cannot come off your own network |
| [When something comes over](docs/en/passages.md) | Passages, the board, and seeing an aircraft coming before it is here |
| [A list worth watching](docs/en/watchlist.md) | Aircraft worth knowing about whenever they turn up |
| [Asking a question](docs/en/services.md) | The actions that answer, with response data |
| [Asking out loud](docs/en/voice.md) | Five questions for Assist, answered from your own roof |
| [Dashboards](docs/en/dashboards.md) | Cards to build out of all this, including the map |
| [Example automations](docs/en/automations.md) | Notifications, announcements and what to trigger on |
| [About the endpoints](docs/en/endpoints.md) | What is read, how often, and what it costs |
| [Troubleshooting](docs/en/troubleshooting.md) | When something is not there |

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

Custom integration voor [Home Assistant](https://www.home-assistant.io/) die **je eigen ADS-B-ontvanger** uitleest. Alles gebeurt op je eigen netwerk: de integratie leest de `aircraft.json` van je decoder uit en, als je die draait, de statuspagina `monitor.json` van `fr24feed` ernaast. Er is één uitzondering, die staat uit tenzij je hem aanzet, en die heeft een eigen hoofdstuk: [waar een vlucht heen gaat](docs/nl/routes.md) is het enige wat je antenne niet kan horen.

De integratie zit niet vast aan één netwerk. Alles wat een `aircraft.json` aanbiedt werkt, dus het maakt niet uit of je aan Flightradar24, FlightAware of Plane Finder voedt, aan meerdere tegelijk, of aan niets:

| Decoder | Wat je krijgt |
|---|---|
| readsb of tar1090 | Alle ontvanger-entiteiten, en daarvan de meeste; zie [Welke decoder](docs/nl/decoders.md) |
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

### Documentatie

Al het andere staat in [`docs/nl`](docs/nl), één pagina per onderwerp:

| | |
|---|---|
| [Entiteiten](docs/nl/entities.md) | Elke entiteit, wat hij betekent en waar hij vandaan komt |
| [Feeders](docs/nl/feeders.md) | Wat elke feeder toevoegt, en waar je antenne geblokkeerd zit |
| [Welke decoder](docs/nl/decoders.md) | Wat elke decoder kan vertellen, de vliegtuigdatabase, en de namen die meegeleverd worden |
| [Configuratie](docs/nl/configuration.md) | Een station opzetten, en wat overhead precies betekent |
| [Waar een vlucht heen gaat](docs/nl/routes.md) | Het enige cijfer dat niet van je eigen netwerk kan komen |
| [Als er iets overkomt](docs/nl/passages.md) | Passages, het bord, en een toestel zien aankomen voordat het er is |
| [Een lijst om in de gaten te houden](docs/nl/watchlist.md) | Toestellen die je wilt weten zodra ze opduiken |
| [Iets vragen](docs/nl/services.md) | De acties die antwoorden, met antwoordgegevens |
| [Hardop vragen](docs/nl/voice.md) | Vijf vragen voor Assist, beantwoord vanaf je eigen dak |
| [Dashboards](docs/nl/dashboards.md) | Kaarten om dit alles mee te bouwen, inclusief de kaart |
| [Voorbeeldautomatiseringen](docs/nl/automations.md) | Meldingen, aankondigingen en waarop je triggert |
| [Over de endpoints](docs/nl/endpoints.md) | Wat er gelezen wordt, hoe vaak, en wat het kost |
| [Problemen oplossen](docs/nl/troubleshooting.md) | Als er iets niet is |

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

### Ontwikkeling

Werken aan de integratie zelf staat in [CONTRIBUTING.md](CONTRIBUTING.md) (Engels): hoe je het opzet, de drie controles die alles zijn wat CI je over de code kan vertellen, hoe de code is ingedeeld en hoe een release eruit gaat. Je hebt Python 3.14 of nieuwer nodig en verder niets: geen eigen Home Assistant-installatie.

```bash
pip install -r requirements_test.txt
scripts/check.sh          # of scripts\check.ps1
```

### Disclaimer

Dit is een onofficiële integratie en is niet gelieerd aan Flightradar24, FlightAware of Plane Finder. Gebruik op eigen risico.
