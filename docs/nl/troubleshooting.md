# Problemen oplossen

## De ontvanger hoort niets

Een werkende ontvanger telt elke seconde berichten, ook 's nachts, omdat de teller alle vliegtuigen meetelt die hij kan horen en niet alleen die in de buurt. Heeft de decoder tien minuten niets geteld, dan gaat **Ontvanger stil** aan en verschijnt er een melding onder **Instellingen → Systeem → Reparaties**. Allebei verdwijnen ze vanzelf zodra er weer berichten binnenkomen.

Het is bijna altijd de dongle. Die is van de USB-bus gevallen, of de host is herstart zonder dat de dongle stroomloos werd, en hij kwam terug in een toestand waar de decoder niet uit kan lezen. Trek hem eruit en steek hem er weer in, of herstart de decoder (`sudo systemctl restart readsb`, of `dump1090-fa`). Een virtuele machine is het gewone geval van het tweede: een herstart van de gast laat het USB-apparaat onder stroom, en alleen eruit trekken zet het terug.

De sensor kijkt naar de teller en niet naar het aantal vliegtuigen, dus een rustige lucht wordt nooit aangezien voor een dode ontvanger. Hij gaat ook aan als de decoder helemaal niet meer antwoordt, zolang er een feeder is om dat te melden. Een station zonder feeder wordt dan als geheel onbeschikbaar, en de melding verschijnt toch.

## Entiteiten blijven onbekend of onbeschikbaar

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

**Diagnostiek downloaden.** Kies op dezelfde pagina **Diagnostische gegevens downloaden**. Het bestand bevat de configuratie en de laatste meting, met het adres van je ontvanger en je feed-alias weggehaald.
