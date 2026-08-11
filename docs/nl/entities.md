# Entiteiten

Alles uit `aircraft.json`, het deel dat elke opstelling krijgt:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Vliegtuigen ontvangen | Sensor | Vliegtuigen in de laatste `aircraft.json` |
| Vliegtuigen met positie | Sensor | Daarvan het aantal met een bekende positie |
| Maximaal bereik | Sensor (km) | Afstand tot het verste gehoorde vliegtuig |
| Berichten per seconde | Sensor (msg/s) | Mode S-berichten per seconde, berekend tussen twee metingen |
| Dichtstbijzijnde vliegtuig | Sensor (km) | Afstand tot het dichtstbijzijnde vliegtuig, met callsign, hoogte, snelheid, koers, stijgsnelheid, maatschappij en signaalsterkte als attributen. Een decoder met vliegtuigdatabase voegt registratie, type en een militair-markering toe |
| Hoogste vliegtuig | Sensor (ft) | Hoogte van het hoogste vliegtuig in bereik, met dezelfde attributen |
| Snelste vliegtuig | Sensor (kn) | Grondsnelheid van het snelste vliegtuig in bereik, met dezelfde attributen |
| Vliegtuigen dichtbij | Sensor | Hoeveel vliegtuigen binnen de straal "dichtbij" zitten, met ze allemaal als attributen, dichtstbijzijnde eerst. Dit zijn de twee die [waar de vlucht heen gaat](routes.md) kunnen dragen |
| Vliegtuig overhead | Binary sensor | Aan zolang er minstens één vliegtuig binnen die straal zit |
| Vlucht overhead | Sensor | Het ene vliegtuig boven je, het dichtstbijzijnde door de lucht gemeten. Houdt de laatste vast als de lucht leegloopt, zodat een paneel erop nooit leeg staat. Zie [als er iets overkomt](passages.md) |
| Passages vandaag | Sensor | Hoeveel vliegtuigen er vandaag overkwamen, met de laatste twintig als attributen, meest recente eerst |
| Vandaag gehoord | Sensor | Hoeveel verschillende toestellen het station vandaag hoorde, op elke afstand |
| Watchlist in bereik | Binary sensor | Aan zolang er een toestel van je [watchlist](watchlist.md) in de lucht is. Staat er alleen als je er een hebt ingesteld |
| Noodsquawk | Binary sensor (veiligheid) | Aan zolang een vliegtuig in je bereik 7500, 7600 of 7700 squawkt |
| Berichten | Sensor (diagnostisch) | De totale berichtenteller van de ontvanger |
| Ontvanger bijgewerkt | Sensor (diagnostisch) | Het tijdstempel in `aircraft.json` |

Het hoogste en het snelste tellen ook vliegtuigen die nooit een positie uitzenden: hoogte en snelheid komen al via Mode S binnen, en die weglaten zou beide cijfers te laag maken. Hun attribuut `distance` is dan leeg.

"In de laatste `aircraft.json`" is wat de decoder vasthoudt, en dat is iets meer dan wat er op dit moment uitzendt: hij bewaart een vliegtuig nog ongeveer een minuut na het laatste bericht. Dat is met opzet, en het is wat het aantal laat kloppen met de kaart die je decoder zelf toont. Het attribuut `seen` bij elk vliegtuig zegt hoeveel seconden geleden het voor het laatst gehoord is.

