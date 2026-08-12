"""Tests that read the shipped sentence files the way Home Assistant does.

Everything else about the voice questions is tested by handing an intent its
slots directly, which is the right way to test a handler and says nothing at
all about the files. Those reach Home Assistant as text, are parsed by
`hassil`, and a mistake in one of them is only found by trying it: a list
written `<kind>` instead of `{kind}` is valid YAML, names an intent that
exists, and matches nothing whatsoever.
"""

from __future__ import annotations

from pathlib import Path

from hassil import Intents, recognize
import pytest
import yaml

from custom_components.adsb_station.intent import (
    INTENT_CLOSEST,
    INTENT_COUNT,
    INTENT_OVERHEAD,
    INTENT_ROUTE,
    INTENT_TRAFFIC,
    TRAFFIC_KINDS,
)
from custom_components.adsb_station.services import (
    SENTENCES_DIRECTORY,
    SENTENCES_FILE,
)
from custom_components.adsb_station.speech import PHRASES

SENTENCES = (
    Path(__file__).parent.parent
    / "custom_components"
    / "adsb_station"
    / SENTENCES_DIRECTORY
)

# What somebody would actually say, rather than the sentences written down.
# Each of these is a phrasing the file has to cover, and between them they
# reach every intent and every kind of traffic.
SPOKEN: dict[str, list[tuple[str, str, str | None]]] = {
    "en": [
        ("what is flying over", INTENT_OVERHEAD, None),
        ("what is above me right now", INTENT_OVERHEAD, None),
        ("is there anything overhead", INTENT_OVERHEAD, None),
        ("how many aircraft are there", INTENT_COUNT, None),
        ("how many planes are nearby", INTENT_COUNT, None),
        ("how busy is the sky", INTENT_COUNT, None),
        ("what is the closest aircraft", INTENT_CLOSEST, None),
        ("how far away is the nearest plane", INTENT_CLOSEST, None),
        ("are there any helicopters nearby", INTENT_TRAFFIC, "helicopter"),
        ("are there helicopters nearby", INTENT_TRAFFIC, "helicopter"),
        ("is there a helicopter up there", INTENT_TRAFFIC, "helicopter"),
        ("can you hear any drones", INTENT_TRAFFIC, "drone"),
        ("any military traffic", INTENT_TRAFFIC, "military"),
        ("where is it going", INTENT_ROUTE, None),
        ("what is the route of the aircraft overhead", INTENT_ROUTE, None),
    ],
    "nl": [
        ("wat vliegt er over", INTENT_OVERHEAD, None),
        ("wat vliegt er boven ons", INTENT_OVERHEAD, None),
        ("hangt er iets boven me", INTENT_OVERHEAD, None),
        ("hoeveel vliegtuigen zijn er", INTENT_COUNT, None),
        ("hoeveel toestellen zijn er in de buurt", INTENT_COUNT, None),
        ("hoe druk is het in de lucht", INTENT_COUNT, None),
        ("wat is het dichtstbijzijnde vliegtuig", INTENT_CLOSEST, None),
        ("hoe ver weg is het dichtstbije toestel", INTENT_CLOSEST, None),
        ("zijn er helikopters in de buurt", INTENT_TRAFFIC, "helicopter"),
        ("is er een helikopter dichtbij", INTENT_TRAFFIC, "helicopter"),
        ("hoor je een drone", INTENT_TRAFFIC, "drone"),
        ("is er militair verkeer in de buurt", INTENT_TRAFFIC, "military"),
        ("zijn er drones", INTENT_TRAFFIC, "drone"),
        ("waar gaat hij heen", INTENT_ROUTE, None),
        ("waar komt het vliegtuig boven me vandaan", INTENT_ROUTE, None),
    ],
}


def _intents(language: str) -> Intents:
    """Parse one shipped file the way the conversation agent parses it."""
    payload = yaml.safe_load(
        (SENTENCES / language / SENTENCES_FILE).read_text("utf-8")
    )
    return Intents.from_dict(payload)


@pytest.mark.parametrize("language", sorted(PHRASES))
def test_the_files_parse(language: str) -> None:
    """Test that the sentences are sentences, and name the intents we have."""
    intents = _intents(language)

    assert set(intents.intents) == {
        INTENT_OVERHEAD,
        INTENT_COUNT,
        INTENT_CLOSEST,
        INTENT_TRAFFIC,
        INTENT_ROUTE,
    }


@pytest.mark.parametrize("language", sorted(PHRASES))
def test_what_somebody_would_say(language: str) -> None:
    """Test that each phrasing reaches the intent it is meant for."""
    intents = _intents(language)

    for spoken, intent_type, kind in SPOKEN[language]:
        result = recognize(spoken, intents)
        assert result is not None, f"{language}: nothing matches {spoken!r}"
        assert result.intent.name == intent_type, spoken
        if kind is not None:
            assert result.entities["kind"].value == kind, spoken


@pytest.mark.parametrize("language", sorted(PHRASES))
def test_every_kind_it_can_send_is_one_we_know(language: str) -> None:
    """Test that the list cannot send a word the handler has no answer for."""
    intents = _intents(language)

    sends = {
        value.value_out
        for value in intents.slot_lists["kind"].values  # type: ignore[attr-defined]
    }

    # Named rather than counted, so this cannot pass by finding nothing: the
    # list lives at the top of the file rather than under the intent, and
    # reading the wrong one of those is a test that always agrees with you.
    assert sends == set(TRAFFIC_KINDS)
