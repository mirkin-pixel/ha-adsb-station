# What it looks like

Your antenna does not hear this either. An aircraft broadcasts an address, `484506`, and a database on the ground knows which airframe has it and what that airframe looks like. **Look up aircraft photos** under **Configure** asks that database, and like [routes](routes.md) it is off until you switch it on.

The source is **Planespotters.net**, which keeps a photo of most airframes that fly. It is asked by the ICAO address every aircraft broadcasts, so it works whether or not your decoder has an aircraft database, and that address is all it is sent.

Only the aircraft inside your nearby radius are looked up, and the ones on your [watchlist](watchlist.md) wherever they are: an aircraft worth a line on that list is the one whose photo you want when it turns up forty kilometres out. Each aircraft is a request of its own, so no more than three new ones are looked up per poll, and answers are kept for a day, which is as long as Planespotters allows. An aircraft flying under a PIA address is never looked up, because that address is lent out and taken back, and its photo would be of whichever airframe last had it.

When a photo is found it appears on the aircraft in the attributes of **Aircraft nearby**, **Aircraft overhead**, **Watchlist in range** and the map entities, and in the passage and watchlist events. An aircraft announced as approaching is still outside the radius, so it has none yet. These are the three:

| Attribute | Example |
|---|---|
| `photo` | `https://t.plnspttrs.net/27134/1978923_ff0b1a1dbf_280.jpg` |
| `photo_link` | `https://www.planespotters.net/photo/1978923/ph-bvs-…` |
| `photographer` | `Jan Seler` |

They come as a set or not at all.

## Showing one properly

The photos are someone's work, and Planespotters lends them out on [terms](https://www.planespotters.net/photo/api): **the photographer is named next to the photo, and the photo leads to its page** on Planespotters.net. That is why there are three attributes, and why the photo is never set as an entity picture: Home Assistant shows one of those as a small round avatar without a name or a link, and there is no way to add them.

The image itself is not fetched by the integration. Your browser or phone loads it straight from the address in `photo`, which is what the terms ask for. Use the addresses as they are; the terms do not allow copying the image elsewhere or rewriting the link.

A markdown card does both in two lines:

```yaml
type: markdown
content: |
  {% set plane = (state_attr('binary_sensor.your_station_aircraft_overhead', 'aircraft') or [{}]) | first %}
  {% if plane.photo is defined %}
  [![{{ plane.flight or plane.hex }}]({{ plane.photo }})]({{ plane.photo_link }})
  Photo: {{ plane.photographer }} / Planespotters.net
  {% endif %}
```

A notification with the photo as its image does it by putting the name in the text and the page behind a tap:

```yaml
automation:
  - alias: "ADS-B: aircraft overhead, with a photo"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.photo is defined }}"
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {{ trigger.event.data.airline | default(trigger.event.data.flight) }}
            overhead. Photo: {{ trigger.event.data.photographer }} / Planespotters.net
          data:
            image: "{{ trigger.event.data.photo }}"
            # Android opens clickAction when the notification is tapped, iOS opens url.
            clickAction: "{{ trigger.event.data.photo_link }}"
            url: "{{ trigger.event.data.photo_link }}"
```

A display without a screen to tap, such as an e-ink frame, needs a different way to reach the page; the terms name a QR code or an NFC tag.

## When there is none

A good share of private, military and newly delivered aircraft has no photo, and the attributes are then simply absent. On a busy sky the photo can also arrive a poll after the aircraft does, because only three are looked up at a time, so the passage event of that aircraft goes without one. If Planespotters cannot be reached, that poll has no new photos and a later one asks again; the aircraft entities never depend on it.
