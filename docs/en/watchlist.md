# A list worth watching

Some aircraft are worth knowing about whenever they turn up, wherever they are: the air ambulance, a tail you know, an aircraft type you have never seen. **Watchlist** under **Configure** is a list of them, one to a line.

```
484123
PH-BXA
KLM123
EC35
7700
```

There is no radius. A passage says something came over your house; a watchlist asks whether the aircraft is in the air at all, so it is matched against everything your decoder is holding — the whole sky your antenna reaches.

A line can be four things, and its shape says which:

| Written like | Read as |
|---|---|
| `484123` | The hex code an aircraft transmits |
| `PH-BXA`, `PHBXA`, `KLM123` | A name it flies under: the registration or the callsign, compared against both |
| `EC35` | An aircraft type from the [shipped table](decoders.md#names-for-the-codes) |
| `7700` | A squawk code |

Capitals, dashes and spaces make no difference. A line that fits none of the four is refused when you save, and the error names it — a watchlist that quietly never matches would be worse than one that will not save.

When something matches, **Watchlist in range** goes on and an event fires:

```yaml
automation:
  triggers:
    - trigger: event
      event_type: adsb_station_watchlist_match
  actions:
    - action: notify.persistent_notification
      data:
        message: >
          {{ trigger.event.data.watching }} is up:
          {{ trigger.event.data.flight or trigger.event.data.hex }},
          {{ trigger.event.data.distance }} km out.
```

The event carries the line that matched, `matched_on` to say which part of the aircraft it hit, and everything else the aircraft attributes carry. One aircraft is one message, however many lines name it, and it is not repeated while the aircraft stays in the air — the same ten minute gap a passage uses. Ten minutes after it drops out, coming back is worth being told about again.

## Keeping it from a dashboard

The list does not have to be edited under **Configure**. The entry that carries your decoder has two boxes for it on its device page: **Watchlist: add** and **Watchlist: remove**. Type a line and press enter. It goes through the same check as the form, so a line that would not save there is refused here too, with the line named, and adding a line already on the list, written however it was written, changes nothing. Removing a line that is not on the list says so rather than doing nothing, because that is usually a typo.

An entities card puts them beside the sensor that shows the list:

```yaml
type: entities
title: Watchlist
entities:
  - entity: text.your_station_watchlist_add
  - entity: text.your_station_watchlist_remove
  - entity: binary_sensor.your_station_watchlist_in_range
```

The list itself is in the `watching` attribute of **Watchlist in range**.

The same two things are actions, for a script or an automation: `adsb_station.watch` and `adsb_station.unwatch`, each with the line as `aircraft`:

```yaml
action: adsb_station.watch
data:
  aircraft: PH-BXA
```

The new list takes effect straight away, without reloading the integration, so nothing under way is lost: an aircraft that was already announced is not announced again, and a passage overhead is not counted twice. That goes for the options form as well, as long as the watchlist is all you change there. The actions are for administrators, like the options form. The boxes are entities, so anyone who can use your dashboard can type into them.
