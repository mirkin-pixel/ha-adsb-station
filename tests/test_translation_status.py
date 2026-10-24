"""Tests for the translation status the issue is written from."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "translation_status.py"


def _script() -> ModuleType:
    """Load the script the way the workflow runs it."""
    spec = importlib.util.spec_from_file_location("translation_status", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_what_is_missing_comes_with_the_english() -> None:
    """Test that a gap is listed with the text to translate from."""
    script = _script()
    parts = {
        "Texts": {
            "en": {"a": "Aircraft", "b": "Range"},
            "nl": {"a": "Vliegtuigen"},
            "de": {"a": "Flugzeuge", "b": "Reichweite"},
        },
        "Spoken": {"en": {"x": "Nothing"}, "nl": {"x": "Niets"}},
    }

    assert script.missing(parts) == {
        "de": {"Texts": {}, "Spoken": None},
        "nl": {"Texts": {"b": "Range"}, "Spoken": {}},
    }

    table = script.render(parts)
    assert "| `de` | complete | not started |" in table
    assert "| `nl` | 1 of 2 | complete |" in table
    assert "<code>nl</code>: texts, 1 to translate" in table
    assert "| `b` | Range |" in table


def test_the_shipped_languages_are_counted() -> None:
    """Test the real tables: Dutch is there, and English is not a row."""
    script = _script()
    table = script.render(script.sources())

    assert "| `nl` |" in table
    assert "| `en` |" not in table
