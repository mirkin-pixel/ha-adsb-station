# Iets vragen

De entiteiten beantwoorden de vragen die je wist te stellen toen je je dashboard bouwde. Twee acties beantwoorden de rest, uit diezelfde poll, zonder opnieuw bij de decoder langs te gaan, en een derde kijkt terug naar de [passages van de afgelopen dagen](#passages-van-de-afgelopen-dagen).

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
      {{ found.aircraft.flight }} zit {{ found.aircraft.distance }}
      {{ found.distance_unit }} naar het {{ found.aircraft.sector }}, op
      {{ found.aircraft.altitude }} {{ found.altitude_unit }}.
```

`aircraft` is `null` als het station hem niet hoort, en dat is een antwoord en geen fout — het is het gewone antwoord op "hangt hij er?".

**`adsb_station.list_aircraft`** antwoordt met alles wat voldoet, dichtstbij eerst:

```yaml
- action: adsb_station.list_aircraft
  data:
    max_distance: 25
    max_altitude: 3000
  response_variable: low
```

| Filter | |
|---|---|
| `max_distance` | In de [eenheden](configuration.md#eenheden) van het station: km, NM of mijl |
| `min_altitude`, `max_altitude` | In de eenheden van het station: meter of voet |
| `military` | Aan voor alleen militair verkeer, uit voor alles behalve dat |
| `category` | De emittercategorie, `A7` voor een helikopter en `B6` voor een drone |

Een filter laat weg wat het niet kan beoordelen: een toestel dat alleen over Mode S gehoord is heeft geen positie en geen hoogte, en valt dus uit een afstands- of hoogtefilter in plaats van als nul geteld te worden.

Allebei reiken ze tot **alles wat de decoder vasthoudt**, dus de hele lucht die je antenne dekt en niet alleen de nabijheidsstraal. Zonder één filter antwoordt `list_aircraft` met de complete lijst. Allebei voegen ze één ding toe dat de attributen niet dragen: `sector`, de windrichting waarin je moet kijken. De getallen in het antwoord staan in de [eenheden](configuration.md#eenheden) van het station, met `altitude_unit`, `speed_unit`, `distance_unit` en `vertical_rate_unit` ernaast; de filters vul je ook in die eenheden in.

Probeer ze onder **Ontwikkelhulpmiddelen → Acties**, met **Antwoordgegevens teruggeven** aangevinkt.

Draai je meerdere entries — een feeder of twee naast de entry die je decoder draagt — dan kun je het station weglaten. Alleen de entries die echt een ontvanger hebben tellen mee, dus het veld is pas nodig als er twee van jou een antenne lezen.

## Passages van de afgelopen dagen

Het bord van **Passages vandaag** begint om middernacht opnieuw. Het station bewaart de passages daarnaast 30 dagen, in te stellen onder **Configureren** als **Passages bewaren**, en **`adsb_station.list_passages`** zoekt ze op, de nieuwste eerst:

```yaml
- action: adsb_station.list_passages
  data:
    aircraft: PH-BXA
    start: "2026-11-01 00:00:00"
  response_variable: seen
- action: notify.persistent_notification
  data:
    message: >
      PH-BXA kwam deze maand {{ seen.passages | count }} keer over,
      het laatst op {{ as_timestamp(seen.passages[0].at) | timestamp_custom('%d %b %H:%M') }}.
```

| Veld | |
|---|---|
| `aircraft` | Een hexcode, roepnaam of registratie, met of zonder streepje. Leeg voor alle toestellen |
| `start`, `end` | Alleen passages die daartussen begonnen, in de tijdzone van Home Assistant tenzij de tijd er zelf een noemt |

Elke passage is zoals op het bord: `at`, `hex`, `flight`, `altitude`, `distance`, `duration`, en waar bekend `peak_rssi`, `airline`, `registration`, `aircraft_type`, `description` en `route`, in de eenheden van het station. Ze staan in een eigen bestand onder `.storage`, zo'n 200 bytes per passage, dus een maand van een rustig station is een paar honderd kilobyte; het wordt hooguit elk kwartier geschreven, en een station bewaart er nooit meer dan 50.000. Zet **Passages bewaren** op 0 om er geen te bewaren; dan verdwijnt ook het bestand.

## De watchlist wijzigen

Twee acties veranderen iets in plaats van te antwoorden: `adsb_station.watch` en `adsb_station.unwatch` zetten een regel op de watchlist en halen hem er weer af. Ze staan beschreven bij de [watchlist](watchlist.md#bijhouden-vanaf-een-dashboard).
