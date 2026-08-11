# Welke decoder

Elke decoder levert je de entiteiten hierboven waarvoor hij data heeft; wat hij meldt wordt bij het instellen gedetecteerd, zodat er geen entiteit wordt aangemaakt die nooit een waarde kan hebben. Dat betekent wel dat de decoder die je draait bepaalt hoeveel je krijgt, en **readsb levert het meest**:

| | dump1090-fork van fr24feed | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Vliegtuigen, bereik, berichten per seconde | Ja | Ja | Ja |
| Signaal, ruis, signaal-ruisverhouding | Ja | Ja | Ja |
| Gain | Nee | Ja | Ja |
| Antennepositie in `receiver.json` | Nee | Ja | Ja |
| Emittercategorie, en hoe het toestel gehoord is | Nee | Ja | Ja |
| Registratie, type, omschrijving | Nee | Nee | Ja, met vliegtuigdatabase |
| Markeringen interesting, PIA en LADD | Nee | Nee | Ja, met vliegtuigdatabase |

Twee daarvan zijn het benoemen waard. Zonder gain-waarde stem je je dongle blind af, en zonder antennepositie in `receiver.json` wordt het bereik gemeten vanaf de thuislocatie van je Home Assistant-installatie in plaats van vanaf je antenne, wat prima is als dat dezelfde plek is en fout als je ontvanger elders staat.

Draai je nu alleen `fr24feed`, dan kost het vervangen van de meegeleverde dump1090 door readsb je niets en levert het de gain-sensor, de vliegtuigdetails en een echte antennepositie op. **Draai Herconfigureren na een decoder-upgrade** om op te pikken wat hij nu kan.

## De vliegtuigdatabase

De laatste twee rijen vragen één extra stap. readsb vult `r`, `t`, `desc` en `dbFlags` alleen als hij een vliegtuigdatabase heeft; zonder database meldt de sensor voor het dichtstbijzijnde vliegtuig wel een hex-code en een callsign, maar geen registratie en geen type. De militair-markering is de uitzondering: zonder database wordt die uit het adres afgeleid, wat [de tabel hieronder](#namen-bij-de-codes) uitlegt.

Haal op een readsb-installatie de database op en wijs readsb ernaar:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Voeg daarna de optie toe aan `/etc/default/readsb`, bij de argumenten waarmee readsb start:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Herstart readsb en de extra velden staan meteen in `aircraft.json`. De integratie pikt ze vanzelf op: de attributen verschijnen zodra de decoder ze stuurt, dus je hoeft niets te herconfigureren. De database is een momentopname, dus ververs hem af en toe door hetzelfde commando opnieuw te draaien.

## Wat de decoder verder meldt

Er reizen nog vijf attributen met een vliegtuig mee, en net als hierboven staan ze er alleen als de decoder ze stuurt:

| Attribuut | Wat het zegt |
|---|---|
| `category` | De emittercategorie die het vliegtuig uitzendt, `A0` tot en met `D7`. `A7` is een helikopter en `B6` een drone, en dit is de enige plek waar dat ergens staat |
| `heard_as` | Hoe de decoder van het toestel af weet: `adsb_icao` rechtstreeks van het vliegtuig gehoord, `mlat` uitgerekend uit de aankomsttijden bij meerdere ontvangers, `mode_s` een kaal antwoord zonder positie erin |
| `interesting` | De vliegtuigdatabase heeft dit toestel gemarkeerd als de moeite waard |
| `pia` | Een Privacy ICAO Address: een tijdelijke hexcode waaronder een operator vliegt om buiten de lijsten te blijven |
| `ladd` | Het Amerikaanse verzoek om te beperken waar het toestel getoond wordt |

`category` komt door de lucht en staat er dus ook zonder vliegtuigdatabase; de laatste drie zijn de overige bits van diezelfde `dbFlags` waarvan de militaire markering bit 0 is. Alle drie worden doorgegeven en niet toegepast. Een toestel dat je ontvanger gehoord heeft, is er een die hij gehoord heeft, en of een dashboard een PIA- of LADD-vlucht weglaat is aan jou en niet aan deze integratie.

## Namen bij de codes

Een vliegtuig zendt `DLH6CH`, `A20N` en `484123` uit. Geen van drieën is een naam, en geen decoder kan er een van maken, want die namen zitten niet in het radiosignaal: het zijn lijsten die iemand bijhoudt. Die lijsten worden met de integratie meegeleverd, dus de vliegtuigattributen dragen een naam zonder dat er iets over internet gevraagd wordt:

| Attribuut | Afgeleid uit | Voorbeeld |
|---|---|---|
| `airline` | De eerste drie letters van de callsign | `DLH6CH` → `Lufthansa` |
| `airline_code` | Diezelfde drie letters, of de tabel er nu een naam bij heeft of niet | `DLH6CH` → `DLH` |
| `description` | De ICAO-typecode, als de decoder hem zelf niet omschrijft | `A20N` → `Airbus A-320neo` |
| `country` | Het 24-bits adres zelf, dat ICAO per land in reeksen heeft uitgegeven | `484123` → `AW` |

Een callsign die geen vluchtnummer is levert geen maatschappij op. Zakenjets, zweefvliegtuigen en de meeste kleine luchtvaart vliegen onder hun registratie, dus `PHABC` blijft met rust gelaten in plaats van gelezen te worden als een maatschappijcode en te veranderen in wat `PHA` toevallig is.

`airline_code` staat er ook bij een maatschappij die de tabel niet kent, want het vliegtuig zendt hem uit en een dashboard zoekt er een logo mee op. `airline` staat er alleen als de tabel er een naam bij heeft.

Een typecode staat voor een familie en niet voor één vliegtuig: een A20N is een A320neo maar ook de zakenversie ervan, en een BE20 is elk van een stuk of tien King Airs plus hun militaire neven. Niets in de gegevens zegt welke je het vaakst boven je hoofd krijgt, dus de naam is degene die de code zelf spelt. Dat klopt voor de lijnvliegtuigen en kan bij de kleine luchtvaart op een vreemde variant uitkomen.

`country` is waar een toestel geregistreerd staat en niet waar het is: een KLM-toestel boven Spanje blijft `NL`. Niet elk adres valt in een reeks — sommige zijn nooit uitgegeven, sommige horen bij geen enkele staat, en een adres dat readsb heeft uitgerekend in plaats van gehoord krijgt een `~` mee — en een toestel daaruit draagt helemaal geen land in plaats van een gok.

Diezelfde tabel zegt welke reeksen een land voor zijn eigen krijgsmacht apart houdt, en daar komt de **militair-markering** vandaan als de decoder geen vliegtuigdatabase heeft. Het is het grovere van de twee antwoorden: het kent de reeks en niet het toestel, dus een civiel vliegtuig binnen een militaire reeks zou meegemarkeerd worden. Een decoder die wél een database heeft, heeft daarom het laatste woord, en in beide richtingen. Zegt `dbFlags` dat een toestel civiel is, dan is het civiel, ook binnen een militaire reeks; het adres wordt pas gevraagd als niemand anders antwoord geeft.

Beide tabellen komen uit de [standing data van Virtual Radar Server](https://github.com/vradarserver/standing-data), die publiek domein is onder CC0-1.0. Net als de vliegtuigdatabase hierboven zijn het momentopnames; `scripts/build_reference.py` maakt ze opnieuw aan vanuit de bron.
