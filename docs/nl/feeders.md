# Feeders

Elke feeder voegt zijn eigen entiteiten toe, op zijn eigen apparaat. Welke je ziet hangt af van de feeder waarvoor die entry is ingericht.

**Flightradar24**, uit de `monitor.json` van `fr24feed`:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Vliegtuigen gevolgd | Sensor | Vliegtuigen die de feeder op dit moment volgt |
| Vliegtuigen gevolgd via ADS-B | Sensor | Daarvan het aantal dat via ADS-B gevolgd wordt |
| Vliegtuigen doorgestuurd | Sensor | Vliegtuigen in de laatste upload naar Flightradar24 |
| Feedstatus | Sensor | De ruwe statustekst van de feed |
| Ontvanger | Binary sensor (verbinding) | Aan zolang `fr24feed` de dongle ziet |
| Feed | Binary sensor (verbinding) | Aan zolang de feed Flightradar24 bereikt |
| MLAT | Binary sensor (verbinding, diagnostisch) | Aan zolang multilateratie werkt |
| Feedmodus | Sensor (diagnostisch) | De huidige feedmodus, bijvoorbeeld MLAT |
| Feed-alias | Sensor (diagnostisch) | Je feeder-ID, bijvoorbeeld T-EHXX23 |
| Kaartgrootte | Sensor (diagnostisch) | De `d11_map_size` van de feeder |
| Herstarts | Sensor (diagnostisch) | Het aantal resets sinds de start |
| Laatst verbonden | Sensor (diagnostisch) | Wanneer de feed voor het laatst verbond |
| CPU-temperatuur | Sensor (diagnostisch) | De SoC-temperatuur van de host. Alleen op de builds voor single board computers |
| Klokafwijking | Sensor (s, diagnostisch) | Hoe ver de klok van de feeder afdreef. Multilateratie heeft dit klein nodig |
| Tijdbron | Sensor (diagnostisch) | Waar de feeder zijn klok mee gelijkzet, bijvoorbeeld NTP |
| Feed-server | Sensor (diagnostisch) | De Flightradar24-server waar deze feeder mee praat |
| Hersynchronisaties | Sensor (diagnostisch) | Hoe vaak de feeder opnieuw moest synchroniseren |

**FlightAware**, uit de `status.json` van PiAware:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Radio | Sensor | Of de decoder gehoord wordt |
| Feed | Sensor | De verbinding met FlightAware |
| MLAT | Sensor | Multilateratie |
| PiAware-dienst | Sensor (diagnostisch) | De feeder zelf |
| CPU-belasting | Sensor (%, diagnostisch) | Belasting van de host |
| Bedrijfstijd | Sensor (u, diagnostisch) | Hoe lang de host draait |
| CPU-temperatuur | Sensor (diagnostisch) | Alleen aangemaakt op een host die er een uitleest |

Die vier zijn groen, amber of rood in plaats van aan of uit, want amber zegt iets wat de andere twee niet kunnen: een feeder die een onstabiele klok meldt draait prima, maar zal nooit multilatereren. De kleur is de state, en de zin erachter, *"Local clock source is unstable"*, staat als attribuut `message` op de entiteit.

**Plane Finder**, uit de `/ajax/stats` van `pfclient`:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Berichten per seconde | Sensor (msg/s) | Mode S-pakketten per seconde, zoals pfclient ze telt |
| MLAT | Binary sensor (verbinding) | Aan zolang er multilateratiedata verstuurd wordt |
| Mode S-berichten | Sensor (diagnostisch) | Totaal aantal pakketten sinds de client startte |
| Mode A/C-berichten | Sensor (diagnostisch) | Daarvan de Mode A/C-pakketten |
| CRC-fouten | Sensor (diagnostisch) | Pakketten die hun controlegetal niet haalden |
| Geüpload | Sensor (MB, diagnostisch) | Verstuurd naar Plane Finder |
| MLAT geüpload | Sensor (kB, diagnostisch) | Daarvan het multilateratie-aandeel |
| Datasnelheid ontvanger | Sensor (B/s, diagnostisch) | Wat er van de decoder binnenkomt |

pfclient publiceert zelf geen multilateratie-vlag, maar telt wel wat het verstuurt, en een station waarvan de klok te onstabiel is om te multilatereren verstuurt niets. Die bytesteller is dus de sensor.

Met een feeder worden de feeder en de ontvanger los van elkaar uitgelezen: als de decoder niet meer antwoordt, worden alleen de vliegtuig-entiteiten onbeschikbaar en blijven de feed-entiteiten werken. Zonder feeder is de decoder de enige bron, en neemt een storing alles mee.

## Waar je antenne geblokkeerd zit

Eén enkel maximumbereik verbergt de vorm van je dekking: 250 km naar het zuiden en 40 km naar het noorden is een heel ander station dan 145 km rondom. Acht sensoren houden per windrichting bij hoe ver een vliegtuig ooit gehoord is, elk over 45 graden gecentreerd op hun richting, dus **Bereikrecord noord** dekt 337,5° tot 22,5°.

| Entiteit | Type | Omschrijving |
|---|---|---|
| Bereikrecord noord … noordwest | Sensor (km) | Het record voor die sector, met `recorded_at`, `flight` en `hex` als attributen |
| Bereikrecords wissen | Knop | Wist alle acht |

Dit zijn de records; **Maximaal bereik** hierboven is het cijfer van nu. Die heet zo omdat de hobby het zo noemt en je feedersites het zo rapporteren, en hij volgt de lucht: een poll waarin niets verder weg is dan 40 km zet hem op 40 km. Deze acht gaan alleen maar omhoog.

De records groeien alleen maar, en ze overleven een herstart van Home Assistant, want een record dat bij elke herstart opnieuw begint is niets waard. De sensoren blijven ook leesbaar als er niets vliegt, want een record van vorige maand is nog steeds een meting.

Datzelfde groeien maakt ze onjuist zodra je antenne verhuist of de buurman een schuur neerzet; daar is de knop voor. Druk je erop terwijl er toestellen in beeld zijn, dan zet hij meteen nieuwe records vanaf de plek waar je antenne nu staat.
