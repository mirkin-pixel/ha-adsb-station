# Configuratie

1. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen**.
2. Zoek naar **ADS-B Station**.
3. Kies waar deze entry voor is:
   - **Flightradar24-feeder (fr24feed)**: het adres van de machine waarop hij draait, en de poort van de statuspagina, standaard `8754`.
   - **FlightAware-feeder (PiAware)**: idem, standaard poort `8080`. Staat er een andere webserver op die poort, dan kan `status.json` elders staan; op een station met tar1090 achter nginx is poort 80 het proberen waard.
   - **Plane Finder-feeder (pfclient)**: idem, standaard poort `30053`.
   - **Alleen een ADS-B-ontvanger**: voor een station dat nergens aan voedt, of als de entry die de decoder draagt.
4. Elk pad biedt daarna de ontvanger aan. Koppel die aan één entry en laat hem bij de andere leeg, anders tellen de vliegtuigcijfers dubbel.

Deze paden worden automatisch geprobeerd, op poort 8080 waar fr24feed en PiAware ze aanbieden en op poort 80 waar readsb met tar1090 dat doet:

```
/dump1090/data/aircraft.json
/data/aircraft.json
/tar1090/data/aircraft.json
/skyaware/data/aircraft.json
/dump1090-fa/data/aircraft.json
```

Alle kandidaten worden tegelijk geprobeerd, en de eerste in die volgorde die antwoordt wint. Staat die van jou elders, vul dan zelf de volledige URL in.

Er staan vijf instellingen onder **Configureren** op de integratiepagina. De ververstijd is standaard 15 seconden; alles draait op je eigen netwerk, dus een korte tijd kan prima. De straal "dichtbij" is standaard 10 km en bepaalt wat als overhead telt voor de entiteiten **Vliegtuigen dichtbij** en **Vliegtuig overhead**; tien kilometer is ongeveer wat je kunt zien en horen, terwijl een goede ontvanger een veelvoud daarvan haalt. Daarnaast staat de [hoogtegrens](#wat-overhead-precies-betekent), en die is leeg. De laatste twee zijn [vliegtuigen op de kaart](dashboards.md#vliegtuigen-op-de-kaart) en [waar een vlucht heen gaat](routes.md), en die staan allebei uit. Station verhuisd naar een ander adres? Gebruik **Herconfigureren** in plaats van hem opnieuw toe te voegen.

Wil je een feeder toevoegen aan een station dat je als alleen-ontvanger hebt ingericht, voeg dan een tweede entry toe, precies wat je later ook doet om een tweede of derde netwerk erbij te zetten.

## De feeder als add-on draaien

Draait je decoder als Home Assistant-add-on in plaats van op een eigen machine — [MaxWinterstein's ADS-B Multi Portal Feeder](https://github.com/MaxWinterstein/homeassistant-addons) is de bekendste — dan is er geen IP-adres in te vullen. Add-ons bereiken elkaar op hostnaam, en de **Info**-pagina van de add-on zelf laat zien welke dat is: de slug met de prefix van de repository ervoor, zoals `1a2b3c4d-adsb-multi-portal-feeder`. Vul die in waar de flow om een host vraagt.

## Wat overhead precies betekent

Een straal is een cirkel op de grond. Een lijnvliegtuig op 36.000 voet dat over je straat gaat zit binnen een cirkel van tien kilometer, en niemand kijkt daarnaar op — de hoogte telt al mee voor de afstand, maar een ruime straal laat hem er toch in.

**Hoogtegrens overhead** onder **Configureren** is het antwoord, in voet, en hij is leeg tot je hem invult. Tienduizend voet is een verstandig beginpunt: daaronder zit verkeer in de nadering, helikopters, en alles met een reden om laag te zitten.

Wat hij verandert is bewust smal:

| | Met een grens |
|---|---|
| **Vliegtuigen dichtbij**, **Vliegtuig overhead**, passages, het passage-event, de kaart | Alleen toestellen eronder |
| **Vliegtuigen ontvangen**, de bereikrecords, **Maximaal bereik**, de hoogste en de snelste | Onveranderd — die gaan over wat je station hoorde |
| **Noodsquawk** | Onveranderd, op elke hoogte. Een toestel dat 7700 squawkt wil je ook vanaf 37.000 voet horen |

Een toestel dat zegt **op de grond** te staan blijft dichtbij, wat de grens ook is. Het meldt juist geen hoogte omdát het op de grond staat, dus het getal vergelijken zou het verkeer weggooien waar een grens nooit op gemikt was. Een toestel dat om een andere reden geen hoogte meldt — alleen over kale Mode S gehoord bijvoorbeeld — valt niet te beoordelen en valt af, net zoals een hoogtefilter op de [acties](services.md) weglaat wat het niet kan meten.
