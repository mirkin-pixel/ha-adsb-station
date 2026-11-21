# Configuratie

1. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen**.
2. Zoek naar **ADS-B Station**.
3. Typ het adres van je ontvanger. Home Assistant zoekt daar de `aircraft.json` van de decoder en de feeders: fr24feed op `8754`, PiAware op `8080`, `80` of `8082`, pfclient op `30053`. Wat al is ingesteld, wordt overgeslagen.
4. Hij laat zien wat hij vond. **Toevoegen** zet de eerste feeder op met de decoder eraan, of de ontvanger alleen als er geen feeder antwoordt. Elke andere feeder verschijnt daarna onder **Ontdekt** op dezelfde pagina: **Toevoegen** daar is één klik, zonder de decoder, want één entry die hem leest is genoeg.
5. Antwoordt er niets nieuws, of kies je liever zelf, dan kies je met de hand, met het adres al ingevuld:
   - **Flightradar24-feeder (fr24feed)**: het adres van de machine waarop hij draait, en de poort van de statuspagina, standaard `8754`.
   - **FlightAware-feeder (PiAware)**: idem, standaard poort `8080`. Staat er een andere webserver op die poort, dan kan `status.json` elders staan; op een station met tar1090 achter nginx is poort 80 het proberen waard.
   - **Plane Finder-feeder (pfclient)**: idem, standaard poort `30053`.
   - **Alleen een ADS-B-ontvanger**: voor een station dat nergens aan voedt, of als de entry die de decoder draagt.

   Elk daarvan biedt daarna de ontvanger aan. Koppel die aan één entry en laat hem bij de andere leeg, anders tellen de vliegtuigcijfers dubbel.

De getallen staan vanaf het begin in de eenheden van Home Assistant: metrisch, of imperiaal bij US-eenheden. De voet, knopen en zeemijlen van piloten zijn één keuze verderop, onder **Configureren**.

Deze paden worden automatisch geprobeerd, op poort 8080 waar fr24feed en PiAware ze aanbieden en op poort 80 waar readsb met tar1090 dat doet. Poort 8504 wordt geprobeerd voor `/data/aircraft.json`, waar tar1090 hem ook aanbiedt als lighttpd de webserver is:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

Alle kandidaten worden tegelijk geprobeerd, en de eerste in die volgorde die antwoordt wint. Staat die van jou elders, vul dan zelf de volledige URL in.

Onder **Configureren** op de integratiepagina:

