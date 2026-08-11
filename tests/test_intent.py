"""Tests for what the station answers out loud."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import intent
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
import yaml

from custom_components.adsb_station.const import (
    CONF_LOOK_UP_ROUTES,
    DOMAIN,
    ROUTESET_URL,
)
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
    SERVICE_INSTALL_SENTENCES,
)
from custom_components.adsb_station.speech import PHRASES

from .conftest import MOCK_PIAWARE, PIAWARE_URL, set_responses, setup_integration
from .test_route import ROUTESET_ANSWER

# One overhead, one further out and one helicopter beyond the radius.
MOCK_SKY: dict[str, Any] = {
    "now": 1636387404.0,
    "messages": 10,
    "aircraft": [
        {
            "hex": "484123",
            "flight": "KLM123",
            "lat": 52.005,
            "lon": 5.0,
            "alt_baro": 30000,
            "gs": 450,
        },
        {
            "hex": "3c6444",
            "flight": "DLH99",
            "lat": 52.05,
            "lon": 5.0,
            "alt_baro": 12000,
        },
        {
            "hex": "480123",
            "flight": "PHTRA",
            "lat": 52.2,
            "lon": 5.0,
            "alt_baro": 1200,
            "category": "A7",
        },
    ],
}

EMPTY_SKY: dict[str, Any] = {"now": 1636387404.0, "messages": 10, "aircraft": []}


async def _ask(
    hass: HomeAssistant, intent_type: str, language: str = "en", **slots: Any
) -> str:
    """Ask one question and return what is said back."""
    response = await intent.async_handle(
        hass,
        DOMAIN,
        intent_type,
        {key: {"value": value} for key, value in slots.items()},
        language=language,
    )
    return str(response.speech["plain"]["speech"])


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    aircraft: dict[str, Any] | None = None,
) -> None:
    set_responses(aioclient_mock, aircraft=aircraft or MOCK_SKY)
    assert await setup_integration(hass, entry)


async def test_overhead(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the question the whole receiver was put on the roof for."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    # Overhead is measured through the air, so the Lufthansa at 12,000 feet
    # a little to the north beats the KLM at 30,000 feet almost straight up.
    # And Lufthansa is a name because the shipped table has one for DLH.
    assert await _ask(hass, INTENT_OVERHEAD) == (
        "Lufthansa 99 is overhead, 3,700 metres up."
    )
    assert await _ask(hass, INTENT_OVERHEAD, language="nl") == (
        "Lufthansa 99 vliegt over, 3.700 meter hoog."
    )


async def test_overhead_with_an_empty_sky(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the answer that comes up most often of all."""
    await _setup(hass, mock_config_entry, aioclient_mock, aircraft=EMPTY_SKY)

    assert await _ask(hass, INTENT_OVERHEAD) == "Nothing is overhead right now."
    assert await _ask(hass, INTENT_OVERHEAD, language="nl") == (
        "Er hangt nu niets boven je."
    )


