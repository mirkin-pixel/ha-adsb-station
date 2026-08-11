# Als er iets overkomt

**Vliegtuig overhead** beantwoordt één vraag, en dat doet hij goed: hangt er iets boven me. Wat hij niet kan vertellen is dat er een tweede toestel is aangekomen terwijl het eerste er nog is, want er verandert niets. Hij stond aan, en hij blijft aan.

Daarom vuurt een vliegtuig dat de lucht boven je oversteekt een eigen event af, één keer, op het moment dat het aankomt:

```yaml
automation:
  - alias: "ADS-B: er kwam iets over"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app
        data:
          message: >-
            {{ trigger.event.data.airline | default('Een onbekend vliegtuig') }}
            op {{ trigger.event.data.slant_distance }} km
            {%- if trigger.event.data.route is defined %},
            {{ trigger.event.data.route }}
            {%- endif %}.
```

Het event draagt dezelfde sleutels als de vliegtuigattributen, dus alles uit de melding hierboven zit erin: `flight`, `airline`, `description`, `altitude`, `vertical_rate`, de route als je die opzoekt, en `entry_id` en `station` om het ene station van het andere te onderscheiden. Er komt één sleutel bij, `slant_distance`, en die is het onderwerp van de volgende alinea.

Drie dingen houden het draaglijk.

**De afstand telt de hoogte mee.** Elke andere afstand in deze integratie wordt over de grond gemeten, en dat is het juiste antwoord op hoe ver je antenne reikt en het verkeerde op wat er boven je hangt. Een verkeersvliegtuig op 37.000 voet dat negen kilometer noordelijk passeert zit op de kaart binnen een straal van tien kilometer, en is veertien kilometer bij je vandaan door de lucht. Hij telt als dichtbij, en dat hoort ook, en hij is geen passage, en dat hoort ook. De `distance` in het event is nog steeds die over de grond; `slant_distance` is de echte.

**Een vliegtuig moet eerst weg zijn voor het opnieuw kan aankomen.** De ontvangst valt weg, toestellen draaien rondjes, en eentje op de rand van de straal knippert in en uit. Een vliegtuig dat weggaat en binnen tien minuten terugkomt is dezelfde passage; duurt het langer, dan is het een nieuwe. Een helikopter die vlakbij een perceel afwerkt belt dus één keer aan, niet elke minuut.

**Een vliegtuig moet vliegen.** Eentje op de grond meldt geen hoogte, dus de afstand door de lucht valt terug op die over de grond en een taxiënd verkeersvliegtuig lijkt precies op een lage overkomst. Woon je vlakbij een veld, dan is dat het grootste deel van je verkeer, dus die blijven erbuiten. Ze staan wel gewoon bij **Vliegtuigen dichtbij**, gemarkeerd met `on_ground`, want het is echt een vliegtuig binnen je straal.

## Een melding die leest als een paneel

Het event draagt genoeg om het hele paneel in een notificatie te zetten, en de companion-app neemt er een afbeelding bij. Houd het bericht een letterlijk blok, `|-` en niet `>-`, anders vouwen de regels tot één zin:

```yaml
automation:
  - alias: "ADS-B: passage als paneel"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_jouw_telefoon
        data:
          title: >-
            {{ trigger.event.data.airline
               | default(trigger.event.data.flight) | default('Onbekend toestel') }}
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Hgt {{ trigger.event.data.altitude or '?' }}ft, Snh {{ trigger.event.data.speed | round | int if trigger.event.data.speed else '?' }}kn
            Krs {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Stg {{ trigger.event.data.vertical_rate or 0 }}ft/min
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

Dat leest zo, en de rechterkolom is wat je krijgt van iets dat bijna niets uitzendt:

```
Lufthansa                    PHABC
CDG-AMS                      1,1 km
Airbus A-320neo
Hgt 4100ft, Snh 250kn        Hgt 2000ft, Snh ?kn
Krs 263deg, Stg -1088ft/min  Krs 90deg, Stg 0ft/min
```

Voor meters en kilometers per uur verandert alleen het bericht, met dezelfde factoren als bij [de cards](#het-paneel-en-het-bord):

```yaml
          message: |-
            {{ trigger.event.data.description | default(trigger.event.data.aircraft_type) | default('') }}
            Hgt {{ (trigger.event.data.altitude * 0.3048) | round | int }}m, Snh {{ (trigger.event.data.speed * 1.852) | round | int if trigger.event.data.speed else '?' }}km/h
            Krs {{ trigger.event.data.track | round | int if trigger.event.data.track is not none else '?' }}deg, Stg {{ (trigger.event.data.vertical_rate | default(0) * 0.00508) | round(1) }}m/s
