"""Tests that every language is a faithful copy of English, however far along.

English is the source, as it is for the rest of Home Assistant. Another
language may lack a text: Home Assistant shows the English one instead, and
so does the spoken side, so a contribution only has to be written in English
and the translations catch up after. What `scripts/translation_status.py`
reports is that lag, and nothing here fails on it.

What a translation may not do is be wrong rather than behind: carry a key
English no longer has, which is a text nobody will ever see, or fill in a
placeholder English does not, which fails the moment the text is shown. A
language with words but no way to write a number is wrong too, because the
number would come out in another language's notation. Whether the words are
good is a matter for review; whether they fit is a matter of counting.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any

import pytest

from custom_components.adsb_station.speech import (
    _DECIMAL,
    _THOUSANDS,
    DEFAULT_LANGUAGE,
    PHRASES,
    SECTORS,
)

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "adsb_station"
TRANSLATIONS = INTEGRATION / "translations"


def _load(path: Path) -> dict[str, Any]:
    """Return one translation file."""
    return json.loads(path.read_text("utf-8"))


def _flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Return every text in a translation file by its dotted key."""
    texts: dict[str, str] = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            texts |= _flatten(value, f"{prefix}{key}.")
        else:
            texts[f"{prefix}{key}"] = value
    return texts


def _placeholders(text: str) -> set[str]:
    """Return the names a text expects to be filled in."""
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def _fits(english: dict[str, str], other: dict[str, str], where: str) -> None:
    """Assert that a translation has no key English lacks, and its placeholders."""
    extra = sorted(other.keys() - english.keys())
    assert not extra, f"{where} has keys English does not: {extra}"
    for key, text in other.items():
        assert _placeholders(text) == _placeholders(english[key]), (
            f"{where} {key} fills in {sorted(_placeholders(text))}, "
            f"English fills in {sorted(_placeholders(english[key]))}"
        )


def test_english_is_the_source() -> None:
    """Test that en.json is strings.json, word for word."""
    assert _load(TRANSLATIONS / "en.json") == _load(INTEGRATION / "strings.json")


@pytest.mark.parametrize(
    "path", sorted(TRANSLATIONS.glob("*.json")), ids=lambda path: path.stem
)
def test_every_translation_fits_english(path: Path) -> None:
    """Test that a translation file has only English's keys and placeholders."""
    _fits(
        _flatten(_load(INTEGRATION / "strings.json")),
        _flatten(_load(path)),
        path.name,
    )


@pytest.mark.parametrize("language", sorted(PHRASES))
def test_every_spoken_language_fits_english(language: str) -> None:
    """Test that a spoken language has only English's phrases and directions."""
    _fits(PHRASES[DEFAULT_LANGUAGE], PHRASES[language], f"PHRASES[{language}]")
    _fits(
        SECTORS[DEFAULT_LANGUAGE],
        SECTORS.get(language, {}),
        f"SECTORS[{language}]",
    )


def test_english_says_everything() -> None:
    """Test that the source itself is whole, since every gap falls back on it."""
    assert set(SECTORS[DEFAULT_LANGUAGE]) == {
        "n",
        "ne",
        "e",
        "se",
        "s",
        "sw",
        "w",
        "nw",
    }
    assert all(PHRASES[DEFAULT_LANGUAGE].values())


def test_every_spoken_language_can_write_a_number() -> None:
    """Test that the number tables cover the same languages as the phrases."""
    assert set(SECTORS) <= set(PHRASES)
    assert set(_THOUSANDS) == set(PHRASES)
    assert set(_DECIMAL) == set(PHRASES)


def test_every_spoken_language_is_one_home_assistant_can_hand_over() -> None:
    """Test that a spoken language is a base code, the only kind we match.

    `language_of` reads `pt-BR` as `pt`, so a table keyed `pt-BR` would never
    be spoken. The JSON files can carry a region; the tables cannot.
    """
    for language in PHRASES:
        assert language.isalpha(), language
        assert language == language.lower(), language
