# When something comes over

**Aircraft overhead** answers one question, and it answers it well: is there anything up there. It cannot tell you that a second aircraft has arrived while the first is still in view, because nothing changed. It was on, and it stays on.

So an aircraft crossing the sky above you fires an event of its own, once, the moment it arrives:

```yaml
automation:
  - alias: "ADS-B: something went over"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {{ trigger.event.data.airline | default('An unknown aircraft') }}
            at {{ trigger.event.data.slant_distance }} km
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}
            {%- endif %}.
```

The event carries the same keys as the aircraft attributes, so everything in the notification above is there: `flight`, `airline`, `description`, `altitude`, `vertical_rate`, the route if you look them up, and `entry_id` and `station` to tell one station from another. It adds one key of its own, `slant_distance`, which is the subject of the next paragraph.

Three things stop it becoming a nuisance.

**The distance counts the height.** Every other distance in this integration is measured across the ground, which is the right answer for how far your antenna reaches and the wrong one for what is above you. An airliner at 37,000 feet passing nine kilometres to the north is inside a ten kilometre radius on the map, and is fourteen kilometres away from you in the sky. It counts as nearby, as it should, and it is not a passage, as it should not be. The `distance` in the event is still the one across the ground; `slant_distance` is the real one.

**An aircraft has to leave before it can arrive again.** Reception drops out, aircraft circle, and one on the edge of the radius flickers in and out. An aircraft that goes and comes back inside ten minutes is the same passage; longer than that and it is a new one. So a helicopter working a field nearby rings once, not once a minute.

**An aircraft has to be flying.** One on the ground reports no altitude, so the distance through the air falls back to the distance across the ground and a taxiing airliner would look exactly like a low pass. If you live near a field that is most of your traffic, so it is left out. It still shows up under **Aircraft nearby**, marked `on_ground`, because it really is an aircraft within your radius.

## A notification that reads like a panel

The event carries enough to put the whole panel in a notification, and the companion app takes an image with it. Keep the message a literal block, `|-` rather than `>-`, or the lines fold into one sentence:

```yaml
automation:
  - alias: "ADS-B: passage as a panel"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: >-
            {{ trigger.event.data.airline
               | default(trigger.event.data.flight) | default('Unknown aircraft') }}
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Alt {{ trigger.event.data.altitude or '?' }}ft, Spd {{ trigger.event.data.speed | round | int if trigger.event.data.speed else '?' }}kn
            Trk {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Vr {{ trigger.event.data.vertical_rate or 0 }}ft/min
          data:
            subtitle: >-
              {{ trigger.event.data.route
                 | default(trigger.event.data.slant_distance ~ ' km') }}
            tag: adsb-passage
            group: adsb
            image: >-
              /local/airline_logos/{{ trigger.event.data.airline_code
                 | default('unknown') }}.png
```

Which reads as this, and as the right-hand column for something that broadcasts almost nothing:

```
Lufthansa                    PHABC
CDG-AMS                      1.1 km
Airbus A-320neo
Alt 4100ft, Spd 250kn        Alt 2000ft, Spd ?kn
Trk 263deg, Vr -1088ft/min   Trk 90deg, Vr 0ft/min
```

