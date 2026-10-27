# Contributing

This file is for people working on the integration. If you are looking for how
to install or configure it, that is the [README](README.md), which is the page
HACS shows, and [`docs/`](docs), which holds a page per subject in English and
Dutch. Both languages are kept side by side: a change to one belongs in the
other, and the README stays short enough to stand on its own. If you do not
write Dutch, put your English text in the Dutch page as well and say so in the
pull request; it is translated before the merge.

Contributions are welcome. An issue first is appreciated for anything larger
than a fix, so nobody writes the same thing twice.

## Getting set up

Python 3.14 or newer, and nothing else:

```bash
python -m venv .venv
. .venv/bin/activate          # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements_test.txt
```

There is no Home Assistant installation to keep alongside this. The tests bring
their own through
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component),
which pins the Home Assistant version they run against.

## Checks

```bash
ruff check .        # style and imports
ruff format .       # layout; CI runs it with --check
mypy                # types, over custom_components/adsb_station
pytest --cov        # tests, and the coverage floor
```

`scripts/check.sh` and `scripts/check.ps1` run all three in that order.

### The oldest supported Home Assistant

`hacs.json` says which Home Assistant this needs at least: 2025.7. CI runs the
tests against that release too, on the Python 3.13 it runs on, from
`tests/oldest/requirements.txt`. That file sits outside the root on purpose:
Dependabot updates every requirements file in the root, and a pin it raised
would quietly stop testing the oldest release at all. Two things follow from it. The code may not use
anything newer than Python 3.13, which ruff enforces through `target-version`.
And it may not lean on a Home Assistant API that 2025.7 lacks; the tests that
need one, such as asking the device registry for an entry's own device, go
through a helper in `tests/conftest.py` that falls back on what the old release
has. Raising the minimum is allowed in a minor version: change `hacs.json`, the
README and `tests/oldest/requirements.txt` together.

That is everything CI can tell you about the code, so there is no need to push
a branch to find out whether something is broken. Two workflow jobs are left
over, hassfest and HACS validation, and they check the manifest and the
repository layout rather than the code. Both run as containers, so they stay in
CI; nothing they check changes on a normal code change.

Coverage has a floor of 95% over `custom_components/adsb_station`, set in
`pyproject.toml`. It is a floor rather than a target: a new branch of behaviour
is expected to arrive with the test that pins it down.

### Windows

The tests run there too, even though Home Assistant itself only ever runs on
Linux and imports two modules CPython ships on POSIX alone. `pytest_windows.py`
stands in for `fcntl` and `resource`, and lets the event loop have the loopback
socket pair it wakes itself over, which `pytest-socket` would otherwise refuse.
It is loaded through `addopts` in `pyproject.toml` and does nothing at all on
Linux, so the same `pytest` runs in both places.

## How the code is laid out

| File | What lives there |
|---|---|
| `api.py` | Reading the local endpoints, and detecting which ones exist |
| `coordinator.py` | One poll cycle, and everything derived from it |
| `route.py` | The optional route lookup, and the only code that leaves your network |
| `reference.py` | The shipped tables that name an airline code and a type code |
| `sensor.py`, `binary_sensor.py`, `button.py` | The entities |
| `config_flow.py` | Setting a station up, reconfiguring it, and its options |
| `const.py` | Constants, and the table of feeder kinds |

Two things are worth knowing before changing much:

- **A poll must not fail over something optional.** The feeder is the primary
  source when there is one, and the receiver when there is not. Anything else
  that cannot be read degrades to `None` and logs once, rather than taking the
  entities with it.
- **Decoders disagree about field names.** The dump1090 fork that fr24feed
  ships reports `altitude` and `speed`; dump1090-fa and readsb report
  `alt_baro` and `gs`. Both are read, and a new field should assume the same.

## The reference tables

`airlines.json`, `aircraft_models.json` and `code_blocks.json` are generated,
not edited. They turn the codes an aircraft broadcasts into names, and they are
committed rather than fetched at runtime, because asking a service for
something that never changes would be a request per aircraft for data that fits
in a file.

```bash
python scripts/build_reference.py
```