```

Wat er dan uitkomt, met een echte vlucht erdoorheen:

```
Delta Air Lines
FRA-JFK
Airbus A-330-200
Hgt 8702m, Snh 891km/h
Krs 290deg, Stg 2,9m/s
```

Het logo lever je zelf: de app accepteert een `/local/`-pad naar je `www`-map, dus `www/airline_logos/DLH.png` met een `unknown.png` ernaast dekt elk vliegtuig. Logo's van maatschappijen zijn merken, en die kan deze integratie niet voor je meeleveren. Geef elke melding dezelfde `tag` en elk toestel vervangt het vorige in plaats van je scherm vol te zetten; laat je de `tag` weg en houd je de `group`, dan zie je ze allemaal staan.

## Het paneel en het bord

Twee sensoren lezen die passages uit, en samen zijn ze een vertrekbord voor je eigen dak.

**Vlucht overhead** is het toestel dat nu boven je hangt, het dichtstbijzijnde door de lucht gemeten, met alles erover als attributen: `airline`, `description`, `altitude`, `speed`, `track`, `vertical_rate`, `slant_distance`, de route als je die opzoekt, en `since`, het moment dat hij aankwam. Hij houdt het laatste toestel vast in plaats van leeg te lopen als de lucht leeg raakt, want een paneel dat tussen twee vliegtuigen door leeg staat is het ophangen niet waard. Het attribuut `overhead` zegt welke van de twee je ziet, en `seen_at` wanneer het gelezen is.

Meer heb je voor een paneel niet nodig, alleen een markdown-card:

```yaml
type: markdown
content: |
  {% set plane = states.sensor.ads_b_station_vlucht_overhead %}
  ## {{ plane.attributes.airline | default(plane.state) }}
  {% if plane.attributes.route is defined %}### {{ plane.attributes.route }}{% endif %}
  {{ plane.attributes.description | default(plane.attributes.aircraft_type) | default('') }}

  `Hgt {{ plane.attributes.altitude }}ft  Snh {{ plane.attributes.speed }}kn`
  `Krs {{ plane.attributes.track | round | int }}deg  Stg {{ plane.attributes.vertical_rate or 0 }}ft/min`

  {% if not plane.attributes.overhead %}*Laatst gezien {{ relative_time(plane.last_changed) }} geleden*{% endif %}
```

Hoogtes staan daar in voet en snelheden in knopen, want zo zendt het vliegtuig ze uit en zo leest de luchtvaart ze. De entiteiten zelf kun je stuk voor stuk omzetten naar meters en kilometers per uur via **Instellingen → Entiteit → Maateenheid**, maar attributen rekent Home Assistant nooit om, dus een kaart die metrisch wil doet de som zelf:

```jinja
  `Hgt {{ (plane.attributes.altitude * 0.3048) | round | int }}m  Snh {{ (plane.attributes.speed * 1.852) | round | int }}km/h`
  `Krs {{ plane.attributes.track | round | int }}deg  Stg {{ (plane.attributes.vertical_rate * 0.00508) | round(1) }}m/s`
```

| Van | Naar | Maal |
|---|---|---|
| ft | m | 0,3048 |
| kn | km/h | 1,852 |
| ft/min | m/s | 0,00508 |

`distance` en `slant_distance` staan al in kilometers.

**Passages vandaag** is de teller, en de laatste twintig staan als attributen op de sensor: hoe laat ze aankwamen, de callsign, de maatschappij, het type, hoe hoog en hoe dichtbij ze kwamen, hoe lang ze in beeld waren (`duration`, in seconden) en hoe sterk ze op hun best gehoord werden (`peak_rssi`). Die laatste twee weet een passage en één poll niet; ze lopen op zolang het toestel er nog is en staan stil zodra het weg is. Alles overleeft een herstart van Home Assistant, zodat het bord een verslag is en niet een sessie.

**Vandaag gehoord** telt iets anders, en die twee zijn het naast elkaar te hebben waard. Passages zijn wat er over je huis kwam; **Vandaag gehoord** is elk verschillend toestel dat je antenne die dag bereikte, hoe ver weg en hoe hoog ook. Het is het getal dat zegt wat je station doet in plaats van wat je lucht doet, en het is degene om naar te kijken nadat je een antenne verplaatst hebt.

Elke regel houdt het toestel op zijn dichtste punt vast en niet bij aankomst, want je ziet een vliegtuig het eerst aan de rand van de straal en het best als het recht boven je staat. Hij verschijnt op het bord zodra het toestel aankomt en wordt bijgewerkt zolang het in beeld is, dus het bord loopt bij en klopt uiteindelijk.

```yaml
type: markdown
content: |
  {% for plane in state_attr('sensor.ads_b_station_passages_vandaag', 'passages') %}
  `{{ as_timestamp(plane.at) | timestamp_custom('%H:%M') }}` **{{ plane.airline | default(plane.flight) | default('?') }}**
  {{ plane.route | default('') }} {{ plane.description | default('') }} · {{ plane.distance }} km
  {% endfor %}