For metres and kilometres per hour, only the message changes, with the same factors as [the cards](#the-panel-and-the-board):

```yaml
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Alt {{ (trigger.event.data.altitude * 0.3048) | round | int }}m, Spd {{ (trigger.event.data.speed * 1.852) | round | int if trigger.event.data.speed else '?' }}km/h
            Trk {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Vr {{ (trigger.event.data.vertical_rate | default(0) * 0.00508) | round(1) }}m/s
```

Which reads as this, with a real flight through it:

```
Delta Air Lines
FRA-JFK
Airbus A-330-200
Alt 8702m, Spd 891km/h
Trk 290deg, Vr 2.9m/s
```

The logo is yours to supply: the app takes a `/local/` path into your `www` folder, so `www/airline_logos/DLH.png` and one `unknown.png` beside it covers every aircraft. Airline logos are trademarks and are not something this integration can ship for you. Give every notification the same `tag` and each aircraft replaces the one before it rather than filling your screen; leave the `tag` out and keep the `group` to see them all.

## The panel and the board

Two sensors read those passages, and between them they are a departure board for your own roof.

**Overhead flight** is the aircraft above you right now, the nearest one measured through the air, with everything about it as attributes: `airline`, `description`, `altitude`, `speed`, `track`, `vertical_rate`, `slant_distance`, the route if you look them up, and `since`, which is when it arrived. It keeps the last aircraft rather than blanking when the sky empties, because a panel that goes empty between aircraft is not worth looking at. The `overhead` attribute says which of the two you are looking at, and `seen_at` says when it was read.

That is enough for a panel, with nothing but a markdown card:

```yaml
type: markdown
content: |
  {% set plane = states.sensor.ads_b_station_overhead_flight %}
  ## {{ plane.attributes.airline | default(plane.state) }}
  {% if plane.attributes.route is defined %}### {{ plane.attributes.route }}{% endif %}
  {{ plane.attributes.description | default(plane.attributes.aircraft_type) | default('') }}

  `Alt {{ plane.attributes.altitude }}ft  Spd {{ plane.attributes.speed }}kn`
  `Trk {{ plane.attributes.track | round | int }}deg  Vr {{ plane.attributes.vertical_rate or 0 }}ft/min`

  {% if not plane.attributes.overhead %}*Last seen {{ relative_time(plane.last_changed) }} ago*{% endif %}
```

Altitudes are in feet and speeds in knots there, because that is what the aircraft broadcast and how aviation reads them. The entities themselves can be switched to metres and kilometres per hour one by one under **Settings → Entity → Unit of measurement**, but attributes are never converted by Home Assistant, so a card that wants metric does the sum itself:

```jinja
  `Alt {{ (plane.attributes.altitude * 0.3048) | round | int }}m  Spd {{ (plane.attributes.speed * 1.852) | round | int }}km/h`
  `Trk {{ plane.attributes.track | round | int }}deg  Vr {{ (plane.attributes.vertical_rate * 0.00508) | round(1) }}m/s`
```

| From | To | Multiply by |
|---|---|---|
| ft | m | 0.3048 |
| kn | km/h | 1.852 |
| ft/min | m/s | 0.00508 |

`distance` and `slant_distance` are in kilometres already.

**Passages today** is the tally, and the last twenty of them are on it as attributes: the time they arrived, the callsign, the airline, the type, how high and how close they came, how long they were in view (`duration`, in seconds) and the strongest they were ever heard (`peak_rssi`). Those last two are what a passage knows and a single poll cannot; both keep growing while the aircraft is still there and stand still once it has gone. Everything survives a restart of Home Assistant, so the board is a record rather than a session.

**Heard today** counts something else, and the two are worth having side by side. Passages are what came over your house; **Heard today** is every different aircraft your antenna reached all day, however far away and however high. It is the figure that says what your station is doing rather than what your sky is doing, and it is the one to watch after moving an aerial.

Each entry holds the aircraft at its closest approach rather than at its arrival, because an aircraft is first seen at the edge of the radius and is worth looking up at when it is overhead. It appears on the board as soon as it arrives and is rewritten while it is still in view, so the board is current and ends up correct.

```yaml
type: markdown
content: |
  {% for plane in state_attr('sensor.ads_b_station_passages_today', 'passages') %}
  `{{ as_timestamp(plane.at) | timestamp_custom('%H:%M') }}` **{{ plane.airline | default(plane.flight) | default('?') }}**
  {{ plane.route | default('') }} {{ plane.description | default('') }} · {{ plane.distance }} km
  {% endfor %}
```

One thing to know before you leave that running: twenty entries are written to the database every time an aircraft comes over. On a busy station that is worth keeping out of the recorder, which costs you nothing but the history of a board you read live anyway:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ads_b_station_passages_today
```

## On your lock screen

The companion app can put a passage on your lock screen and in the Dynamic Island as a [Live Activity](https://companion.home-assistant.io/docs/notifications/live-activities/), which is the closest thing to a flight wall you can carry around.

**This only works on the TestFlight build of the companion app, with Live Activities switched on under Labs**, and it needs Home Assistant 2026.7 or newer. It is not in the App Store release, so treat it as something to try rather than something to build on.

It needs nothing from this integration. A Live Activity is an ordinary notification carrying `live_update: true` and a `tag`, and what starts it is the passage event:

```yaml
automation:
  - alias: "ADS-B: overhead on the lock screen"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "{{ trigger.event.data.airline | default('Overhead') }}"
          message: >-
            {{ trigger.event.data.description | default('') }}
            {{ trigger.event.data.altitude }} ft
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}{% endif %}
          data:
            tag: adsb-overhead
            live_update: true

  - alias: "ADS-B: the sky is empty again"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_aircraft_overhead
        to: "off"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: clear_notification
          data:
            tag: adsb-overhead
```

The same `tag` on the next aircraft replaces the one before it without a banner or a sound, and the second automation takes it off your screen when there is nothing left up there. iOS limits how often an activity may start and how often it may be redrawn, which is why this hangs off the passage event and off a state going to off rather than off the poll: one message per aircraft instead of one every fifteen seconds.

## Before it gets here

Everything else this integration reports is in the past tense: the aircraft is already overhead. Position, track and speed are all in the poll, and between them they say where an aircraft will be — which is what makes an announcement useful rather than late.

Three figures ride along with every aircraft that is coming your way:

| Attribute | |
|---|---|
| `approaching` | Only there when it is |
| `closest_passing_distance` | How close it will come, in kilometres **across the ground** |
| `seconds_to_closest` | How long until it does |

```yaml
automation:
  triggers:
    - trigger: event
      event_type: adsb_station_aircraft_approaching
  actions:
    - action: notify.mobile_app_phone
      data:
        message: >
          {{ trigger.event.data.airline or trigger.event.data.flight }} passes
          {{ trigger.event.data.closest_passing_distance }} km out in
          {{ (trigger.event.data.seconds_to_closest / 60) | round }} minutes.
```

## What it is worth

**It is a straight line at a constant speed, and nothing more.** An aircraft that turns, starts an approach or is told to hold makes the prediction wrong the moment it does. That is not a limitation to be tuned away; it is what a prediction from three numbers can be.

So it is held to four rules, and they are the reason the event is worth having:

- **All three or nothing.** No position, no track or no speed means no prediction. An aircraft heard over bare Mode S is never announced.
- **Not on the ground.** Something taxiing is not coming over.
- **Five minutes ahead at most.** Beyond that an aircraft has had time to do something else entirely.
- **Two polls in a row.** One mis-decoded heading points an aircraft straight at your house for fifteen seconds; the event waits for the next poll to agree. An aircraft that turns towards you starts that count over rather than firing at once.

The event fires only for aircraft predicted to pass inside your nearby radius and under your [overhead ceiling](configuration.md#what-counts-as-overhead) — there is nothing to say about one that will pass forty kilometres away. It is said once, not every fifteen seconds until it arrives, using the same ten minute gap that separates two passages.

The distance is measured across the ground. An airliner at eleven kilometres passing straight overhead has a closest approach of nearly nothing on the map, which is the honest answer to "will it come over my house"; whether it is worth looking up at is what the ceiling decides.
