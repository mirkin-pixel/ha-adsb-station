# Iets vragen

De entiteiten beantwoorden de vragen die je wist te stellen toen je je dashboard bouwde. Twee acties beantwoorden de rest, uit diezelfde poll, zonder opnieuw bij de decoder langs te gaan.

**`adsb_station.look_up_aircraft`** neemt een hexcode of een callsign, hoofdletters maken niet uit, en antwoordt met alles wat het station van dat ene toestel weet:

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
      {{ found.aircraft.flight }} zit {{ found.aircraft.distance }} km naar het
      {{ found.aircraft.sector }}, op {{ found.aircraft.altitude }} voet.
```

`aircraft` is `null` als het station hem niet hoort, en dat is een antwoord en geen fout — het is het gewone antwoord op "hangt hij er?".

**`adsb_station.list_aircraft`** antwoordt met alles wat voldoet, dichtstbij eerst:

```yaml
- action: adsb_station.list_aircraft
  data:
    max_distance: 25
    max_altitude: 10000
  response_variable: low
```

| Filter | |
|---|---|
| `max_distance` | In kilometers |
| `min_altitude`, `max_altitude` | In voet |
| `military` | Aan voor alleen militair verkeer, uit voor alles behalve dat |
| `category` | De emittercategorie, `A7` voor een helikopter en `B6` voor een drone |

Een filter laat weg wat het niet kan beoordelen: een toestel dat alleen over Mode S gehoord is heeft geen positie en geen hoogte, en valt dus uit een afstands- of hoogtefilter in plaats van als nul geteld te worden.

Allebei reiken ze tot **alles wat de decoder vasthoudt**, dus de hele lucht die je antenne dekt en niet alleen de nabijheidsstraal. Zonder één filter antwoordt `list_aircraft` met de complete lijst. Allebei voegen ze één ding toe dat de attributen niet dragen: `sector`, de windrichting waarin je moet kijken.

Probeer ze onder **Ontwikkelhulpmiddelen → Acties**, met **Antwoordgegevens teruggeven** aangevinkt.

Draai je meerdere entries — een feeder of twee naast de entry die je decoder draagt — dan kun je het station weglaten. Alleen de entries die echt een ontvanger hebben tellen mee, dus het veld is pas nodig als er twee van jou een antenne lezen.
