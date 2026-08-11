# Waar een vlucht heen gaat

Je antenne hoort dit nooit. Een vliegtuig zendt een callsign uit, `KLM1234`, en verder niets over de vlucht erachter, dus waar het opgestegen is en waar het heen gaat staat niet in `aircraft.json` en kan daar ook niet staan. Elke kaart die je een route laat zien, ook die van tar1090, vraagt het aan een database op de grond. Daarmee is dit het enige gegeven dat deze integratie niet op je eigen netwerk kan ophalen, en daarom staat **Vluchtroutes opzoeken** onder **Configureren** uit tot je hem aanzet.

De bron is **routeset**, via `adsb.im`, dezelfde bron die tar1090 zelf gebruikt. Hij vraagt niet om een account of een sleutel, en hij neemt alle callsigns van één meting in één verzoek.

Hij krijgt ook te horen waar elk vliegtuig gehoord is, en dat is wat hem laat oordelen. Een moderne callsign van een maatschappij wordt over de benen van een dag hergebruikt, dus het vluchtnummer kennen is niet hetzelfde als weten waar dát toestel heen gaat; routeset laat een route die niet bij de positie past vallen in plaats van hem te tonen, omdat een verkeerde route in een notificatie erger is dan geen.

Alleen de vliegtuigen binnen je straal "dichtbij" worden opgezocht. Dat is het handjevol waar een automatisering iets mee doet, en vragen naar elk vliegtuig in bereik zou een stroom verzoeken aan andermans server zijn voor een gegeven dat nergens getoond wordt. Antwoorden worden twaalf uur bewaard, zodat de lijnvluchten die er dagelijks overkomen één keer opgezocht worden in plaats van elke poll, en er worden nooit meer dan 25 nieuwe callsigns per poll opgezocht.

Wordt er een route gevonden, dan verschijnt die bij elk vliegtuig in de attributen van **Vliegtuigen dichtbij** en **Vliegtuig overhead**:

| Attribuut | Voorbeeld |
|---|---|
| `route` | `CDG-AMS` |
| `origin`, `destination` | `CDG`, `AMS` |
| `origin_location`, `destination_location` | `Paris`, `Amsterdam` |
| `origin_name`, `destination_name` | `Charles de Gaulle International Airport` |

De maatschappij staat er niet bij, en dat hoeft ook niet: die is er [hoe dan ook al](decoders.md#namen-bij-de-codes).

Attributen die niet bekend zijn worden weggelaten in plaats van leeg gelaten, zodat een template kan vragen of de sleutel er überhaupt is. Privé, militair en een flink deel van het vrachtverkeer levert niets op, en een bron die onbereikbaar is betekent simpelweg geen route die poll; de vliegtuigentiteiten zelf hangen er nooit van af.

Een vliegtuig dat geen positie uitzendt krijgt ook geen route, want de bron toetst elke route die hij vindt aan waar het toestel is. In de praktijk kost dat niets: alleen de vliegtuigen die dichtbij genoeg zijn worden opgezocht, en dichtbij genoeg wordt vanaf een positie gemeten.