```

Eén ding om te weten voor je dat laat draaien: er worden twintig regels naar de database geschreven elke keer dat er een vliegtuig overkomt. Op een druk station is het de moeite waard om dat buiten de recorder te houden, wat je niets kost behalve de historie van een bord dat je toch live afleest:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ads_b_station_passages_vandaag
```

## Op je vergrendelscherm

De companion-app kan een passage op je vergrendelscherm en in het Dynamic Island zetten als [Live Activity](https://companion.home-assistant.io/docs/notifications/live-activities/), en dat is het dichtst bij een flight wall dat je op zak kunt dragen.

**Dit werkt alleen op de TestFlight-versie van de companion-app, met Live Activities aangezet onder Labs**, en je hebt Home Assistant 2026.7 of nieuwer nodig. In de App Store-versie zit het niet, dus zie het als iets om te proberen en niet als iets om op te bouwen.

Van deze integratie vraagt het niets. Een Live Activity is een gewone notificatie met `live_update: true` en een `tag` erin, en wat hem start is het passage-event:

```yaml
automation:
  - alias: "ADS-B: overhead op het vergrendelscherm"
    trigger:
      - platform: event
        event_type: adsb_station_aircraft_passage
    action:
      - service: notify.mobile_app_jouw_telefoon
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

  - alias: "ADS-B: de lucht is weer leeg"
    trigger:
      - platform: state
        entity_id: binary_sensor.ads_b_station_vliegtuig_overhead
        to: "off"
    action:
      - service: notify.mobile_app_jouw_telefoon
        data:
          message: clear_notification
          data:
            tag: adsb-overhead
```

Dezelfde `tag` bij het volgende toestel vervangt het vorige zonder banner en zonder geluid, en de tweede automatisering haalt hem van je scherm als er niets meer boven je hangt. iOS beperkt hoe vaak een activity mag starten en hoe vaak hij opnieuw getekend mag worden, en daarom hangt dit aan het passage-event en aan een state die naar off gaat en niet aan de meting: één bericht per vliegtuig in plaats van één per vijftien seconden.

## Voordat het er is

Al het andere dat deze integratie meldt staat in de verleden tijd: het toestel hangt er al. Positie, koers en snelheid zitten allemaal in de poll, en samen zeggen ze waar een toestel zál zijn — en dat is wat een aankondiging bruikbaar maakt in plaats van te laat.

Drie waarden reizen mee met elk toestel dat jouw kant op komt:

| Attribuut | |
|---|---|
| `approaching` | Staat er alleen als het zo is |
| `closest_passing_distance` | Hoe dichtbij hij komt, in kilometers **over de grond** |
| `seconds_to_closest` | Hoe lang dat nog duurt |

```yaml
automation:
  triggers:
    - trigger: event
      event_type: adsb_station_aircraft_approaching
  actions:
    - action: notify.mobile_app_telefoon
      data:
        message: >
          {{ trigger.event.data.airline or trigger.event.data.flight }} komt over
          {{ (trigger.event.data.seconds_to_closest / 60) | round }} minuten op
          {{ trigger.event.data.closest_passing_distance }} km langs.
```

## Wat het waard is

**Het is een rechte lijn op constante snelheid, en verder niets.** Een toestel dat draait, aan een nadering begint of een holding krijgt, maakt de voorspelling op dat moment ongeldig. Dat is geen tekortkoming die je wegregelt; dat is wat een voorspelling uit drie getallen kán zijn.

Daarom gelden er vier regels, en juist die maken het event de moeite waard:

- **Alle drie of niets.** Geen positie, geen koers of geen snelheid betekent geen voorspelling. Een toestel dat alleen over kale Mode S gehoord is wordt nooit aangekondigd.
- **Niet op de grond.** Iets dat taxiet komt niet over.
- **Hoogstens vijf minuten vooruit.** Daarbuiten heeft een toestel tijd gehad om iets heel anders te doen.
- **Twee polls op rij.** Eén verkeerd gedecodeerde koers richt een toestel vijftien seconden lang recht op je huis; het event wacht tot de volgende poll het beaamt. Een toestel dat jouw kant op draait begint die telling opnieuw in plaats van meteen af te gaan.

Het event vuurt alleen voor toestellen die binnen je nabijheidsstraal en onder je [hoogtegrens](configuration.md#wat-overhead-precies-betekent) langs zullen komen — over iets dat op veertig kilometer passeert valt niets te melden. En het wordt één keer gezegd, niet elke vijftien seconden tot het er is, met dezelfde tien minuten die twee passages scheiden.

De afstand wordt over de grond gemeten. Een lijnvliegtuig op elf kilometer hoogte dat recht overkomt heeft op de kaart een langsafstand van vrijwel niets, en dat is het eerlijke antwoord op "komt hij over mijn huis"; of je er ook naar opkijkt bepaalt de hoogtegrens.
