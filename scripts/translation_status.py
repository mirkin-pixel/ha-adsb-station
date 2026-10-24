"""Write down how far each translation has come, as Markdown.

English is the source. Every other language may lag behind it, because Home
Assistant shows the English text for anything a translation lacks and so
does the spoken side, so a new text can land before anybody has translated
it. What this is for is making the lag visible: a table per language, and
the texts each one is missing, with the English to translate from.

    python scripts/translation_status.py

The Translation status issue is this output, rewritten on every push to the
default branch, and a pull request shows it in the summary of its run.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.adsb_station.speech import (  # noqa: E402
    DEFAULT_LANGUAGE,
    PHRASES,
    SECTORS,
)

INTEGRATION = ROOT / "custom_components" / "adsb_station"
REPOSITORY = "https://github.com/mirkin-pixel/ha-adsb-station"


def _flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Return every text in a translation file by its dotted key."""
    texts: dict[str, str] = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            texts |= _flatten(value, f"{prefix}{key}.")
        else:
            texts[f"{prefix}{key}"] = value
    return texts


def _read(path: Path) -> dict[str, str]:
    """Return every text in one translation file."""
    return _flatten(json.loads(path.read_text("utf-8")))


def sources(integration: Path = INTEGRATION) -> dict[str, dict[str, dict[str, str]]]:
    """Return every part that can be translated, per language, English included."""
    files = {
        path.stem: _read(path)
        for path in sorted((integration / "translations").glob("*.json"))
    }
    # strings.json is the English source; en.json is held to it by the tests.
    files[DEFAULT_LANGUAGE] = _read(integration / "strings.json")
    return {
        "Texts in Home Assistant": files,
        "Spoken answers": dict(PHRASES),
        "Compass directions": dict(SECTORS),
    }


def missing(
    parts: dict[str, dict[str, dict[str, str]]],
) -> dict[str, dict[str, dict[str, str] | None]]:
    """Return, per language and part, what is missing, with the English.

    None for a part the language has not started at all, which is different
    from a part it has finished.
    """
    languages = sorted({code for part in parts.values() for code in part})
    return {
        language: {
            label: (
                None
                if language not in part
                else {
                    key: text
                    for key, text in part[DEFAULT_LANGUAGE].items()
                    if key not in part[language]
                }
            )
            for label, part in parts.items()
        }
        for language in languages
        if language != DEFAULT_LANGUAGE
    }


def render(parts: dict[str, dict[str, dict[str, str]]]) -> str:
    """Return the status as Markdown."""
    totals = {label: len(part[DEFAULT_LANGUAGE]) for label, part in parts.items()}
    status = missing(parts)

    lines = [
        "English is the source. Every other language may lag behind it: Home "
        "Assistant shows the English text for anything a translation lacks, "
        "and so does the spoken side. This is what each language is missing.",
        "",
        "To help, see [adding a language]"
        f"({REPOSITORY}/blob/main/CONTRIBUTING.md#adding-a-language), or offer "
        f"a new one with the [New language]"
        f"({REPOSITORY}/issues/new?template=new_language.yml) form.",
        "",
        "| Language | " + " | ".join(totals) + " |",
        "|---|" + "---|" * len(totals),
    ]
    for language, gaps in status.items():
        cells = []
        for label, total in totals.items():
            gap = gaps[label]
            if gap is None:
                cells.append("not started")
            elif not gap:
                cells.append("complete")
            else:
                cells.append(f"{total - len(gap)} of {total}")
        lines.append(f"| `{language}` | " + " | ".join(cells) + " |")

    for language, gaps in status.items():
        for label, gap in gaps.items():
            if not gap:
                continue
            lines += [
                "",
                "<details>",
                f"<summary><code>{language}</code>: {label.lower()}, "
                f"{len(gap)} to translate</summary>",
                "",
                "| Key | English |",
                "|---|---|",
                *(f"| `{key}` | {_cell(text)} |" for key, text in gap.items()),
                "",
                "</details>",
            ]
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    """Return a text that fits in one table cell."""
    return text.replace("|", "&#124;").replace("\n", " ")


if __name__ == "__main__":
    sys.stdout.write(render(sources()))
