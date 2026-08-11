# Troubleshooting

If entities stay `unknown` or `unavailable`, collect the two things below and attach them to an [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

**Enable debug logging.** Go to **Settings → Devices & services → ADS-B Station**, click the three dots and choose **Enable debug logging**. Reproduce the problem, then choose **Disable debug logging**, and Home Assistant downloads the log automatically.

To log across a restart, add this to `configuration.yaml` instead:

```yaml
logger:
  default: warning
  logs:
    custom_components.adsb_station: debug
```

Debug logging shows the HTTP status of every poll and any value the integration could not parse.

**Download diagnostics.** On the same page, choose **Download diagnostics**. The file contains the configuration and the last poll, with the address of your receiver and your feed alias redacted.
