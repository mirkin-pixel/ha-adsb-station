# Hardop vragen

"Wat vliegt daar over?" is een vraag die je eerder aan de kamer stelt dan opzoekt op een dashboard — je stelt hem terwijl je naar buiten kijkt. Assist beantwoordt er vijf, uit je eigen ontvanger, zonder dat er één verzoek je netwerk verlaat.

| Vraag | En hij zegt |
|---|---|
| *Wat vliegt er over?* | Welk toestel boven je hangt, en hoe hoog |
| *Hoeveel vliegtuigen hoor je?* | Hoeveel er dichtbij zijn, en hoeveel in totaal |
| *Wat is het dichtstbijzijnde vliegtuig?* | Hoe ver weg het is, en in welke richting |
| *Zijn er helikopters in de buurt?* | Militair verkeer, helikopters of drones in bereik |
| *Waar gaat hij heen?* | Waar het toestel boven je vandaan komt en heen gaat |

De antwoorden gebruiken de namen uit de [meegeleverde tabellen](decoders.md#namen-bij-de-codes), dus hij zegt "KLM 123" en niet "kilo lima mike één twee drie", en ze volgen het eenhedenstelsel van je Home Assistant en niet de taal: meters en kilometers, of voet en mijl.

Engels en Nederlands worden gesproken; een vraag in een andere taal wordt in het Engels beantwoord.

Er zijn twee manieren om dit aan te sluiten, en ze komen bij dezelfde vijf antwoorden uit.

## Een automatisering, zonder enig bestand

Home Assistant laat een automatisering zijn eigen zinnen bezitten. Schrijf ze waar je ze kunt zien, vraag deze integratie om het antwoord, en zeg het terug:

```yaml
automation:
  triggers:
    - trigger: conversation
      command:
        - "wat vliegt er over"
        - "wat hangt er boven me"
  actions:
    - action: adsb_station.speak
      data:
        question: overhead
      response_variable: spoken
    - set_conversation_response: "{{ spoken.speech }}"
```

Er wordt niets in je configuratiemap geschreven, er hoeft niets herstart, en je kunt de zinnen in de interface aanpassen. `question` is `overhead`, `count`, `closest`, `traffic` of `route`; die laatste-op-een-na neemt ook `kind`, en dat is `military`, `helicopter` of `drone`.

De formulering blijft van ons. `adsb_station.speak` geeft een afgemaakte zin terug — callsign gespeld of maatschappij genoemd, hoogte afgerond, eenheden en decimaalteken passend bij de taal — zodat de automatisering drie regels is en geen template vol `round()`.

## De zinsbestanden, zodat Assist de vragen zelf kent

De andere weg heeft geen automatiseringen nodig: Assist herkent alle vijf uit zichzelf, in beide talen, ook formuleringen die je zelf niet had bedacht.

De adder zit in waar die zinnen moeten staan. Home Assistant leest ze **alleen uit je configuratiemap**, dus een integratie kan de zijne niet meeleveren; ze zitten erin en moeten één keer gekopieerd worden.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Of laat de integratie ze kopiëren, als je er liever niet naar op zoek gaat:

```yaml
- action: adsb_station.install_sentences
```

Wees helder over wat dat doet: **het schrijft twee bestanden in je configuratiemap** en overschrijft ze als ze er al staan. Het is dezelfde kopie die je met de hand zou maken, en verder wordt er niets aangeraakt.

Hoe dan ook leest Assist zijn zinnen bij het opstarten, dus draai daarna `conversation.reload` of herstart. Probeer het vervolgens onder **Instellingen → Spraakassistenten**, en vraag het ook eens met een lege lucht — dat is het antwoord dat het vaakst voorkomt.

Lezen twee van je entries een antenne, dan antwoordt de eerste op naam. Assist is voor een snelle vraag; de [acties](services.md) zijn er als het precies moet.
