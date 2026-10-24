## What and why

<!-- What changes, and what it is for. Link the issue if there is one. -->

## Checklist

- [ ] `scripts/check.sh` (or `scripts\check.ps1`) passes: ruff, the format check, mypy and the tests.
- [ ] A new behaviour comes with the test that pins it down.
- [ ] Text a user sees is in `strings.json`, `translations/en.json` and `translations/nl.json`, and a change to `docs/en` has its counterpart in `docs/nl`. The tests check both. No Dutch? Put the English text in the Dutch file and say so here; it gets translated before the merge.
- [ ] Nothing in [what 1.0 promises](https://github.com/mirkin-pixel/ha-adsb-station/blob/main/CONTRIBUTING.md#what-a-version-number-promises) breaks: no unique ID, action field or event field renamed or removed.
