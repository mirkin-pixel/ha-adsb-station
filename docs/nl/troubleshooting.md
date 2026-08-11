# Problemen oplossen

Blijven entiteiten op `unknown` of `unavailable` staan? Verzamel dan de twee onderstaande zaken en voeg ze toe aan een [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

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
