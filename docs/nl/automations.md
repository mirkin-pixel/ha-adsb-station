# Voorbeeldautomatiseringen

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
            {% set plane = state_attr(
                 'binary_sensor.ads_b_station_vliegtuig_overhead',
                 'aircraft')[0] %}
            {{ plane.airline | default(plane.flight or 'Een onbekend vliegtuig') }}
            overhead op {{ plane.altitude }} ft
            {%- if plane.description is defined %},
            een {{ plane.description }}
            {%- endif %}
            {%- if plane.vertical_rate %},
            {{ 'stijgend' if plane.vertical_rate > 0 else 'dalend' }} met
            {{ plane.vertical_rate | abs }} ft/min
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
            komt over op {{ trigger.event.data.altitude }} voet
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
            op {{ trigger.event.data.closest_passing_distance }} kilometer langs.
```

Melding als er iets van je [watchlist](watchlist.md) opduikt, waar het ook is:

```yaml
automation:
  - alias: Watchlist
    triggers:
      - trigger: event
        event_type: adsb_station_watchlist_match
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "{{ trigger.event.data.watching }} is in de lucht"
          message: >
            {{ trigger.event.data.flight or trigger.event.data.hex }},
            {{ trigger.event.data.distance }} km ver
            {%- if trigger.event.data.altitude %} op {{ trigger.event.data.altitude }} voet{% endif %}.
```