| Optie | Standaard | Wat het doet |
|---|---|---|
| [Eenheden](#eenheden) | Zoals Home Assistant | Waarin hoogtes, snelheden en afstanden staan |
| Ververstijd | 15 s | Hoe vaak de vliegtuigen uitgelezen worden. Alles draait op je eigen netwerk, dus een korte tijd kan prima. Zolang er een stationskaart openstaat elke 5 s, zodat de kaart op verse posities beweegt |
| Ververstijd statistieken | 60 s | Hoe vaak de feeder en de statistieken van de decoder uitgelezen worden. Dat zijn tellers en gemiddelden over een minuut, dus vaker uitlezen vult vooral de recorder; een station dat alleen feedt wordt alleen op deze tijd uitgelezen |
| Straal dichtbij | 10 km, 5,4 NM of 6,2 mijl | Wat als dichtbij en overhead telt, voor **Vliegtuigen dichtbij**, **Vliegtuig overhead** en passages. Tien kilometer is ongeveer wat je kunt zien en horen; een goede ontvanger haalt een veelvoud daarvan |
| [Hoogtegrens overhead](#wat-overhead-precies-betekent) | Leeg | Hoe hoog een vliegtuig mag zijn en nog als overhead telt |
| [Passages bewaren](services.md#passages-van-de-afgelopen-dagen) | 30 dagen | Hoe lang passages bewaard blijven nadat het bord om middernacht opnieuw begint |
| [Vliegtuigen op de kaart](dashboards.md#vliegtuigen-op-de-kaart) | Uit | Elk vliegtuig dichtbij als entiteit op de eigen kaart van Home Assistant |
| [Vluchtroutes opzoeken](routes.md) | Uit | Waar een vlucht heen gaat, gevraagd aan een dienst op internet |
| [Foto's van vliegtuigen opzoeken](photos.md) | Uit | Een foto van elk vliegtuig, van Planespotters.net |
| [Watchlist](watchlist.md) | Leeg | Toestellen die je wilt weten zodra ze opduiken |
| [Vliegtuigdatabase downloaden](decoders.md#de-vliegtuigdatabase) | Uit | Alleen als je decoder zelf geen vliegtuigen benoemt |

Bovenaan het formulier staat vanaf welk punt afstanden gemeten worden: de antennepositie die de decoder in `receiver.json` publiceert, of de thuislocatie van Home Assistant als hij er geen publiceert. Station verhuisd naar een ander adres? Gebruik **Herconfigureren** in plaats van hem opnieuw toe te voegen.

Wil je een feeder toevoegen aan een station dat je als alleen-ontvanger hebt ingericht, voeg dan een tweede entry toe, precies wat je later ook doet om een tweede of derde netwerk erbij te zetten.

## Eenheden

**Eenheden** bepaalt waarin hoogtes, snelheden en afstanden staan, overal: de sensoren, hun attributen, de events, de antwoorden van de acties, **Activiteit** en wat Assist zegt. De keuzes zijn de drie van tar1090:

| Eenheden | Hoogte | Snelheid | Afstand | Stijgen en dalen |
|---|---|---|---|---|
| Luchtvaart | ft | kn | nmi | ft/min |
| Metrisch | m | km/h | km | m/s |
| Imperiaal | ft | mph | mi | ft/min |

Dit zijn de namen die Home Assistant de eenheden geeft, en die waarmee een template vergelijkt. De keuze zelf schrijft knopen en zeemijlen zoals piloten dat doen, kt en NM, en het formulier en **Activiteit** schrijven een afstand ook als NM.

**Zoals Home Assistant**, de standaard, is imperiaal als Home Assistant op Amerikaanse eenheden staat en anders metrisch. Een station dat vóór 1.4 is ingesteld krijgt na de update een melding onder **Instellingen → Systeem → Reparaties**, met de eenheden waarin zijn getallen nu staan en de keuze er meteen bij; kies **Luchtvaart** om hoogtes in voet en snelheden in knopen te houden. Wissel je, dan gaan de bestaande sensoren mee, met hun historie, behalve een sensor waar je zelf een eenheid voor koos onder **Instellingen → Entiteit → Maateenheid**: die houdt de jouwe. Home Assistant heeft geen weg terug van zo'n eenheid, dus de integratie biedt er een. Zolang een hoogte-, snelheid- of afstandsensor een eigen eenheid heeft, staat onder **Configureren** onder **Eenheden** een vakje dat hem noemt en hem, aangevinkt, weer laat meegaan. Een station dat naar 1.4 gaat krijgt dezelfde vraag onder **Reparaties**, omdat zo'n eenheid waarschijnlijk gekozen is toen de eenheden door elkaar stonden. Daar laat je ze meegaan, of houd je ze zo.

Attributen en events zeggen zelf waarin ze staan, zodat een template nooit hoeft te raden: `altitude_unit`, `speed_unit`, `distance_unit` en `vertical_rate_unit` gaan mee met elk getal. De [stationskaart](dashboards.md) toont dezelfde eenheden, zodat je ze op één plek kiest.

Wat je invult volgt het ook: de straal "dichtbij" en de [hoogtegrens](#wat-overhead-precies-betekent) onder **Configureren**, de filters van de [acties](services.md), en `map_range` en `max_altitude` van de kaart. De straal en de hoogtegrens houden bij een wissel de afstand die ze voorstellen: tien kilometer wordt 5,4 NM in het formulier, niet tien. De filters en de instellingen van de kaart zijn getallen die je zelf ergens opschreef, in een script of op een dashboard, dus die kan de integratie niet omrekenen; na een wissel betekent een `max_distance` van 25 dan 25 van de nieuwe eenheid.

## De feeder als add-on draaien

Draait je decoder als Home Assistant-add-on in plaats van op een eigen machine — [MaxWinterstein's ADS-B Multi Portal Feeder](https://github.com/MaxWinterstein/homeassistant-addons) is de bekendste — dan is er geen IP-adres in te vullen. Add-ons bereiken elkaar op hostnaam, en de **Info**-pagina van de add-on zelf laat zien welke dat is: de slug met de prefix van de repository ervoor, zoals `1a2b3c4d-adsb-multi-portal-feeder`. Vul die in waar de flow om een host vraagt.

## Wat overhead precies betekent

Een straal is een cirkel op de grond, en alles wat erin komt telt als dichtbij en komt over, hoe hoog het ook vliegt. Een lijnvliegtuig op 36.000 voet dat over je straat gaat zit binnen een cirkel van tien kilometer, en die wil je misschien niet op je bord of in je meldingen.

**Hoogtegrens overhead** onder **Configureren** is het antwoord, in de [eenheden](#eenheden) die je koos, en hij is leeg tot je hem invult. Tienduizend voet, zo'n 3.000 meter, is een verstandig beginpunt: daaronder zit verkeer in de nadering, helikopters, en alles met een reden om laag te zitten.

Wat hij verandert is bewust smal:

| | Met een grens |
|---|---|
| **Vliegtuigen dichtbij**, **Vliegtuig overhead**, passages, het passage-event, de kaart | Alleen toestellen eronder |
| **Vliegtuigen ontvangen**, de bereikrecords, **Maximaal bereik**, de hoogste en de snelste | Onveranderd — die gaan over wat je station hoorde |
| **Noodsquawk** | Onveranderd, op elke hoogte. Een toestel dat 7700 squawkt wil je ook vanaf 37.000 voet horen |

Een toestel dat zegt **op de grond** te staan blijft dichtbij, wat de grens ook is. Het meldt juist geen hoogte omdát het op de grond staat, dus het getal vergelijken zou het verkeer weggooien waar een grens nooit op gemikt was. Een toestel dat om een andere reden geen hoogte meldt — alleen over kale Mode S gehoord bijvoorbeeld — valt niet te beoordelen en valt af, net zoals een hoogtefilter op de [acties](services.md) weglaat wat het niet kan meten.
