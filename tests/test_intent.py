"""Tests for what the station answers out loud."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
import voluptuous as vol
import yaml

from custom_components.adsb_station.const import (
    CONF_LOOK_UP_ROUTES,
    DOMAIN,
    ROUTESET_URL,
)
from custom_components.adsb_station.intent import (
    INTENT_CLOSEST,
    INTENT_COUNT,
    INTENT_EMERGENCY,
    INTENT_HIGHEST,
    INTENT_OVERHEAD,
    INTENT_ROUTE,
    INTENT_TRAFFIC,
    QUESTIONS,
    TRAFFIC_KINDS,
)
from custom_components.adsb_station.services import (
    SENTENCES_DIRECTORY,
    SENTENCES_FILE,
    SERVICE_INSTALL_SENTENCES,
    SERVICE_SPEAK,
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


@pytest.fixture(autouse=True)
async def intent_component(hass: HomeAssistant) -> None:
    """Load the component that registers the questions, as Assist does."""
    assert await async_setup_component(hass, "intent", {})


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

    # Overhead is the circle on the map, so the KLM at 30,000 feet almost
    # straight up beats the Lufthansa at 12,000 feet a little to the north.
    assert await _ask(hass, INTENT_OVERHEAD) == (
        "KLM 123 is overhead, 9,100 metres up."
    )
    assert await _ask(hass, INTENT_OVERHEAD, language="nl") == (
        "KLM 123 vliegt over, 9.100 meter hoog."
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
    # Every question Assist is taught, and nothing else.
    known = {handler.intent_type for handler in QUESTIONS.values()}
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


async def test_install_sentences_is_for_administrators(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AiohttpClientMocker,
    tmp_path: Path,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that only an administrator may write into the configuration."""
    assert await setup_integration(hass, mock_config_entry)
    hass.config.config_dir = str(tmp_path)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL_SENTENCES,
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
            return_response=True,
        )
    assert not (tmp_path / "custom_sentences").exists()

    # An administrator still gets the answer back, not only the files
    answer = await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL_SENTENCES,
        {},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
        return_response=True,
    )
    assert answer["languages"] == ["en", "nl"]
    assert (tmp_path / "custom_sentences" / "en" / SENTENCES_FILE).is_file()


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


async def test_speak_without_any_sentence_file(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the answers being reachable through an action instead."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    spoken = await hass.services.async_call(
        DOMAIN,
        SERVICE_SPEAK,
        {"question": "overhead"},
        blocking=True,
        return_response=True,
    )
    # The same sentence the voice question gives, word for word
    assert spoken == {"speech": "KLM 123 is overhead, 9,100 metres up."}


async def test_speak_takes_a_kind_and_a_language(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the traffic question and an answer in the other language."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    spoken = await hass.services.async_call(
        DOMAIN,
        SERVICE_SPEAK,
        {"question": "traffic", "kind": "helicopter", "language": "nl"},
        blocking=True,
        return_response=True,
    )
    assert spoken == {"speech": "P H T R A, 22,3 kilometer naar het noorden."}


async def _speak(hass: HomeAssistant, **data: Any) -> str:
    spoken = await hass.services.async_call(
        DOMAIN, SERVICE_SPEAK, data, blocking=True, return_response=True
    )
    assert spoken is not None
    return str(spoken["speech"])


