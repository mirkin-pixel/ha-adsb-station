# Dashboards

## Vliegtuigen op de kaart

Zet **Vliegtuigen op de kaart** aan onder **Configureren** en elk toestel binnen de nabijheidsstraal krijgt een eigen entiteit, getekend waar het is, zolang het er is. Er wordt niets extra's voor gelezen: de posities zitten al in elke poll, naast de afstanden waar de nabijheidssensoren op gebouwd zijn.

Eén kaartkaart laat ze allemaal zien:

```yaml
type: map
geo_location_sources:
  - adsb_station
hours_to_show: 0
```

Die `hours_to_show: 0` is het overwegen waard. Alles daarboven tekent een spoor uit de recorder, en deze entiteiten worden daar niet in bewaard.

Dat is precies de afweging die deze optie maakt, en die is het waard om te kennen voor je hem aanzet. **Deze vliegtuigen worden bewust niet geregistreerd.** Ze bestaan zolang ze boven je zijn en zijn weg zodra ze zijn doorgevlogen, dus een week verkeer laat niets achter — geen duizenden entiteiten in je registratie, geen `unavailable` toestellen die na elke herstart terugkomen, niets om op te ruimen. Daar staat tegenover dat je ze niet kunt hernoemen, verbergen of aan een gebied koppelen vanuit de interface, dat ze niet onder het apparaat van je station staan, en dat hun attributen buiten de recorder blijven. Hun entity-id's worden ook hergebruikt: `geo_location.klm123` is volgende week een andere vlucht onder dezelfde naam. Voor de geschiedenis is er het passagebord en het [passage-event](passages.md), en die zijn er wél op gebouwd.

Elk toestel heet naar zijn callsign, of naar zijn hexcode als hij er nog geen heeft gestuurd, en die naam ligt vast op het moment dat hij verschijnt. Een callsign komt vaak een paar polls later binnen, en hernoemen zou dan het entity-id middenin een passage onder je dashboard vandaan trekken.

Hoeveel het er zijn is wat je straal toelaat — bij de standaard tien kilometer meestal nul tot een handvol. Kies je een ruime straal en wil je ze liever helemaal niet in je database, sluit ze dan in één keer uit:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```

## Een bord van wat er overkwam

Het passagebord is een lijst in een attribuut, dus een markdown-kaart maakt er iets leesbaars van:

```yaml
type: markdown
content: |
  {% for passage in state_attr('sensor.jouw_station_passages_vandaag', 'passages') %}
  **{{ passage.flight or passage.hex }}**{% if passage.airline %} · {{ passage.airline }}{% endif %}
  {{ as_timestamp(passage.at) | timestamp_custom('%H:%M') }} · {{ passage.distance }} km · {{ passage.altitude }} ft
  {% endfor %}
```

## Alleen als het ertoe doet

Een conditionele kaart houdt de stille dingen uit beeld tot ze niet stil meer zijn:

```yaml
type: conditional
conditions:
  - condition: state
    entity: binary_sensor.jouw_station_noodsquawk
    state: "on"
card:
  type: entities
  entities:
    - binary_sensor.jouw_station_noodsquawk
```

Dezelfde vorm werkt voor **Watchlist in bereik**, die per ontwerp meestal uit staat.

## Een vlag, en een logo als je dat wilt

Twee attributen bestaan om dingen mee op te zoeken. `country` is de tweeletterige code waar een vlagemoji uit opgebouwd wordt, en `airline_code` is de drie letters waar een logobestand naar heet:

```yaml
type: markdown
content: |
  {% set toestel = 'sensor.jouw_station_dichtstbijzijnde_vliegtuig' %}
  {% set land = state_attr(toestel, 'country') %}
  {% if land %}{{ land | list | map('ord') | map('add', 127397) | map('char') | join }} {% endif %}
  {{ state_attr(toestel, 'airline') or state_attr(toestel, 'hex') }}
```

De vlag wordt uit de code zelf opgebouwd en kost niets. **Een maatschappijlogo is een verzoek dat je netwerk verlaat**, precies het enige wat deze integratie verder nooit doet, dus dat is jouw keuze en geen standaard: richt een afbeelding op de logodienst die je vertrouwt, of zet de bestanden zelf in `www/airline_logos/`.

## Chips voor wat er hangt

Met [Mushroom](https://github.com/piitaya/lovelace-mushroom) geïnstalleerd leest een rij template-chips in één oogopslag. De emittercategorie is wat helikopters en drones een eigen chip geeft:

```yaml
type: custom:mushroom-chips-card
chips:
  - type: template
    entity: sensor.jouw_station_vliegtuigen_dichtbij
    icon: mdi:airplane
    content: "{{ states('sensor.jouw_station_vliegtuigen_dichtbij') }}"
  - type: template
    entity: sensor.jouw_station_vliegtuigen_dichtbij
    icon: mdi:helicopter
    content: >
      {{ state_attr('sensor.jouw_station_vliegtuigen_dichtbij', 'aircraft')
         | selectattr('category', 'defined')
         | selectattr('category', 'eq', 'A7') | list | count }}
```

## De Flightradar24-kaart, op je eigen data

[`Springvar/home-assistant-flightradar24-card`](https://github.com/Springvar/home-assistant-flightradar24-card) is een volwaardige interactieve kaart, en hij zit hardgecodeerd vast aan de attribuutnamen van de FR24-integratie. Een template-sensor zet ons `aircraft`-attribuut om naar de vorm die hij verwacht, en dan draait hij op toestellen die je eigen antenne hoorde:

```yaml
template:
  - sensor:
      - name: ADS-B voor de FR24-kaart
        state: "{{ state_attr('sensor.jouw_station_vliegtuigen_dichtbij', 'aircraft') | count }}"
        attributes:
          flights: >
            {% set out = namespace(flights=[]) %}
            {% for plane in state_attr('sensor.jouw_station_vliegtuigen_dichtbij', 'aircraft') %}
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

De laatste twee sleutels staan er bij toestellen die [jouw kant op komen](passages.md#voordat-het-er-is) en bij de rest niet, en dat is ook wat de kaart ermee doet. De kaart wil daarnaast een positie per vlucht; daarvoor moet de kaartoptie aan, want de vliegtuigentiteiten zijn de enige plek waar de posities gepubliceerd worden.

## De database erbuiten houden

De lijsten die deze kaarten lezen zijn attributen, en de zware houdt de integratie zelf al uit de recorder. De kaartentiteiten zijn de uitzondering die een eigen regel verdient als je een ruime straal draait:

```yaml
recorder:
  exclude:
    entity_globs:
      - geo_location.*
```
