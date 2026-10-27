# Hoe hij eruitziet

Ook dit hoort je antenne niet. Een vliegtuig zendt een adres uit, `484506`, en een database op de grond weet welk toestel dat adres heeft en hoe het eruitziet. **Foto's van vliegtuigen opzoeken** onder **Configureren** vraagt het die database, en net als [routes](routes.md) staat het uit tot je het aanzet.

De bron is **Planespotters.net**, dat van de meeste toestellen die vliegen een foto heeft. Er wordt gevraagd op het ICAO-adres dat elk vliegtuig uitzendt, dus het werkt of je decoder nu een vliegtuigdatabase heeft of niet, en dat adres is het enige wat er verstuurd wordt.

Alleen de vliegtuigen binnen je straal "dichtbij" worden opgezocht, en die op je [watchlist](watchlist.md) waar ze ook zijn: een toestel dat een regel op die lijst waard is, is het toestel waarvan je de foto wilt als het op veertig kilometer opduikt. Elk vliegtuig is een eigen verzoek, dus per poll worden er hooguit drie nieuwe opgezocht, en antwoorden worden een dag bewaard, wat het maximum is dat Planespotters toestaat. Een vliegtuig onder een PIA-adres wordt nooit opgezocht, want dat adres wordt uitgeleend en weer ingenomen, en de foto zou dan van het toestel zijn dat het als laatste had.

Als er een foto is, staat die bij het vliegtuig in de attributen van **Vliegtuigen dichtbij**, **Vliegtuig overhead**, **Watchlist in bereik** en de kaartentiteiten, en in de events voor passages en de watchlist. Een vliegtuig dat als naderend gemeld wordt is nog buiten de straal, dus dat heeft er nog geen. Dit zijn de drie:

| Attribuut | Voorbeeld |
|---|---|
| `photo` | `https://t.plnspttrs.net/27134/1978923_ff0b1a1dbf_280.jpg` |
| `photo_link` | `https://www.planespotters.net/photo/1978923/ph-bvs-…` |
| `photographer` | `Jan Seler` |

Ze komen met z'n drieën of helemaal niet.

## Er een netjes tonen

De foto's zijn het werk van iemand, en Planespotters leent ze uit onder [voorwaarden](https://www.planespotters.net/photo/api): **de fotograaf wordt naast de foto genoemd, en de foto linkt naar zijn pagina** op Planespotters.net. Daarom zijn er drie attributen, en daarom wordt de foto nooit als entiteitsafbeelding gezet: Home Assistant toont die als een klein rond plaatje zonder naam en zonder link, en die zijn er niet bij te zetten.

De afbeelding zelf haalt de integratie niet op. Je browser of telefoon laadt hem rechtstreeks van het adres in `photo`, en zo willen de voorwaarden het ook. Gebruik de adressen zoals ze zijn; de voorwaarden staan niet toe dat je de afbeelding ergens anders neerzet of de link herschrijft.

Een markdown-kaart doet allebei in twee regels:

```yaml
type: markdown
content: |
  {% set plane = (state_attr('binary_sensor.your_station_aircraft_overhead', 'aircraft') or [{}]) | first %}
  {% if plane.photo is defined %}
  [![{{ plane.flight or plane.hex }}]({{ plane.photo }})]({{ plane.photo_link }})
  Foto: {{ plane.photographer }} / Planespotters.net
  {% endif %}
```

Een melding met de foto als afbeelding doet het door de naam in de tekst te zetten en de pagina achter een tik:

```yaml
automation:
  - alias: "ADS-B: vliegtuig overhead, met foto"
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
            overhead. Foto: {{ trigger.event.data.photographer }} / Planespotters.net
          data:
            image: "{{ trigger.event.data.photo }}"
            # Android opent clickAction bij een tik op de melding, iOS opent url.
            clickAction: "{{ trigger.event.data.photo_link }}"
            url: "{{ trigger.event.data.photo_link }}"
```

Een scherm zonder iets om op te tikken, zoals een e-ink-lijstje, heeft een andere weg naar de pagina nodig; de voorwaarden noemen een QR-code of een NFC-tag.

## Als er geen is

Een flink deel van de privé-, militaire en net afgeleverde toestellen heeft geen foto, en dan zijn de attributen er gewoon niet. Bij een drukke lucht kan de foto ook een poll later komen dan het vliegtuig, omdat er maar drie tegelijk opgezocht worden, en dan heeft het passage-event van dat vliegtuig er geen. Is Planespotters niet bereikbaar, dan komen er die poll geen nieuwe foto's bij en vraagt een latere poll het opnieuw; de vliegtuigentiteiten hangen er nooit van af.
