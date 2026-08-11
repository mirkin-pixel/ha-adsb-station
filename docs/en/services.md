# Asking a question

The entities answer the questions you knew to ask when you built the dashboard. Two services answer the rest, out of the same poll, without going back to the decoder.

**`adsb_station.look_up_aircraft`** takes a hex code or a callsign, in either case, and answers with everything the station knows about that one aircraft:

```yaml
- action: adsb_station.look_up_aircraft
  data:
    aircraft: KLM123
  response_variable: found
- condition: template
  value_template: "{{ found.aircraft is not none }}"
- action: notify.persistent_notification
  data:
    message: >
      {{ found.aircraft.flight }} is {{ found.aircraft.distance }} km to the
      {{ found.aircraft.sector }}, at {{ found.aircraft.altitude }} feet.
```

`aircraft` is `null` when the station is not hearing it, which is an answer and not a failure — that is the ordinary reply to "is it up there".

**`adsb_station.list_aircraft`** answers with everything that matches, nearest first:

```yaml
- action: adsb_station.list_aircraft
  data:
    max_distance: 25
    max_altitude: 10000
  response_variable: low
```

| Filter | |
|---|---|
| `max_distance` | In kilometres |
| `min_altitude`, `max_altitude` | In feet |
| `military` | On for military traffic only, off for everything but |
| `category` | The emitter category, `A7` for a helicopter and `B6` for a drone |

A filter leaves out what it cannot judge: an aircraft heard over Mode S alone has no position and no altitude, so it drops out of a distance or a height filter rather than being counted as nought.

Both reach **everything the decoder is holding**, which is the whole sky your antenna covers and not just the nearby radius. Without a single filter, `list_aircraft` answers with all of it. Both add one thing the attributes do not carry: `sector`, the compass direction to look in.

Try them under **Developer tools → Actions**, with **Return response data** ticked.

If you run several entries — a feeder or two beside the entry that carries your decoder — you can leave the station out. Only the entries that actually have a receiver are considered, so the field is needed only when two of yours are reading antennas.
