# Voorbeeldautomatiseringen

## Een vliegtuig in nood

Melding wanneer een vliegtuig in je bereik een noodsituatie meldt, op elke afstand en hoogte:

```yaml
automation:
  - alias: "ADS-B: noodgeval"
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_emergency
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "Noodgeval: {{ trigger.event.data.reason }}"
          message: >
            {{ trigger.event.data.flight or trigger.event.data.hex }}
            {%- if trigger.event.data.distance is not none %}, {{ trigger.event.data.distance }} {{ trigger.event.data.distance_unit }} verderop{% endif %}
            {%- if trigger.event.data.altitude %} op {{ trigger.event.data.altitude }} {{ trigger.event.data.altitude_unit }}{% endif %}.
```

`adsb_station_aircraft_emergency` gaat één keer per vlucht af, net als de [watchlist](watchlist.md): een toestel dat een uur in nood blijft is één bericht, en hetzelfde toestel wordt pas opnieuw gemeld na tien minuten buiten bereik, ook over een herstart van Home Assistant heen. Het event heeft dezelfde velden als de andere events, in de [eenheden](configuration.md#eenheden) die je koos, plus `reason` en `squawk`. Anders dan de binary sensor `Noodsquawk`, die maar één keer aangaat zolang er een toestel in nood is, meldt het ook een tweede.

Elk noodgeval laat ook een regel achter in **Activiteit**, ook op de apparaatpagina van het station. Passages niet: tientallen per dag zouden de rest wegdrukken, en het [passagebord](dashboards.md) heeft ze al. Elk event draagt `device_id`, het apparaat van het station, naast `entry_id` en `station`.

Liever kiezen dan typen? **Toestel in nood** is een event-entiteit op het apparaat van het station die tegelijk afgaat, zodat een automatisering er in de editor mee kan beginnen. **Watchlist** doet hetzelfde voor de watchlist. Een toestel dat al in bereik is terwijl Home Assistant opstart, staat alleen op de bus: de eerste uitlezing komt voordat de entiteiten bestaan.

`reason` is één woord, hetzelfde bij elke decoder:

| `reason` | Squawk | ADS-B-status | Betekent |
|---|---|---|---|
| `emergency` | 7700 | `general` | Een algemene noodsituatie |
| `hijack` | 7500 | `unlawful` | Kaping |
| `radio_failure` | 7600 | `nordo` | Geen radioverbinding |
| `downed` | | `downed` | Neergestort toestel |

De ADS-B-status komt van readsb en dump1090-fa; fr24feed heeft alleen de squawk. Twee statussen tellen bewust niet mee: `lifeguard`, een ambulancevlucht die voorrang vraagt, en `minfuel`, een waarschuwing voordat er een noodgeval is. Geen van beide is een toestel in nood. Squawkt zo'n toestel ook 7700, dan telt het wel.

Er is geen event voor het einde van een noodgeval: een toestel dat uit je bereik vliegt, is niet te onderscheiden van een toestel waarvan de nood voorbij is.

Melding wanneer er iets overkomt, met wat het is en waar het heen gaat:

```yaml
automation:
  - alias: "ADS-B: vliegtuig overhead"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_vliegtuig_overhead
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {% set overhead = 'binary_sensor.ads_b_station_vliegtuig_overhead' %}
            {% set plane = state_attr(overhead, 'aircraft')[0] %}
            {{ plane.airline | default(plane.flight or 'Een onbekend vliegtuig') }}
            overhead op {{ plane.altitude }} {{ state_attr(overhead, 'altitude_unit') }}
            {%- if plane.description is defined %},
            een {{ plane.description }}
            {%- endif %}
            {%- if plane.vertical_rate %},
            {{ 'stijgend' if plane.vertical_rate > 0 else 'dalend' }} met
            {{ plane.vertical_rate | abs }} {{ state_attr(overhead, 'vertical_rate_unit') }}
            {%- endif %}
            {%- if plane.origin_location is defined %},
            {{ plane.origin_location }} naar {{ plane.destination_location }}
            {%- endif %}.
```

Wat er zo uitkomt: *"Lufthansa overhead op 4100 ft, een Airbus A-320neo, dalend met 1088 ft/min, Parijs naar Amsterdam."*

Alle vier zijn sleutels die kunnen ontbreken, elk om een eigen reden, en daarom vraagt de template ernaar in plaats van ze te lezen. De maatschappij en de typenaam staan er voor de vluchten die de [meegeleverde tabellen](decoders.md#namen-bij-de-codes) herkennen, dus een zakenjet onder zijn registratie valt terug op de callsign. De stijgsnelheid ontbreekt bij vliegtuigen aan de grond en is nul in horizontale vlucht, waar niets zeggen beter is dan "stijgend met 0". De route heeft een [bron nodig](routes.md) en staat er alleen bij voor de vluchten die hij kent.

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

De entity-ID's hierboven volgen de apparaatnaam: `ads_b_station` voor een station zonder feeder, je feed-alias voor een station met. Die apparaatnaam wordt niet vertaald, de entiteitsnaam erachter wel, dus noem je het apparaat in Home Assistant anders, dan veranderen de entity-ID's mee.

Hardop aankondigen wat er overkomt, maar alleen als er iemand thuis is om het te horen:

```yaml
automation:
  - alias: Aankondigen wat er overkomt
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_passage
    conditions:
      - condition: state
        entity_id: person.jij
        state: home
    actions:
      - action: tts.speak
        target:
          entity_id: tts.piper
        data:
          media_player_entity_id: media_player.keuken
          message: >
            {{ trigger.event.data.airline or trigger.event.data.flight or 'Een vliegtuig' }}
            komt over op {{ trigger.event.data.altitude }} {{ trigger.event.data.altitude_unit }}
            {%- if trigger.event.data.route %}, {{ trigger.event.data.route }}{% endif %}.
```

Geen eigen cooldown: een toestel dat in beeld blijft is één passage en één event, en hetzelfde toestel dat terugkomt is pas na tien minuten een tweede. Dat is de [passagegap](passages.md) die het werk doet waar je anders een template voor zou schrijven.

Of zeg het *voordat* hij er is, via dezelfde speaker:

```yaml
automation:
  - alias: Aankondigen wat eraan komt
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_approaching
    conditions:
      - condition: state
        entity_id: person.jij
        state: home
    actions:
      - action: tts.speak
        target:
          entity_id: tts.piper
        data:
          media_player_entity_id: media_player.keuken
          message: >
            {{ trigger.event.data.airline or trigger.event.data.flight or 'Er' }}
            komt over ongeveer {{ (trigger.event.data.seconds_to_closest / 60) | round }} minuten
            op {{ trigger.event.data.closest_passing_distance }} {{ trigger.event.data.distance_unit }} langs.
```

Melding als er iets van je [watchlist](watchlist.md) opduikt, waar het ook is:

```yaml
automation:
  - alias: Watchlist
    triggers:
      - trigger: event
        event_type: adsb_station_watchlist_match
    actions:
      - action: adsb_station.speak
        data:
          question: aircraft
          aircraft: "{{ trigger.event.data.hex }}"
        response_variable: spoken
      - action: notify.mobile_app_telefoon
        data:
          title: "{{ trigger.event.data.watching }} is in de lucht"
          message: "{{ spoken.speech }}"
```

[`adsb_station.speak`](voice.md) schrijft de zin, in jouw taal en eenheden: wat het is, waar, hoe hoog, en de route als die bekend is.

Melding wanneer de ontvanger niets meer hoort, wat na een herstart meestal betekent dat de dongle er even uit en weer in moet:

```yaml
automation:
  - alias: "ADS-B: ontvanger stil"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_ontvanger_stil
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            De ADS-B-dongle levert al drie minuten niets.
            Trek de dongle eruit en steek hem er weer in.
```

## Een nieuw record

Een melding als een vliegtuig het verste, hoogste of snelste is dat je station ooit gehoord heeft:

```yaml
automation:
  - alias: "ADS-B: nieuw record"
    triggers:
      - trigger: event
        event_type: adsb_station_record_broken
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "Nieuw record: {{ trigger.event.data.record }}"
          message: >
            {{ trigger.event.data.flight or trigger.event.data.hex }}:
            {%- if trigger.event.data.record == 'range' %} {{ trigger.event.data.distance }} {{ trigger.event.data.distance_unit }}
            {%- elif trigger.event.data.record == 'altitude' %} {{ trigger.event.data.altitude }} {{ trigger.event.data.altitude_unit }}
            {%- else %} {{ trigger.event.data.speed }} {{ trigger.event.data.speed_unit }}{% endif %}.
```

`adsb_station_record_broken` gaat één keer per vlucht af, zodra het vliegtuig het record vijf minuten niet verbeterd heeft, of weg is: een verkeersvliegtuig dat voorbij het hoogterecord klimt is één melding, met de hoogte waarop het uitvlakte. Een grondsnelheid schommelt een paar knopen, dus hetzelfde vliegtuig verbetert zijn eigen record vaak later nog een beetje; de sensor volgt dat, zonder nieuwe melding. `record` zegt welk record, `range`, `altitude` of `speed`, en de velden zijn die van de andere events, in de [eenheden](configuration.md#eenheden) die je koos, zoals het vliegtuig was toen het het record zette. `previous` bevat het record dat het verbeterde: dezelfde waarde, `flight`, `hex` en `recorded_at`.

De eerste dag nadat het station is toegevoegd, of na **Records wissen**, blijft stil: dan verbetert bijna elk vliegtuig het vorige, en worden de records alleen verzameld. **Records** is de event-entiteit voor de editor, en elk record laat een regel achter in **Activiteit**.

## Een nieuw toestel

Een melding als het station een type hoort dat het nog nooit gehoord heeft, bijvoorbeeld een eerste A380:

```yaml
automation:
  - alias: "ADS-B: eerste van dit type"
    triggers:
      - trigger: event
        event_type: adsb_station_new_aircraft
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.first_of_type }}"
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "Eerste {{ trigger.event.data.aircraft_type }}"
          message: >
            {{ trigger.event.data.description or trigger.event.data.aircraft_type }},
            {{ trigger.event.data.registration or trigger.event.data.hex }}
            {%- if trigger.event.data.flight %} als {{ trigger.event.data.flight }}{% endif %}.
```

`adsb_station_new_aircraft` gaat af voor elk toestel dat het station nog nooit gehoord heeft, op zijn ICAO-adres, met de velden van de andere events en twee eigen: `first_of_type`, het eerste van zijn type, en `first_of_airline`, de eerste vlucht van een bekende maatschappij. Een type vraagt een decoder met een vliegtuigdatabase, of de [gedownloade](decoders.md#de-vliegtuigdatabase).

Nieuwe toestellen blijven maandenlang komen, in het begin tientallen per dag, dus dit event blijft alleen op de bus, net als de passages, en laat geen regel achter in **Activiteit**. Meestal wil je een voorwaarde zoals `first_of_type`. De eerste week nadat het station is toegevoegd blijft stil: dan is bijna elk toestel nieuw, en verzamelt het station alleen.

**Ooit gehoorde toestellen** telt ze. Ze staan in een eigen bestand onder `.storage`, zo'n 30 bytes per toestel: een jaar van een druk station is een of twee megabyte. Het wordt hooguit elk kwartier geschreven, en als Home Assistant stopt, om een SD-kaart te sparen. Een toestel dat een jaar niet gehoord is, wordt vergeten en is dan weer nieuw.

## Het beste van vandaag

**Maximaal bereik**, **Hoogste vliegtuig** en **Snelste vliegtuig** houden langetermijnstatistieken bij, dus een [statistiekkaart](https://www.home-assistant.io/dashboards/statistic/) toont het beste van elke dag zonder eigen sensor:

```yaml
type: statistic
entity: sensor.ads_b_station_highest_aircraft
name: Hoogste vandaag
period:
  calendar:
    period: day
stat_type: max
```

Zet `period` op `week` of `month` voor het beste daarvan.

## Een automatisering uitproberen

Je hoeft niet op een vliegtuig te wachten: vuur onder **Ontwikkelhulpmiddelen → Gebeurtenissen** `adsb_station_aircraft_emergency` af, of een ander event van hier, met eigen gegevens:

```yaml
flight: TEST1
reason: emergency
squawk: "7700"
distance: 12.3
distance_unit: km
altitude: 900
altitude_unit: m
```

Elke automatisering op dat event draait, dus de melding gaat echt uit, en de watchlist-, nood- en recordevents laten ook een regel achter in **Activiteit**.