That reads the [standing data of Virtual Radar
Server](https://github.com/vradarserver/standing-data), which is CC0-1.0, and
rewrites all three files sorted so a regeneration makes a readable diff.
Refreshing them is a commit of its own; the script's docstring explains how it
picks one row out of the several that share a type code, and why the address
blocks are flattened before they are written rather than searched as they come.

## Translations

**English is the source**, as it is for the rest of Home Assistant. User-facing
text lives in `custom_components/adsb_station/strings.json`, and is mirrored
into `translations/en.json`; the two are identical, so a change to one belongs
in the other. Entity names come from `translation_key`, never from a hard-coded
`name`.

That is all a contribution has to do. Every other language, Dutch included,
may lag behind: Home Assistant shows the English text for anything a
translation lacks, and the spoken answers fall back to English phrase by
phrase. What each language is missing is kept up to date in the
[Translation status](https://github.com/mirkin-pixel/ha-adsb-station/issues?q=is%3Aissue+is%3Aopen+label%3Atranslation+%22Translation+status%22) issue, written by
`scripts/translation_status.py` on every push to `main`. A pull request shows
the same table in the summary of its *Translation status* run.

`tests/test_translations.py` holds the rest to account. It fails when the two
English files differ, and when a translation is wrong rather than behind: a
key English no longer has, or a placeholder English does not fill in.

### Adding a language

A new language comes in two parts, and the first is useful on its own.
Announce it with the *New language* issue first, so nobody translates the same
thing twice.

**1. What Home Assistant shows.** Copy `translations/en.json` to
`translations/<code>.json`, where `<code>` is the code Home Assistant uses for
the language: `de`, `fr`, or with a region, `pt-BR`. Translate the values only.
Keys stay as they are, and so does anything in braces, such as `{station}`:
that is filled in when the text is shown. Anything you leave out is shown in
English and listed in the status issue, so a partial translation is welcome
and can be finished later, by you or someone else. `strings.json` is not
touched, because it is the English source.

**2. What the station says out loud, and what it understands.** These belong
together: an answer nobody can ask for is no use, and neither is a question
that is answered in English. Both are keyed by the language alone, without a
region, because that is all Home Assistant's language is matched on here: a
`pt` table answers `pt-BR` and `pt-PT` alike.

- In `speech.py`, add a `<code>` entry to `PHRASES` and to `SECTORS` with the
  keys of the `en` entry; a phrase you leave out is said in English. Add one
  to `_THOUSANDS` and `_DECIMAL` as well, which are required: they are how the
  language writes 3,700 and 2.5, and the wrong way round turns a height into a
  different number.
- Add `sentences/<code>/adsb_station.yaml`, with `language: <code>` and an
  entry for every intent in the English file. Write the questions the way
  people actually ask them, not as a translation of the English ones; this
  part needs a native or daily speaker more than any other.

**Not part of a translation:** the pages under `docs/` and the README. They are
thirteen pages per language and are kept in English and Dutch only.

The checks in [Checks](#checks) tell you whether what is there fits, and
`python scripts/translation_status.py` what is still left, before you open the
pull request.

## What a version number promises

From 1.0 on, the version says whether an upgrade can break something you
built. Automations, dashboards and templates lean on the integration in a few
places, and those stay as they are until the next major version:

- **Entities keep their identity.** A unique ID is never changed, so the
  entity ID, its history and anything that refers to it survive every
  upgrade. An entity is not removed and does not change what it measures or
  its unit.
- **Attributes keep their name and meaning.** A template reading
  `state_attr(..., 'altitude')` keeps working.
- **Actions keep their name, their fields and their response.**
  `adsb_station.look_up_aircraft`, `list_aircraft`, `speak` and
  `install_sentences`.
- **Events keep their name and their data.** `adsb_station_aircraft_passage`,
  `adsb_station_watchlist_match` and `adsb_station_aircraft_approaching`.
- **A configured station keeps working.** An older entry is migrated in
  place, as every version before 1.0 already did, and never has to be
  removed and set up again.

What a minor version may do, because none of it breaks what is already there:
add entities, attributes, fields and events; change a display name or a
translation, since the entity ID is not taken from it after setup; and ask
for a newer Home Assistant, which HACS checks before it offers the update.

Anything else is a major version, with the change and what to do about it at
the top of the release notes. A patch version only fixes what did not work as
documented.

## Releases

The standard HACS flow: bump `version` in `manifest.json`, merge to the default
branch, then publish a GitHub release with a matching tag, `v1.0.0` for
version `1.0.0`. The release workflow checks that the tag matches the manifest
version and attaches a zip of the integration to the release.
