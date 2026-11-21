# ADS-B Station for Home Assistant

**See what your own antenna hears, in Home Assistant. No cloud, no account, no API key.**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../images/card-map-dark.png">
  <img src="../images/card-map-light.png" alt="The station card on a map: aircraft around a station between Schiphol and Utrecht, each in the colour of its height with the trail of the last five minutes, a KLM Boeing 737-800 overhead on its way in to Schiphol, a Transavia tapped with its route and where it passes closest, the aircraft nearby, and the station's figures as badges on top" width="640">
</picture>

ADS-B Station reads the ADS-B receiver you run yourself, on your own network, and keeps working when the internet is down. It does not matter which network you feed, or whether you feed one at all.

## What you get

- **Sensors for your station**: aircraft received, message rate, signal and noise, the closest, highest and fastest aircraft, range records in eight directions, and the feed status of each network.
- **A dashboard card** with a radar or a map, trails, routes and photos, the aircraft nearby and a board of what came over.
- **Events to automate on**: an aircraft about to come over, one on your watchlist, one in distress, a new record.
- **Questions out loud**: ten for Assist, and the same as tools for an AI assistant.
- **Local by default**: routes and photos are the only things fetched from the internet, and only once you switch them on.

## Get started

You need Home Assistant 2025.7 or newer, and a decoder that serves an `aircraft.json` on your network: readsb, dump1090-fa, or the one inside fr24feed.

1. **Install.** Open the repository in the Marketplace (HACS before Home Assistant 2026.11) and click **Download**, then restart when Home Assistant asks.

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mirkin-pixel&repository=ha-adsb-station)

2. **Add your station.** Under **Settings → Devices & services → Add integration**, choose **ADS-B Station** and type the address of your receiver. The decoder and the feeders are found for you: one click adds the first, and the others wait under **Discovered** for a click each; see [Configuration](configuration.md).
3. **Put the card on a dashboard.** Edit a dashboard, add a card and pick **ADS-B Station**; see [Dashboards](dashboards.md).

No Marketplace? Copy `custom_components/adsb_station` into the `custom_components` folder of your configuration and restart.

## Documentation

| | |
|---|---|
| [Entities](entities.md) | Every entity, what it means and where it comes from |
| [Feeders](feeders.md) | What each feeder adds, and where your antenna is blocked |
| [Which decoder](decoders.md) | What each decoder can tell you, the aircraft database, and the names this integration ships |
| [Configuration](configuration.md) | Setting a station up, its options, and what counts as overhead |
| [Where a flight is going](routes.md) | A figure that cannot come off your own network |
| [What it looks like](photos.md) | A photo of each aircraft, credited as the photographer asks |
| [When something comes over](passages.md) | Passages, the board, and seeing an aircraft coming before it is here |
| [A list worth watching](watchlist.md) | Aircraft worth knowing about whenever they turn up |
| [Asking a question](services.md) | The actions that answer, with response data |
| [Asking out loud](voice.md) | Ten questions for Assist, and tools for AI assistants, answered from your own roof |
| [Dashboards](dashboards.md) | The card that comes with the integration, and others to build |
| [Example automations](automations.md) | Notifications, announcements and what to trigger on |
| [About the endpoints](endpoints.md) | What is read, how often, and what it costs |
| [Troubleshooting](troubleshooting.md) | When something is not there, what it cannot do, and removing it |

## Languages

The integration speaks English and Dutch: the entity names and the setup, and the answers it gives out loud. Home Assistant shows English for any other language. A translation is welcome; [offer one here](https://github.com/mirkin-pixel/ha-adsb-station/issues/new?template=new_language.yml).

## Upgrading

From 1.0 on, an upgrade within the same major version does not break what you built on it: entity IDs and their history, attributes, actions and their responses, and events stay as they are. What exactly is promised is in [CONTRIBUTING.md](../../CONTRIBUTING.md#what-a-version-number-promises). An update asks for a restart; reload the browser afterwards so the cards are the new ones too.
