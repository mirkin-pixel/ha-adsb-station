# Troubleshooting

## Known limitations

- **Only what your antenna hears.** Buildings and hills block it, so the range is never the same in every direction; the [range records per direction](feeders.md#where-your-antenna-is-blocked) show where. Aircraft beyond it are not there, whatever a flight tracking website shows.
- **No antenna position from fr24feed's own decoder.** Distances are then measured from the home location of Home Assistant; **Configure** says which of the two is in use. readsb and dump1090-fa publish the position you give them.
- **Some feeders keep no status on your network.** RadarBox's `rbfeeder`, the ADS-B Exchange feeder and the free networks (adsb.fi, adsb.lol, airplanes.live) show their state only on their own websites, so they get no entities of their own. With readsb, a **Connection** sensor per network does show whether the connection to it is up.
- **Routes and photos need the internet**, and only once you switch them on. Many private, military and cargo flights have no known route, and an airframe nobody photographed has no photo.
- **Assist needs its sentence files copied** into your configuration; see [Asking out loud](voice.md). The `speak` action and AI assistants need nothing.
- **With two stations, Assist answers from the first by name.** The actions can pick the station.

## Common problems

### The receiver hears nothing

A working dongle hands the decoder 2.4 million samples a second, the raw radio, whether or not anything is flying. When it has delivered nothing for three minutes, **Receiver silent** turns on and a repair appears under **Settings → System → Repairs**. Both clear on their own as soon as the dongle delivers again.

It is nearly always the dongle. It dropped off the USB bus, or the host was rebooted without the dongle losing power, and it came back in a state the decoder cannot read from. Unplug it and plug it back in, or restart the decoder (`sudo systemctl restart readsb`, or `dump1090-fa`). A virtual machine is the usual case of the second: restarting the guest leaves the USB device powered, and only taking it out resets it.

The sensor watches the samples rather than the messages or the aircraft, so a quiet sky is never mistaken for a dead receiver: a modest antenna can hear no message at all for twenty minutes on a quiet night, and still be fine. It reads them from `stats.json`, so a decoder without one gets no such sensor. It also turns on when the decoder stops answering at all, with a feeder still there to say so. A station without a feeder becomes unavailable as a whole instead, and the repair appears all the same.

### A tuner that hears 1090 MHz badly

readsb knows three tuners that receive 1090 MHz badly: the FC0012, FC0013 and FC2580, from cheap TV sticks. With one of those it says so in `stats.json`, and a repair appears under **Settings → System → Repairs**. Nothing is broken; the station just hears far fewer aircraft, and far less far, than it could. A dongle made for ADS-B, or one with an R820T, R828D or R860 tuner, does much better. The repair goes away by itself once readsb no longer reports it.

### Distances or the range look wrong

**Cause:** the decoder publishes no antenna position, so distances are measured from the home location of Home Assistant, and the antenna stands somewhere else.

**Fix:** the top of **Configure** says which point is used. Set the position in the decoder (readsb's `--lat` and `--lon`, or PiAware's location on FlightAware's site), or move the home location of Home Assistant if that is wrong. Then press **Reset records**, so the old ranges go.

### Assist does not understand a question

**Cause:** the sentence files were never copied into your configuration, or an update added questions after you copied them. A question in another language than English or Dutch is answered in English, but only understood in those two.

**Fix:** look under **Settings → System → Repairs** for the message about the Assist sentences and choose **Copy them again**; or run `adsb_station.install_sentences` and then `conversation.reload`. See [Asking out loud](voice.md).

### Every aircraft is counted twice

**Cause:** two entries read the same decoder.

**Fix:** keep the decoder on one entry. On the other, choose **Reconfigure** and leave the `aircraft.json` field empty.

### No route or photo

**Cause:** the lookup is off, the aircraft is none of the ones looked up (nearby, about to come over, on the watchlist, or tapped on the card), or nobody knows its route or has photographed it.

**Fix:** switch the lookup on under **Configure**; see [Where a flight is going](routes.md) and [What it looks like](photos.md) for which aircraft are asked about.

### The card looks old after an update

**Cause:** the browser or the companion app still has the previous card.

**Fix:** reload with Ctrl+Shift+R, or reset the frontend cache in the companion app's settings.

### Something else: entities stay unknown or unavailable

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

**Download diagnostics.** On the same page, choose **Download diagnostics**. The file contains the configuration, the last poll and what `receiver.json` says the decoder is and can do, with the address of your receiver and your feed alias redacted, and without the antenna's position.

## Removing the integration

1. Go to **Settings → Devices & services → ADS-B Station**, and on each entry choose the three dots and **Delete**.
2. Take the station card off your dashboards, or it shows an error where it was.
3. Remove the integration itself under **Settings → Marketplace** (HACS before 2026.11), and restart Home Assistant.

Deleting an entry takes along what it kept under `.storage`: the aircraft it heard, its passages, and what it announced. Deleting the last one also removes the Assist sentence files the integration copied, unless you changed them. Automations and scripts that use its entities or actions are yours, and stay.