async def test_speak_about_one_named_aircraft(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a finished sentence about an aircraft named by an automation."""
    sky = {
        "now": 1636387404.0,
        "messages": 10,
        "aircraft": [
            {
                "hex": "484123",
                "flight": "KLM123",
                "r": "PH-BXA",
                "t": "B738",
                "lat": 52.2,
                "lon": 5.0,
                "alt_baro": 12000,
                "baro_rate": 1600,
            },
            # Heard over Mode S alone: no position to point at.
            {"hex": "3c6444", "flight": "DLH99", "alt_baro": 30000},
        ],
    }
    await _setup(hass, mock_config_entry, aioclient_mock, sky)

    # By callsign, hex code or registration alike, in either case.
    for named in ("KLM123", "484123", "ph-bxa"):
        assert await _speak(hass, question="aircraft", aircraft=named) == (
            "KLM 123, a Boeing 737-800, is 22.3 kilometres to the north, "
            "3,700 metres up and climbing."
        )
    assert await _speak(
        hass, question="aircraft", aircraft="KLM123", language="nl"
    ) == (
        "KLM 123, een Boeing 737-800, zit 22,3 kilometer naar het noorden, "
        "3.700 meter hoog en stijgend."
    )
    # Heard, but not where.
    assert await _speak(hass, question="aircraft", aircraft="DLH99") == (
        "Lufthansa 99 is heard without a position, 9,100 metres up."
    )
    # Not heard at all, which is an answer rather than an error.
    assert await _speak(hass, question="aircraft", aircraft="ryr1") == (
        "I do not hear RYR1 right now."
    )


async def test_speak_about_a_named_aircraft_with_its_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the route added as a sentence of its own when there is one."""
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

    spoken = await _speak(hass, question="aircraft", aircraft="KLM123")
    assert spoken.endswith(" It is flying from Gothenburg to Amsterdam.")


async def test_a_named_aircraft_is_no_assist_question(hass: HomeAssistant) -> None:
    """Test that the named question stays out of what Assist is taught."""
    assert "aircraft" not in QUESTIONS


async def test_highest_fastest_furthest(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the figures every poll has anyway, asked out loud."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    north = ", 0.6 kilometres to the north."
    noorden = ", 0,6 kilometer naar het noorden."
    expected = [
        ("highest", "en", "KLM 123 is highest, 9,100 metres up" + north),
        ("highest", "nl", "KLM 123 vliegt het hoogst, 9.100 meter hoog" + noorden),
        ("fastest", "en", "KLM 123 is fastest, at 830 kilometres an hour" + north),
        ("fastest", "nl", "KLM 123 is het snelst, 830 kilometer per uur" + noorden),
        # How far the station hears right now.
        (
            "furthest",
            "en",
            "P H T R A is furthest away, 22.3 kilometres to the north, 400 metres up.",
        ),
        (
            "furthest",
            "nl",
            "P H T R A is het verst weg, 22,3 kilometer naar het noorden, "
            "400 meter hoog.",
        ),
    ]
    for question, language, sentence in expected:
        assert await _speak(hass, question=question, language=language) == sentence
    # And through Assist, with the same words.
    assert await _ask(hass, INTENT_HIGHEST) == expected[0][2]


async def test_emergency(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an aircraft in distress named, and the quiet answer without one."""
    await _setup(hass, mock_config_entry, aioclient_mock)
    assert await _speak(hass, question="emergency") == (
        "No aircraft is reporting an emergency."
    )
    assert await _ask(hass, INTENT_EMERGENCY, language="nl") == (
        "Geen enkel toestel meldt een noodgeval."
    )


async def test_emergency_squawked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the one squawking 7700 named, with what it reports."""
    sky = {
        **MOCK_SKY,
        "aircraft": [
            {**MOCK_SKY["aircraft"][1], "squawk": "7700"},
            {**MOCK_SKY["aircraft"][2], "squawk": "7600"},
        ],
    }
    await _setup(hass, mock_config_entry, aioclient_mock, sky)
    # The nearest named, the others counted.
    assert await _speak(hass, question="emergency") == (
        "Lufthansa 99 reports an emergency, 5.6 kilometres to the north, "
        "3,700 metres up. And 1 more."
    )
    assert await _speak(hass, question="emergency", language="nl") == (
        "Lufthansa 99 meldt een noodgeval, 5,6 kilometer naar het noorden, "
        "3.700 meter hoog. En nog 1."
    )


async def test_speak_refuses_a_question_it_does_not_have(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a made-up question fails rather than answering something."""
    await _setup(hass, mock_config_entry, aioclient_mock)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SPEAK,
            {"question": "how is the weather"},
            blocking=True,
            return_response=True,
        )


async def test_the_intent_component_registers_every_question_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the questions are registered without an error or a second time.

    Home Assistant awaits `async_setup_intents`; a plain function made it log
    "object can't be awaited" on every start.
    """
    await _setup(hass, mock_config_entry, aioclient_mock)

    registered = intent.async_get(hass)
    assert {handler.intent_type for handler in registered} >= {
        handler.intent_type for handler in QUESTIONS.values()
    }
    assert not [record for record in caplog.records if record.levelname == "ERROR"]
    assert "overwritten" not in caplog.text
