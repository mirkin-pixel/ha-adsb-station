# Hardop vragen

"Wat vliegt daar over?" is een vraag die je eerder aan de kamer stelt dan opzoekt op een dashboard — je stelt hem terwijl je naar buiten kijkt. Assist beantwoordt er tien, uit je eigen ontvanger, zonder dat er één verzoek je netwerk verlaat.

| Vraag | En hij zegt |
|---|---|
| *Wat vliegt er over?* | Welk toestel boven je hangt, en hoe hoog |
| *Hoeveel vliegtuigen hoor je?* | Hoeveel er dichtbij zijn, en hoeveel in totaal |
| *Wat is het dichtstbijzijnde vliegtuig?* | Hoe ver weg het is, en in welke richting |
| *Zijn er helikopters in de buurt?* | Militair verkeer, helikopters of drones in bereik |
| *Waar gaat hij heen?* | Waar het toestel boven je vandaan komt en heen gaat |
| *Wat vloog er net over?* | Welk toestel het laatst overkwam, hoe lang geleden en hoe hoog |
| *Wat is het hoogste vliegtuig?* | Welk toestel het hoogst vliegt, en waar |
| *Wat vliegt er het snelst?* | Welk toestel het snelst vliegt, en hoe snel |
| *Hoe ver reikt de antenne?* | Welk toestel het verst weg is: hoe ver het station nu hoort |
| *Is er een noodgeval?* | Of er een toestel een noodgeval meldt, en welk |

De antwoorden gebruiken de namen uit de [meegeleverde tabellen](decoders.md#namen-bij-de-codes), dus hij zegt "KLM 123" en niet "kilo lima mike één twee drie", en ze volgen de [eenheden](configuration.md#eenheden) van het station en niet de taal: meters en kilometers, voet en zeemijl, of voet en mijl.

Engels en Nederlands worden gesproken; een vraag in een andere taal wordt in het Engels beantwoord.

*Wat vloog er net over?* is voor het toestel dat je hoorde en waar je pas naar vraagt als het weg is. Hij noemt het toestel waarvan het dichtste punt het laatst achter je ligt, en telt de tijd vanaf dat moment. Een toestel dat nog nadert is nog niet overgekomen; dan hoor je wat er nu boven je hangt. Het station onthoudt een toestel tot tien minuten nadat het voor het laatst gezien is, en niets over een herstart heen. Na tien stille minuten, of vlak na een herstart, zegt hij dat hij niets heeft horen overvliegen.

Er zijn twee manieren om dit aan te sluiten, en ze komen bij dezelfde tien antwoorden uit. Een [AI-assistent](#een-ai-assistent) krijgt ze ook zonder die twee.

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

Er wordt niets in je configuratiemap geschreven, er hoeft niets herstart, en je kunt de zinnen in de interface aanpassen. `question` is `overhead`, `count`, `closest`, `traffic`, `route`, `last_passage`, `highest`, `fastest`, `furthest`, `emergency` of `aircraft`; `traffic` neemt ook `kind`, en dat is `military`, `helicopter` of `drone`.

`aircraft` gaat over één toestel dat je noemt in het veld met die naam, op hexcode, roepnaam of registratie, zoals het toestel van een [watchlist](watchlist.md)-event: *"KLM 123, een Boeing 737-800, zit 22,3 kilometer naar het noorden, 3.700 meter hoog en stijgend."*, met waar het vandaan komt en heen gaat als de route bekend is. Het is alleen een actie: Assist heeft er geen zinnen voor, omdat een roepnaam niet iets is wat het betrouwbaar verstaat.

De formulering blijft van ons. `adsb_station.speak` geeft een afgemaakte zin terug — callsign gespeld of maatschappij genoemd, hoogte afgerond, eenheden en decimaalteken passend bij de taal — zodat de automatisering drie regels is en geen template vol `round()`.

## De zinsbestanden, zodat Assist de vragen zelf kent

De andere weg heeft geen automatiseringen nodig: Assist herkent alle tien uit zichzelf, in beide talen, ook formuleringen die je zelf niet had bedacht.

De adder zit in waar die zinnen moeten staan. Home Assistant leest ze **alleen uit je configuratiemap**, dus een integratie kan de zijne niet meeleveren; ze zitten erin en moeten één keer gekopieerd worden.

```
custom_components/adsb_station/sentences/en/adsb_station.yaml  →  custom_sentences/en/adsb_station.yaml
custom_components/adsb_station/sentences/nl/adsb_station.yaml  →  custom_sentences/nl/adsb_station.yaml
```

Of laat de integratie ze kopiëren, als je er liever niet naar op zoek gaat:

```yaml
- action: adsb_station.install_sentences
```

Wees helder over wat dat doet: **het schrijft twee bestanden in je configuratiemap** en overschrijft ze als ze er al staan. Het is dezelfde kopie die je met de hand zou maken, en verder wordt er niets aangeraakt. Omdat het in je configuratie schrijft, kan alleen een beheerder het uitvoeren.

Hoe dan ook leest Assist zijn zinnen bij het opstarten, dus draai daarna `conversation.reload` of herstart. Probeer het vervolgens onder **Instellingen → Spraakassistenten**, en vraag het ook eens met een lege lucht — dat is het antwoord dat het vaakst voorkomt.

De kopie gaat niet mee met de integratie. Voegt een update een vraag toe, kopieer de bestanden dan opnieuw of draai `adsb_station.install_sentences` nog een keer, en herlaad; tot dan kent Assist alleen de vragen van de versie die je kopieerde.

Lezen twee van je entries een antenne, dan antwoordt de eerste op naam. Assist is voor een snelle vraag; de [acties](services.md) zijn er als het precies moet. Wil je een tweede station vragen, geef `adsb_station.speak` dan zijn `config_entry` in een automatisering met een eigen zin, zoals [hierboven](#een-automatisering-zonder-enig-bestand).

## Een AI-assistent

Een spraakassistent die via een AI-model praat, zoals OpenAI, Google Gemini, Anthropic of Ollama, met **Assist** aangevinkt in de instellingen van die assistent, krijgt de tien vragen als hulpmiddel, plus één extra: wat een toestel dat je noemt is, waar het is en waar het heen gaat, op roepnaam, registratie of hexcode. *"Waar is KLM 123 nu?"* werkt daar dus, ook al heeft Assist zelf er geen zin voor. Het model kiest de vraag en zegt het antwoord in eigen woorden; de cijfers komen van je ontvanger, en de hulpmiddelen lezen alleen.

Hiervoor zijn geen zinsbestanden nodig. Vanaf Home Assistant 2026.10 biedt de integratie de hulpmiddelen zelf aan; daarvoor gaf Home Assistant ze uit zichzelf door.