async def test_count(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that both figures are said, since either alone reads as the sky."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    # Two are inside the ten kilometre radius; the helicopter is not
    assert await _ask(hass, INTENT_COUNT) == (
        "2 aircraft nearby, and the station is hearing 3 in all."
    )
    assert await _ask(hass, INTENT_COUNT, language="nl") == (
        "2 vliegtuigen dichtbij, en het station hoort er 3 in totaal."
    )


async def test_count_with_nothing_nearby(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an empty radius still says what the station is hearing."""
    await _setup(hass, mock_config_entry, aioclient_mock, aircraft=EMPTY_SKY)

    assert await _ask(hass, INTENT_COUNT) == (
        "Nothing is nearby, and the station is hearing no aircraft."
    )


async def test_closest(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the distance and the direction being said in words."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    assert await _ask(hass, INTENT_CLOSEST) == (
        "KLM 123 is 0.6 kilometres to the north, 9,100 metres up."
    )


async def test_closest_in_feet_and_miles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the answer follows the unit system rather than the language."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await _setup(hass, mock_config_entry, aioclient_mock)

    assert await _ask(hass, INTENT_CLOSEST) == (
        "KLM 123 is 0.3 miles to the north, 30,000 feet up."
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("helicopter", "P H T R A, 22.3 kilometres to the north."),
        ("drone", "I hear nothing like that."),
        # A word the sentences never send, which must not fall through to
        # the first kind in the table
        ("submarine", "I hear nothing like that."),
    ],
)
async def test_traffic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    kind: str,
    expected: str,
) -> None:
    """Test asking for one kind of traffic, including one that is not a kind."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    assert await _ask(hass, INTENT_TRAFFIC, kind=kind) == expected


async def test_traffic_counts_the_rest(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a list too long to follow by ear becomes a count."""
    await _setup(
        hass,
        mock_config_entry,
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {"hex": "480123", "lat": 52.02, "lon": 5.0, "category": "A7"},
                {"hex": "484124", "lat": 52.2, "lon": 5.0, "category": "A7"},
                {"hex": "484125", "lat": 52.3, "lon": 5.0, "category": "A7"},
            ],
        },
    )

    spoken = await _ask(hass, INTENT_TRAFFIC, kind="helicopter")
    assert spoken.startswith("4 8 0 1 2 3, 2.2 kilometres to the north.")
    assert spoken.endswith("And 2 more.")


async def test_route_when_lookups_are_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the setting being off is said rather than shrugged at."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    assert await _ask(hass, INTENT_ROUTE) == (
        "Route lookups are switched off, so I only know what is up there, "
        "not where it is going."
    )


async def test_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the route being spoken as cities rather than as codes."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_LOOK_UP_ROUTES: True}
    )
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {
                    "hex": "484123",
                    "flight": "KLM123",
                    "lat": 52.005,
                    "lon": 5.0,
                    "alt_baro": 3000,
                }
            ],
        },
    )
    aioclient_mock.post(ROUTESET_URL, json=ROUTESET_ANSWER)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await _ask(hass, INTENT_ROUTE) == (
        "KLM 123 is flying from Gothenburg to Amsterdam."
    )


async def test_without_a_receiver(
    hass: HomeAssistant,
    mock_piaware_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a setup that only feeds somewhere and hears nothing itself."""
    set_responses(aioclient_mock)
    aioclient_mock.get(PIAWARE_URL, json=MOCK_PIAWARE)
    assert await setup_integration(hass, mock_piaware_entry)

    assert await _ask(hass, INTENT_OVERHEAD) == "I cannot reach your ADS-B station."
    assert await _ask(hass, INTENT_OVERHEAD, language="nl") == (
        "Ik kan je ADS-B-station niet bereiken."
    )


async def test_the_sentences_match_their_intents() -> None:
    """Test that every shipped sentence file names intents that exist."""
    known = {
        INTENT_OVERHEAD,
        INTENT_COUNT,
        INTENT_CLOSEST,
        INTENT_TRAFFIC,
        INTENT_ROUTE,
    }
    directory = (
        Path(__file__).parent.parent
        / "custom_components"
        / "adsb_station"
        / SENTENCES_DIRECTORY
    )

    languages = sorted(item.name for item in directory.iterdir() if item.is_dir())
    assert languages == sorted(PHRASES)

    for language in languages:
        sentences = (directory / language / SENTENCES_FILE).read_text("utf-8")
        payload = yaml.safe_load(sentences)
        assert payload["language"] == language
        assert set(payload["intents"]) == known
        # Every value the traffic sentences can send has to be a kind the
        # handler knows, or the question is heard and answered with nothing
        for value in payload["lists"]["kind"]["values"]:
            assert value["out"] in TRAFFIC_KINDS


async def test_install_sentences(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    tmp_path: Path,
) -> None:
    """Test copying the sentences where Home Assistant reads them."""
    assert await setup_integration(hass, mock_config_entry)
    hass.config.config_dir = str(tmp_path)

    answer = await hass.services.async_call(
        DOMAIN, SERVICE_INSTALL_SENTENCES, {}, blocking=True, return_response=True
    )

    assert answer["languages"] == ["en", "nl"]
    for language in ("en", "nl"):
        written = tmp_path / "custom_sentences" / language / SENTENCES_FILE
        assert written.is_file()
        assert yaml.safe_load(written.read_text("utf-8"))["language"] == language

    # Calling it again overwrites rather than failing on what is there
    assert await hass.services.async_call(
        DOMAIN, SERVICE_INSTALL_SENTENCES, {}, blocking=True, return_response=True
    )


async def test_closest_with_nothing_placeable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the nearest aircraft question with nothing to measure."""
    await _setup(
        hass,
        mock_config_entry,
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            # Heard, but never placed, so there is no nearest
            "aircraft": [{"hex": "484125", "flight": "EZY22"}],
        },
    )

    assert await _ask(hass, INTENT_CLOSEST) == "Nothing is overhead right now."


async def test_route_for_a_flight_the_source_does_not_know(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test lookups being on but this particular flight being unknown."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_LOOK_UP_ROUTES: True}
    )
    set_responses(
        aioclient_mock,
        aircraft={
            "now": 1636387404.0,
            "messages": 10,
            "aircraft": [
                {"hex": "484123", "flight": "KLM123", "lat": 52.005, "lon": 5.0}
            ],
        },
    )
    # A callsign the database has never heard of comes back as a null
    aioclient_mock.post(ROUTESET_URL, json=[None])

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await _ask(hass, INTENT_ROUTE) == "I have no route for KLM 123."


async def test_sentences_that_cannot_be_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    tmp_path: Path,
) -> None:
    """Test that a configuration directory that cannot be written says so."""
    assert await setup_integration(hass, mock_config_entry)
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("", "utf-8")
    hass.config.config_dir = str(blocked)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_INSTALL_SENTENCES, {}, blocking=True, return_response=True
        )