Een positie moet mogelijk zijn voordat hij geloofd wordt. ADS-B is zichtlijn, dus een vliegtuig op 37.000 voet is tot ongeveer 440 km te horen en een op 2.000 voet tot ongeveer 100 km, en daar komt 80 km bij voor een antenne die hoog staat. Een positie daarbuiten is verkeerd gedecodeerd in plaats van ontvangen, en vervalt: hij zou anders een vliegtuig boven je zetten dat er nooit was, of een [sectorrecord](feeders.md#waar-je-antenne-geblokkeerd-zit) achterlaten dat voorgoed blijft staan. Het vliegtuig telt nog steeds als ontvangen, want het bestaat; alleen als een vliegtuig waarvan de positie onbekend is.

Die twee en het maximale bereik houden vast wat ze het laatst zagen in plaats van leeg te lopen zodra de lucht leeg is, en ze overleven een herstart. Een station dat een paar vliegtuigen per uur hoort zou anders het grootste deel van de tijd niets melden. Het attribuut `seen_at` zegt hoe lang geleden dat was, en elk volgt nog steeds de lucht: een lager toestel later vervangt de waarde. Dat is het verschil met de [sectorrecords](feeders.md#waar-je-antenne-geblokkeerd-zit), die alleen maar groeien.

En, als je ontvanger ook `stats.json` aanbiedt, de gezondheid van je ontvangst:

| Entiteit | Type | Omschrijving |
|---|---|---|
| Signaalniveau | Sensor (dBFS) | Het gemiddelde signaalniveau van de ontvangen berichten |
| Signaal-ruisverhouding | Sensor (dB) | Signaal min ruis; de beste enkele maat voor hoe goed je hoort |
| Ruisniveau | Sensor (dBFS, diagnostisch) | De ruisvloer |
| Piek-signaalniveau | Sensor (dBFS, diagnostisch) | Het sterkste bericht in het venster |
| Te sterke signalen | Sensor (diagnostisch) | Berichten die te luid waren. Structureel boven nul betekent dat je gain te hoog staat |
| Verloren samples | Sensor (diagnostisch) | Samples die de host niet kon bijbenen. Alles boven nul betekent dat je ongemerkt berichten verliest |
| Geaccepteerde berichten | Sensor (diagnostisch) | Geaccepteerde berichten in het venster, opgeteld over alle correctieniveaus |
| Tracks | Sensor (diagnostisch) | Vliegtuigtracks gestart in het venster |
| Tracks met één bericht | Sensor (diagnostisch) | Tracks die nooit een tweede bericht kregen; een hoog aandeel wijst op slechte decodering |
| Demodulatorbelasting | Sensor (%, diagnostisch) | Hoeveel CPU-tijd de decoder aan demoduleren besteedde |
| Gain | Sensor (dB) | De gain waarop de dongle draait. Wordt alleen aangemaakt als de decoder die meldt |
| Foutratio berichten | Sensor (%, diagnostisch) | Aandeel Mode S-berichten dat niet te decoderen was. Onbekend in een minuut zonder verkeer, want dan is er niets om een aandeel van te nemen |
| Vliegtuigen via ADS-B | Sensor | Vliegtuigen die je hun eigen positie hoort uitzenden |
| Vliegtuigen via MLAT | Sensor | Vliegtuigen die via multilateratie bepaald zijn |
| Vliegtuigen via Mode S | Sensor (diagnostisch) | Vliegtuigen die je hoort, maar die nooit een positie geven |
| Frequentieafwijking | Sensor (ppm, diagnostisch) | Hoe ver de klok van je dongle van zijn nominale frequentie af zit |
| Posities gedecodeerd | Sensor (diagnostisch) | Posities die in het venster geaccepteerd zijn |
| Posities verworpen | Sensor (diagnostisch) | Posities die de plausibiliteitscontrole niet haalden. Een stijgend aandeel wijst op een ruizig signaal |

Hoogtes staan in voet, grondsnelheden in knopen en afstanden in kilometers, zoals dat in de luchtvaart gelezen wordt. Elk daarvan heeft een device class, dus je kunt een losse entiteit omzetten naar meters, mijlen, km/h of mph via **Instellingen → Entiteit → Maateenheid**, en historie en statistieken gaan mee.

De ontvangstcijfers komen uit het kortste meetvenster dat daadwerkelijk een signaal gemeten heeft, normaal `last1min`. Uit welk venster een waarde komt, staat als attribuut `period` op de entiteit.
