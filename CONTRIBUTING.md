# Contributing

This file is for people working on the integration. If you are looking for how
to install or configure it, that is the [README](README.md), which is the page
HACS shows, and [`docs/`](docs), which holds a page per subject in English and
Dutch. Both languages are kept side by side: a change to one belongs in the
other, and the README stays short enough to stand on its own.

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

User-facing text lives in `custom_components/adsb_station/strings.json`, and is
mirrored into `translations/en.json` and `translations/nl.json`. The English
two are identical; a change to one belongs in the other. Entity names come from
`translation_key`, never from a hard-coded `name`.

`tests/test_translations.py` holds all of this to account: it fails when the
English two differ, and when any language is missing a key English has or
fills in a different placeholder.

### Adding a language

A new language comes in two parts, and the first is useful on its own.
Announce it with the *New language* issue first, so nobody translates the same
thing twice.

**1. What Home Assistant shows.** Copy `translations/en.json` to
`translations/<code>.json`, where `<code>` is the code Home Assistant uses for
the language: `de`, `fr`, or with a region, `pt-BR`. Translate the values only.
Keys stay as they are, and so does anything in braces, such as `{station}`:
that is filled in when the text is shown. Anything you leave out is shown in
English, but leave nothing out on purpose; the test treats a missing key as a
mistake. `strings.json` is not touched, because it is the English source.

**2. What the station says out loud, and what it understands.** These belong
together: an answer nobody can ask for is no use, and neither is a question
that is answered in English. Both are keyed by the language alone, without a
region, because that is all Home Assistant's language is matched on here: a
`pt` table answers `pt-BR` and `pt-PT` alike.

- In `speech.py`, add a `<code>` entry with every key the `en` entry has to
  `PHRASES` and to `SECTORS`, and one to `_THOUSANDS` and `_DECIMAL`. The last
  two are how the language writes 3,700 and 2.5; get them the wrong way round
  and a height becomes a different number.
- Add `sentences/<code>/adsb_station.yaml`, with `language: <code>` and an
  entry for every intent in the English file. Write the questions the way
  people actually ask them, not as a translation of the English ones; this
  part needs a native or daily speaker more than any other.

**Not part of a translation:** the pages under `docs/` and the README. They are
thirteen pages per language and are kept in English and Dutch only.

The checks in [Checks](#checks) tell you whether everything is there before you
open the pull request.

## Releases

The standard HACS flow: bump `version` in `manifest.json`, merge to the default
branch, then publish a GitHub release with a matching tag, `v0.2.0` for
version `0.2.0`. The release workflow checks that the tag matches the manifest
version and attaches a zip of the integration to the release.
