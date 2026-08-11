# Dashboards

## Aircraft on the map

Switch **Aircraft on the map** on under **Configure** and every aircraft inside the nearby radius gets an entity of its own, drawn where it is, for as long as it is there. Nothing extra is read to do it: the positions are in every poll already, next to the distances the proximity sensors are built on.

A map card shows them all:

```yaml
type: map
geo_location_sources:
  - adsb_station
hours_to_show: 0
```

`hours_to_show: 0` is worth having. Anything higher draws a trail from the recorder, and these entities are not kept there.

That is the trade this option makes, and it is worth understanding before you turn it on. **These aircraft are deliberately not registered.** They exist while they are overhead and are gone the moment they fly on, so a week of traffic leaves nothing behind — no thousands of entities in your registry, no `unavailable` aircraft coming back after every restart, nothing to clean up. In exchange they cannot be renamed, hidden or given an area from the interface, they are not listed under the station's device, and their attributes are kept out of the recorder. Their entity IDs are reused, too: `geo_location.klm123` next week is a different flight under the same name. For history there is the passage board and the [passage event](passages.md), which are built to be kept.

Each aircraft is named after its callsign, or its hex code when it has not sent one yet, and that name is fixed the moment it appears. A callsign often arrives a few polls late, and renaming then would move the entity ID out from under your dashboard halfway through a passage.

How many there are is whatever your radius holds — usually nought to a handful at the default ten kilometres. If you set a wide radius and would rather your database not see them at all, exclude them wholesale:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```

## A board of what came over

The passage board is a list in an attribute, so a markdown card turns it into something to read:

```yaml
type: markdown
content: |
  {% for passage in state_attr('sensor.your_station_passages_today', 'passages') %}
  **{{ passage.flight or passage.hex }}**{% if passage.airline %} · {{ passage.airline }}{% endif %}
  {{ as_timestamp(passage.at) | timestamp_custom('%H:%M') }} · {{ passage.distance }} km · {{ passage.altitude }} ft
  {% endfor %}
```

## Only when it matters

A conditional card keeps the quiet things out of sight until they are not quiet:

```yaml
type: conditional
conditions:
  - condition: state
    entity: binary_sensor.your_station_emergency_squawk
    state: "on"
card:
  type: entities
  entities:
    - binary_sensor.your_station_emergency_squawk
```

The same shape works for **Watchlist in range**, which is off most of the time by design.

## A flag, and a logo if you want one

Two attributes exist to look things up by. `country` is the two-letter code a flag emoji is built out of, and `airline_code` is the three letters a logo file is named after:

```yaml
type: markdown
content: |
  {% set aircraft = 'sensor.your_station_closest_aircraft' %}
  {% set country = state_attr(aircraft, 'country') %}
  {% if country %}{{ country | list | map('ord') | map('add', 127397) | map('char') | join }} {% endif %}
  {{ state_attr(aircraft, 'airline') or state_attr(aircraft, 'hex') }}
```

The flag is built out of the code itself and costs nothing. **An airline logo is a request leaving your network**, which is the one thing this integration otherwise never does, so that is your call rather than a default: point an image at whichever logo service you are willing to talk to, or drop the files into `www/airline_logos/` and serve them yourself.

## Chips for what is up there

With [Mushroom](https://github.com/piitaya/lovelace-mushroom) installed, a row of template chips reads at a glance. The emitter category is what gives helicopters and drones a chip of their own:

```yaml
type: custom:mushroom-chips-card
chips:
  - type: template
    entity: sensor.your_station_aircraft_nearby
    icon: mdi:airplane
    content: "{{ states('sensor.your_station_aircraft_nearby') }}"
  - type: template
    entity: sensor.your_station_aircraft_nearby
    icon: mdi:helicopter
    content: >
      {{ state_attr('sensor.your_station_aircraft_nearby', 'aircraft')
         | selectattr('category', 'defined')
         | selectattr('category', 'eq', 'A7') | list | count }}
```

## The Flightradar24 card, on your own data

[`Springvar/home-assistant-flightradar24-card`](https://github.com/Springvar/home-assistant-flightradar24-card) is a full interactive card, and it is hard-coded to the attribute names of the FR24 integration. A template sensor turns our `aircraft` attribute into the shape it expects, and then it runs on aircraft your own antenna heard:

```yaml
template:
  - sensor:
      - name: ADS-B for the FR24 card
        state: "{{ state_attr('sensor.your_station_aircraft_nearby', 'aircraft') | count }}"
        attributes:
          flights: >
            {% set out = namespace(flights=[]) %}
            {% for plane in state_attr('sensor.your_station_aircraft_nearby', 'aircraft') %}
              {% set out.flights = out.flights + [{
                'callsign': plane.flight,
                'flight_number': plane.flight,
                'aircraft_registration': plane.registration,
                'aircraft_model': plane.description,
                'aircraft_code': plane.aircraft_type,
                'airline_short': plane.airline,
                'altitude': plane.altitude,
                'ground_speed': plane.speed,
                'vertical_speed': plane.vertical_rate,
                'heading': plane.track,
                'distance_to_tracker': plane.distance,
                'closest_passing_distance': plane.closest_passing_distance,
                'eta_to_closest_distance': plane.seconds_to_closest,
              }] %}
            {% endfor %}
            {{ out.flights }}
```

The last two keys are filled in for aircraft that are [coming your way](passages.md#before-it-gets-here) and absent for the rest, which is what the card does with them anyway. The card also wants a position per flight; that means switching the map on, since the aircraft entities are the only place the positions are published.

## Keeping the database out of it

The lists these cards read are attributes, and the heavy ones are already kept out of the recorder by the integration itself. The map entities are the exception worth a rule of your own if you run a wide radius:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```
