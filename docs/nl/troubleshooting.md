# Problemen oplossen

## Bekende beperkingen

- **Alleen wat je antenne hoort.** Gebouwen en heuvels houden hem tegen, dus het bereik is nooit in elke richting hetzelfde; de [bereikrecords per richting](feeders.md#waar-je-antenne-geblokkeerd-zit) laten zien waar. Vliegtuigen daarbuiten zijn er niet, wat een vluchtvolgsite ook laat zien.
- **Geen antennepositie bij de eigen decoder van fr24feed.** Afstanden worden dan gemeten vanaf de thuislocatie van Home Assistant; **Configureren** zegt welke van de twee in gebruik is. readsb en dump1090-fa publiceren de positie die je ze geeft.
- **Sommige feeders houden geen status op je netwerk bij.** `rbfeeder` van RadarBox, de feeder van ADS-B Exchange en de gratis netwerken (adsb.fi, adsb.lol, airplanes.live) tonen hun status alleen op hun eigen website, dus ze krijgen geen eigen entiteiten. Met readsb laat een sensor **Verbinding** per netwerk wel zien of de verbinding ermee openstaat.
- **Routes en foto's hebben internet nodig**, en alleen als je ze aanzet. Veel privé-, militaire en vrachtvluchten hebben geen bekende route, en van een toestel dat niemand fotografeerde is geen foto.
- **Assist heeft zijn zinbestanden nodig** in je configuratie; zie [Hardop vragen](voice.md). De actie `speak` en AI-assistenten hebben niets nodig.
- **Met twee stations antwoordt Assist vanuit de eerste op naam.** De acties kunnen het station kiezen.

## Veelvoorkomende problemen

### De ontvanger hoort niets

Een werkende dongle levert de decoder 2,4 miljoen samples per seconde, de ruwe radio, of er nu iets vliegt of niet. Heeft hij drie minuten niets geleverd, dan gaat **Ontvanger stil** aan en verschijnt er een melding onder **Instellingen → Systeem → Reparaties**. Allebei verdwijnen ze vanzelf zodra de dongle weer levert.

Het is bijna altijd de dongle. Die is van de USB-bus gevallen, of de host is herstart zonder dat de dongle stroomloos werd, en hij kwam terug in een toestand waar de decoder niet uit kan lezen. Trek hem eruit en steek hem er weer in, of herstart de decoder (`sudo systemctl restart readsb`, of `dump1090-fa`). Een virtuele machine is het gewone geval van het tweede: een herstart van de gast laat het USB-apparaat onder stroom, en alleen eruit trekken zet het terug.

De sensor kijkt naar de samples en niet naar de berichten of de vliegtuigen, dus een rustige lucht wordt nooit aangezien voor een dode ontvanger: een bescheiden antenne kan op een rustige nacht twintig minuten geen enkel bericht horen en toch prima werken. Hij leest ze uit `stats.json`, dus een decoder zonder krijgt deze sensor niet. Hij gaat ook aan als de decoder helemaal niet meer antwoordt, zolang er een feeder is om dat te melden. Een station zonder feeder wordt dan als geheel onbeschikbaar, en de melding verschijnt toch.

### Een tuner die 1090 MHz slecht hoort

readsb kent drie tuners die 1090 MHz slecht ontvangen: de FC0012, FC0013 en FC2580, uit goedkope tv-sticks. Met een daarvan meldt hij dat in `stats.json`, en verschijnt er een reparatiemelding onder **Instellingen → Systeem → Reparaties**. Er is niets kapot; het station hoort alleen veel minder vliegtuigen, en veel minder ver, dan het zou kunnen. Een dongle die voor ADS-B gemaakt is, of een met een R820T-, R828D- of R860-tuner, doet het veel beter. De melding verdwijnt vanzelf zodra readsb het niet meer meldt.

### Afstanden of het bereik kloppen niet

**Oorzaak:** de decoder publiceert geen antennepositie, dus afstanden worden gemeten vanaf de thuislocatie van Home Assistant, en de antenne staat ergens anders.

**Oplossing:** bovenaan **Configureren** staat welk punt gebruikt wordt. Stel de positie in de decoder in (`--lat` en `--lon` van readsb, of de locatie van PiAware op de site van FlightAware), of verplaats de thuislocatie van Home Assistant als die niet klopt. Druk daarna op **Records wissen**, zodat de oude bereiken verdwijnen.

### Assist verstaat een vraag niet

**Oorzaak:** de zinbestanden zijn nooit naar je configuratie gekopieerd, of een update voegde vragen toe nadat je ze kopieerde. Een vraag in een andere taal dan Engels of Nederlands wordt in het Engels beantwoord, maar alleen in die twee verstaan.

**Oplossing:** kijk onder **Instellingen → Systeem → Reparaties** naar de melding over de Assist-zinnen en kies **Opnieuw kopiëren**; of draai `adsb_station.install_sentences` en daarna `conversation.reload`. Zie [Hardop vragen](voice.md).

### Elk vliegtuig wordt dubbel geteld

**Oorzaak:** twee entries lezen dezelfde decoder.

**Oplossing:** houd de decoder aan één entry. Kies bij de andere **Herconfigureren** en laat het veld `aircraft.json` leeg.

### Geen route of foto

**Oorzaak:** het opzoeken staat uit, het vliegtuig is geen van de toestellen die opgezocht worden (dichtbij, op het punt over te komen, op de watchlist, of aangetikt op de kaart), of niemand kent zijn route of heeft hem gefotografeerd.

**Oplossing:** zet het opzoeken aan onder **Configureren**; zie [Waar een vlucht heen gaat](routes.md) en [Hoe hij eruitziet](photos.md) voor welke toestellen er gevraagd worden.

### De kaart ziet er oud uit na een update

**Oorzaak:** de browser of de app heeft de vorige kaart nog.

**Oplossing:** herlaad met Ctrl+Shift+R, of wis de frontend-cache in de instellingen van de app.

### Iets anders: entiteiten blijven onbekend of onbeschikbaar

Verzamel de twee onderstaande zaken en voeg ze toe aan een [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Debug-logging aanzetten.** Ga naar **Instellingen → Apparaten & diensten → ADS-B Station**, klik op de drie puntjes en kies **Debug-logging aanzetten**. Reproduceer het probleem en kies daarna **Debug-logging uitzetten**, en Home Assistant downloadt de log automatisch.

Wil je ook over een herstart heen loggen, zet dan dit in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.adsb_station: debug
```

In de debug-log zie je de HTTP-status van elke poll en elke waarde die de integratie niet kon verwerken.

**Diagnostiek downloaden.** Kies op dezelfde pagina **Diagnostische gegevens downloaden**. Het bestand bevat de configuratie, de laatste meting en wat `receiver.json` zegt over wat de decoder is en kan, met het adres van je ontvanger en je feed-alias weggehaald, en zonder de positie van de antenne.

## De integratie verwijderen

1. Ga naar **Instellingen → Apparaten & diensten → ADS-B Station**, en kies bij elke entry de drie puntjes en **Verwijderen**.
2. Haal de stationskaart van je dashboards, anders toont hij daar een fout.
3. Verwijder de integratie zelf onder **Instellingen → Marktplaats** (HACS vóór 2026.11), en herstart Home Assistant.

Een entry verwijderen neemt mee wat hij onder `.storage` bewaarde: de vliegtuigen die hij hoorde, zijn passages, en wat hij meldde. De laatste verwijderen haalt ook de Assist-zinbestanden weg die de integratie kopieerde, tenzij je ze aanpaste. Automatiseringen en scripts die zijn entiteiten of acties gebruiken zijn van jou, en blijven staan.
