"""Tests for the questions an AI assistant can ask the station."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.adsb_station.const import DOMAIN
from custom_components.adsb_station.intent import QUESTIONS, SPEAK_ONLY

from .conftest import set_responses, setup_integration
from .test_intent import MOCK_SKY

# Home Assistant offers integration tools from 2026.10; before, it handed
# every intent over itself and never loads llm.py.
llm = pytest.importorskip("homeassistant.helpers.llm")
pytest.importorskip("homeassistant.components.llm")


@pytest.fixture(autouse=True)
async def components(hass: HomeAssistant) -> None:
    """Load what an assistant talks through."""
    for component in ("homeassistant", "intent", "llm"):
        assert await async_setup_component(hass, component, {})


def _context() -> Any:
    return llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


async def _tools(hass: HomeAssistant) -> dict[str, Any]:
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, _context())
    return {tool.name: tool for tool in api.tools if tool.integration == DOMAIN}


async def _call(hass: HomeAssistant, name: str, **args: Any) -> str:
    tool = (await _tools(hass))[f"{DOMAIN}__{name}"]
    result = await tool.async_call(
        hass, llm.ToolInput(tool_name=tool.name, tool_args=args), _context()
    )
    return str(result.data["speech"]["plain"]["speech"])


async def test_every_question_is_a_read_only_tool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that each question is offered, titled and marked as only reading."""
    set_responses(aioclient_mock, aircraft=MOCK_SKY)
    assert await setup_integration(hass, mock_config_entry)

    tools = await _tools(hass)

    assert set(tools) == {
        f"{DOMAIN}__{handler.intent_type}"
        for handler in (*QUESTIONS.values(), *SPEAK_ONLY.values())
    }
    for tool in tools.values():
        assert tool.title
        assert tool.annotations.read_only


async def test_no_tools_without_a_station(hass: HomeAssistant) -> None:
    """Test that nothing is offered before a receiver is set up."""
    assert await _tools(hass) == {}


async def test_a_tool_answers_as_assist_does(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that calling a tool gives the spoken sentence."""
    set_responses(aioclient_mock, aircraft=MOCK_SKY)
    assert await setup_integration(hass, mock_config_entry)

    assert (await _call(hass, "AdsbStationOverhead")).startswith("KLM 123")
    traffic = await _call(hass, "AdsbStationTraffic", kind="helicopter")
    assert traffic.startswith("P H T R A")


async def test_a_named_aircraft_as_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a callsign with a space, as an assistant writes it, is found."""
    set_responses(aioclient_mock, aircraft=MOCK_SKY)
    assert await setup_integration(hass, mock_config_entry)

    assert (await _call(hass, "AdsbStationAircraft", aircraft="KLM 123")).startswith(
        "KLM 123"
    )
    assert "DLH 99" not in await _call(hass, "AdsbStationAircraft", aircraft="DLH 98")
