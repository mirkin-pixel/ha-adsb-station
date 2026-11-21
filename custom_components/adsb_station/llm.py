"""The spoken questions as read-only tools for an AI assistant.

Home Assistant 2026.10 stopped handing every intent to the Assist API; an
integration now offers its own. Older versions never load this file, as they
still hand the intents over themselves.
"""

from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    Tool,
    ToolAnnotations,
)

from .const import DOMAIN
from .coordinator import receivers
from .intent import QUESTIONS, SPEAK_ONLY

TITLES = {
    "overhead": "What is overhead",
    "count": "How many aircraft",
    "closest": "Closest aircraft",
    "traffic": "Military, helicopters or drones",
    "route": "Route of the aircraft overhead",
    "last_passage": "Last aircraft overhead",
    "highest": "Highest aircraft",
    "fastest": "Fastest aircraft",
    "furthest": "Furthest aircraft",
    "emergency": "Aircraft in distress",
    "aircraft": "One named aircraft",
}

# They only read the last poll of a receiver on the local network.
_READ_ONLY = ToolAnnotations(read_only=True, open_world=False)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the questions as tools, once there is a station to ask."""
    if api_id != LLM_API_ASSIST or not receivers(hass):
        return None
    tools: list[Tool] = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title=TITLES[question],
            integration=DOMAIN,
            annotations=_READ_ONLY,
        )
        for question, handler in {**QUESTIONS, **SPEAK_ONLY}.items()
    ]
    return LLMTools(tools=tools)
