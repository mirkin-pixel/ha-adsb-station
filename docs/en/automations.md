# Example automations

## An aircraft in distress

Notification when an aircraft in range declares an emergency, at any distance or height:

```yaml
automation:
  - alias: "ADS-B: emergency"
    triggers:
      - trigger: event
        event_type: adsb_station_aircraft_emergency
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "Emergency: {{ trigger.event.data.reason }}"
          message: >
            {{ trigger.event.data.flight or trigger.event.data.hex }}
            {%- if trigger.event.data.distance is not none %}, {{ trigger.event.data.distance }} km away{% endif %}
            {%- if trigger.event.data.altitude %} at {{ trigger.event.data.altitude }} feet{% endif %}.
```

`adsb_station_aircraft_emergency` fires once per flight, like the [watchlist](watchlist.md): an aircraft that stays in distress for an hour is one message, and the same aircraft is announced again only after ten minutes out of range. It carries the same fields as the other events, with the distance in kilometres, plus `reason` and `squawk`. Unlike the `Emergency squawk` binary sensor, which only turns on once while any aircraft is in distress, it also tells you about a second one.

Each one also leaves a line in **Activity**, on the station's device page as well. Passages do not: dozens a day would bury the rest, and the [passage board](dashboards.md) has them. Every event carries `device_id`, the station's device, beside `entry_id` and `station`.

`reason` is one word, the same whichever decoder you run:

| `reason` | Squawk | ADS-B status | Means |
|---|---|---|---|
| `emergency` | 7700 | `general` | A general emergency |
| `hijack` | 7500 | `unlawful` | Unlawful interference |
| `radio_failure` | 7600 | `nordo` | Lost radio contact |
| `downed` | | `downed` | Downed aircraft |

The ADS-B status comes from readsb and dump1090-fa; fr24feed only has the squawk. Two statuses are left out on purpose: `lifeguard`, an ambulance flight asking for priority, and `minfuel`, a warning before any emergency. Neither is an aircraft in distress. One that also squawks 7700 still counts.

There is no event for the end of an emergency: an aircraft that leaves your range cannot be told from one whose emergency is over.

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
            {{ trigger.event.data.flight or trigger.event.data.hex }}
            {%- if trigger.event.data.distance is not none %}, {{ trigger.event.data.distance }} km away{% endif %}
            {%- if trigger.event.data.altitude %} at {{ trigger.event.data.altitude }} feet{% endif %}.
```

Notification when the receiver stops hearing anything, which after a reboot usually means the dongle wants plugging back in:

```yaml
automation:
  - alias: "ADS-B: receiver silent"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_receiver_silent
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            The ADS-B dongle has delivered nothing for three minutes.
            Unplug the dongle and plug it back in.
```
