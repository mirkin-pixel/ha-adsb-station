# Troubleshooting

## The receiver hears nothing

A working receiver counts messages every second, at night as well, because the counter takes in every aircraft it can hear and not only the ones nearby. When the decoder has counted nothing for ten minutes, **Receiver silent** turns on and a repair appears under **Settings → System → Repairs**. Both clear on their own as soon as messages come in again.

It is nearly always the dongle. It dropped off the USB bus, or the host was rebooted without the dongle losing power, and it came back in a state the decoder cannot read from. Unplug it and plug it back in, or restart the decoder (`sudo systemctl restart readsb`, or `dump1090-fa`). A virtual machine is the usual case of the second: restarting the guest leaves the USB device powered, and only taking it out resets it.

The sensor watches the counter rather than the number of aircraft, so a quiet sky is never mistaken for a dead receiver. It also turns on when the decoder stops answering at all, with a feeder still there to say so. A station without a feeder becomes unavailable as a whole instead, and the repair appears all the same.

## Entities stay unknown or unavailable

Collect the two things below and attach them to an [issue](https://github.com/mirkin-pixel/ha-adsb-station/issues).

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
