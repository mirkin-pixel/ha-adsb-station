"""Tests that every language says everything English says.

A translation arrives as a file someone copied and filled in, and the way it
goes wrong is quiet: a key the copy predates, a placeholder translated along
with the sentence around it, a language with words but no way to write a
number. Home Assistant shows the English text for a missing entity name, but
a missing spoken phrase is a `KeyError` in the middle of an answer, and a
renamed placeholder is one in the middle of a notification.

So each layer is compared against English by its keys and its placeholders.
Whether the words are good is a matter for review; whether they are all there
is a matter of counting.
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


def _same_shape(english: dict[str, str], other: dict[str, str], where: str) -> None:
    """Assert that a translation has English's keys, and its placeholders."""
    missing = sorted(english.keys() - other.keys())
    extra = sorted(other.keys() - english.keys())
    assert not missing, f"{where} is missing {missing}"
    assert not extra, f"{where} has keys English does not: {extra}"
    for key, text in english.items():
        assert _placeholders(other[key]) == _placeholders(text), (
            f"{where} {key} fills in {sorted(_placeholders(other[key]))}, "
            f"English fills in {sorted(_placeholders(text))}"
        )


def test_english_is_the_source() -> None:
    """Test that en.json is strings.json, word for word."""
    assert _load(TRANSLATIONS / "en.json") == _load(INTEGRATION / "strings.json")


@pytest.mark.parametrize(
    "path", sorted(TRANSLATIONS.glob("*.json")), ids=lambda path: path.stem
)
def test_every_translation_has_every_text(path: Path) -> None:
    """Test that a translation file has the keys and placeholders of English."""
    _same_shape(
        _flatten(_load(INTEGRATION / "strings.json")),
        _flatten(_load(path)),
        path.name,
    )


@pytest.mark.parametrize("language", sorted(PHRASES))
def test_every_language_can_say_everything(language: str) -> None:
    """Test that a spoken language has every phrase and every direction."""
    _same_shape(PHRASES[DEFAULT_LANGUAGE], PHRASES[language], f"PHRASES[{language}]")
    _same_shape(SECTORS[DEFAULT_LANGUAGE], SECTORS[language], f"SECTORS[{language}]")


def test_every_spoken_language_can_write_a_number() -> None:
    """Test that the number tables cover the same languages as the phrases."""
    assert set(SECTORS) == set(PHRASES)
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
