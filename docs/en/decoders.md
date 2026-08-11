# Which decoder

Every decoder gives you the entities above that it has data for; what it reports is detected when you set it up, so no entity is created that could never have a value. That does mean the decoder you run decides how much you get, and **readsb gives you the most**:

| | fr24feed's dump1090 fork | dump1090-fa / SkyAware | readsb + tar1090 |
|---|---|---|---|
| Aircraft, range, message rate | Yes | Yes | Yes |
| Signal, noise, signal-to-noise | Yes | Yes | Yes |
| Gain | No | Yes | Yes |
| Antenna position in `receiver.json` | No | Yes | Yes |
| Emitter category, and how the aircraft was heard | No | Yes | Yes |
| Registration, type, description | No | No | Yes, with an aircraft database |
| Interesting, PIA and LADD markers | No | No | Yes, with an aircraft database |

Two of those are worth spelling out. Without a gain figure you are tuning your dongle blind, and without an antenna position in `receiver.json` the range is measured from the home location of your Home Assistant installation instead of from your antenna, which is fine if they are the same place and wrong if your receiver sits elsewhere.

If you already run `fr24feed` and nothing else, replacing its bundled dump1090 with readsb costs you nothing and adds the gain sensor, the aircraft details and a real antenna position. **Run Reconfigure after upgrading your decoder** to pick up what it can do now.

## The aircraft database

The last two rows need one extra step. readsb only fills in `r`, `t`, `desc` and `dbFlags` when it has been given an aircraft database, and without one the closest aircraft sensor reports a hex code and a callsign but no registration and no type. The military marker is the exception: without a database it is worked out from the address instead, which [the table below](#names-for-the-codes) explains.

On a readsb install, fetch the database and point readsb at it:

```bash
sudo wget -O /usr/local/share/tar1090/aircraft.csv.gz \
  https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz
```

Then add the option to `/etc/default/readsb`, in the arguments readsb is started with:

```
--db-file /usr/local/share/tar1090/aircraft.csv.gz
```

Restart readsb, and the extra fields appear in `aircraft.json` straight away. The integration picks them up on its own: the attributes are added as soon as the decoder sends them, so there is nothing to reconfigure. The database is a snapshot, so refresh it now and then by running the same command again.

## What else the decoder says

Five more attributes ride along with an aircraft, and like the ones above they are only there when the decoder sends them:

| Attribute | What it says |
|---|---|
| `category` | The emitter category the aircraft broadcasts, `A0` to `D7`. `A7` is a helicopter and `B6` a drone, and this is the only place either of them says so |
| `heard_as` | How the decoder came to know about it: `adsb_icao` heard straight off the aircraft, `mlat` worked out from the timing at several receivers, `mode_s` a bare reply with no position in it at all |
| `interesting` | The aircraft database marks this one as worth a look |
| `pia` | A Privacy ICAO Address: a temporary hex code an operator flies under to stay off the lists |
| `ladd` | The American request to limit where the aircraft is displayed |

`category` comes over the air, so it is there without an aircraft database; the last three are the remaining bits of the same `dbFlags` the military marker is bit 0 of. All three are passed on rather than acted on. An aircraft your receiver heard is one it heard, and whether a dashboard leaves a PIA or LADD flight out is yours to decide, not this integration's.

## Names for the codes

An aircraft broadcasts `DLH6CH`, `A20N` and `484123`. None of the three is a name, and no decoder can make one of them, because the names are not in the radio signal at all: they are a list somebody keeps. The integration ships those lists, so the aircraft attributes carry a name without anything being asked over the internet:

| Attribute | Read from | Example |
|---|---|---|
| `airline` | The first three letters of the callsign | `DLH6CH` → `Lufthansa` |
| `airline_code` | Those same three letters, whether or not the table names them | `DLH6CH` → `DLH` |
| `description` | The ICAO type code, where the decoder does not describe it itself | `A20N` → `Airbus A-320neo` |
| `country` | The 24 bit address itself, which ICAO handed out in ranges per country | `484123` → `AW` |

A callsign that is not a flight number names no airline. Business jets, gliders and most light aircraft fly under their registration, so `PHABC` is left alone rather than read as an airline code and turned into whatever `PHA` happens to be.

`airline_code` is there even for an airline the table has never heard of, because the aircraft broadcast it and a dashboard looks a logo up by it. `airline` is only there when the table can put a name to it.

A type code covers a family rather than a single aircraft: an A20N is an A320neo but also the corporate version of it, and a BE20 is any of a dozen King Airs and their military cousins. Nothing in the data says which one you are most likely to see, so the name is the one the code itself spells out. That is right for the airliners and can land on an odd variant for general aviation.

`country` is where an aircraft is registered and not where it is: a KLM aircraft over Spain is still `NL`. Not every address falls in a range — some were never handed out, some belong to no single state, and readsb marks an address it worked out rather than heard with a `~` — and an aircraft in one of those carries no country at all rather than a guess.

That same table says which ranges a country keeps for its own military, which is where the **military marker** comes from when the decoder has no aircraft database. It is the coarser of the two answers: it knows the range and not the aircraft, so a civil aircraft flying inside a military range would be marked along with the rest. So a decoder that does have a database has the last word, in both directions. If `dbFlags` says an aircraft is civil, it is civil, even inside a military range; the address is only asked when nothing else can answer.

Both tables come from the [standing data of Virtual Radar Server](https://github.com/vradarserver/standing-data), which is in the public domain under CC0-1.0. Like the aircraft database above they are a snapshot; `scripts/build_reference.py` regenerates them from the source.
