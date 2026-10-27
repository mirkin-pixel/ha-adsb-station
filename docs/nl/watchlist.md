# Een lijst om in de gaten te houden

Sommige toestellen wil je weten zodra ze opduiken, waar ze ook zijn: de traumaheli, een staart die je kent, een type dat je nog nooit gezien hebt. **Watchlist** onder **Configureren** is die lijst, één per regel.

```
484123
PH-BXA
KLM123
EC35
7700
```

Er is geen straal. Een passage zegt dat er iets over je huis kwam; een watchlist vraagt of het toestel überhaupt in de lucht is, en wordt dus vergeleken met alles wat je decoder vasthoudt — de hele lucht die je antenne haalt.

Een regel kan vier dingen zijn, en zijn vorm zegt welke:

| Geschreven als | Gelezen als |
|---|---|
| `484123` | De hexcode die een toestel uitzendt |
| `PH-BXA`, `PHBXA`, `KLM123` | Een naam waaronder het vliegt: de registratie of de callsign, tegen allebei vergeleken |
| `EC35` | Een vliegtuigtype uit de [meegeleverde tabel](decoders.md#namen-bij-de-codes) |
| `7700` | Een squawkcode |

Hoofdletters, streepjes en spaties maken niets uit. Een regel die in geen van de vier past wordt geweigerd bij het opslaan, en de melding noemt hem — een watchlist die stilzwijgend nooit matcht is erger dan een die niet wil opslaan.

Matcht er iets, dan gaat **Watchlist in bereik** aan en vuurt er een event:

```yaml
automation:
  triggers:
    - trigger: event
      event_type: adsb_station_watchlist_match
  actions:
    - action: notify.persistent_notification
      data:
        message: >
          {{ trigger.event.data.watching }} is in de lucht:
          {{ trigger.event.data.flight or trigger.event.data.hex }},
          {{ trigger.event.data.distance }} km ver.
```

Het event draagt de regel die matchte, `matched_on` om te zeggen welk deel van het toestel hij raakte, en verder alles wat de vliegtuigattributen dragen. Eén toestel is één bericht, hoeveel regels het ook noemen, en het wordt niet herhaald zolang het toestel in de lucht blijft — dezelfde tien minuten die een passage gebruikt. Tien minuten nadat het wegvalt is terugkomen weer iets om te horen.

## Bijhouden vanaf een dashboard

De lijst hoeft niet onder **Configureren** bewerkt te worden. De entry die je decoder draagt heeft er twee vakjes voor op de apparaatpagina: **Watchlist: toevoegen** en **Watchlist: verwijderen**. Typ een regel en druk op Enter. Hij gaat door dezelfde controle als het formulier, dus een regel die daar niet opgeslagen wordt, wordt hier ook geweigerd, met de regel erbij genoemd. Een regel toevoegen die er al op staat, hoe hij er ook geschreven staat, verandert niets. Een regel verwijderen die er niet op staat geeft een melding in plaats van niets te doen, want meestal is dat een tikfout.

Een entiteitenkaart zet ze naast de sensor die de lijst toont:

```yaml
type: entities
title: Watchlist
entities:
  - entity: text.your_station_watchlist_add
  - entity: text.your_station_watchlist_remove
  - entity: binary_sensor.your_station_watchlist_in_range
```

De lijst zelf staat in het attribuut `watching` van **Watchlist in bereik**.

Hetzelfde kan als actie, voor een script of een automatisering: `adsb_station.watch` en `adsb_station.unwatch`, elk met de regel als `aircraft`:

```yaml
action: adsb_station.watch
data:
  aircraft: PH-BXA
```

Twee dingen om te weten. Op beide manieren herlaadt de entry, precies zoals na het opslaan van het optieformulier, dus de sensoren beginnen even opnieuw. En de acties zijn voor beheerders, net als het optieformulier. De vakjes zijn entiteiten, dus iedereen die je dashboard kan gebruiken kan erin typen.
