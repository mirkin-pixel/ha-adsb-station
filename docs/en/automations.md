# Example automations

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

Notification when something goes over, saying what it is and where it is headed:

```yaml
automation:
  - alias: "ADS-B: aircraft overhead"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_aircraft_overhead
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {% set plane = state_attr(
                 'binary_sensor.ads_b_station_aircraft_overhead',
                 'aircraft')[0] %}
            {{ plane.airline | default(plane.flight or 'An unknown aircraft') }}
            overhead at {{ plane.altitude }} ft
            {%- if plane.description is defined %},
            {{ plane.description }}
            {%- endif %}
            {%- if plane.vertical_rate %},
            {{ 'climbing' if plane.vertical_rate > 0 else 'descending' }}
            {{ plane.vertical_rate | abs }} ft/min
            {%- endif %}
            {%- if plane.origin_location is defined %},
            {{ plane.origin_location }} to {{ plane.destination_location }}
            {%- endif %}.
```

Which reads as *"Lufthansa overhead at 4100 ft, Airbus A-320neo, descending 1088 ft/min, Paris to Amsterdam."*

Every one of those four is a key that can be missing, and each for its own reason, which is why the template asks rather than reads. The airline and the type name are there for the flights the [shipped tables](decoders.md#names-for-the-codes) recognise, so a business jet under its registration falls back to the callsign. The rate of climb is absent from aircraft on the ground and zero in level flight, where saying nothing is better than saying "climbing 0". The route needs a [source configured](routes.md) and is only there for the flights it knows.

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

Announce it out loud when something comes over, but only while somebody is in to hear it:

```yaml
automation:
  - alias: Announce what is overhead
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_passage
    conditions:
      - condition: state
        entity_id: person.you
        state: home
    actions:
      - action: tts.speak
        target:
          entity_id: tts.piper
        data:
          media_player_entity_id: media_player.kitchen
          message: >
            {{ trigger.event.data.airline or trigger.event.data.flight or 'An aircraft' }}
            overhead at {{ trigger.event.data.altitude }} feet
            {%- if trigger.event.data.route %}, {{ trigger.event.data.route }}{% endif %}.
```

No cooldown of its own: an aircraft that stays in view is one passage and one event, and the same aircraft coming back is a second one only after ten minutes. That is the [passage gap](passages.md) doing the work a template would otherwise be written for.

Say it *before* it arrives instead, using the same speaker:

```yaml
automation:
  - alias: Announce what is coming
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_approaching
    conditions:
      - condition: state
        entity_id: person.you
        state: home
    actions:
      - action: tts.speak
        target:
          entity_id: tts.piper
        data:
          media_player_entity_id: media_player.kitchen
          message: >
            {{ trigger.event.data.airline or trigger.event.data.flight or 'Something' }}
            passes {{ trigger.event.data.closest_passing_distance }} kilometres out
            in about {{ (trigger.event.data.seconds_to_closest / 60) | round }} minutes.
```

Notification when something on your [watchlist](watchlist.md) turns up, wherever it is:

```yaml
automation:
  - alias: Watchlist
    triggers:
      - trigger: event
        event_type: adsb_station_watchlist_match
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "{{ trigger.event.data.watching }} is up"
          message: >
            {{ trigger.event.data.flight or trigger.event.data.hex }},
            {{ trigger.event.data.distance }} km away
            {%- if trigger.event.data.altitude %} at {{ trigger.event.data.altitude }} feet{% endif %}.
```
