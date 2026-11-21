"""The Assist sentences: copying them, and noticing a copy an update left behind.

A copy in `custom_sentences` does not follow the integration, so a question an
update adds is not understood until the files are copied again.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.json import JsonArrayType

from .const import DOMAIN, ISSUE_SENTENCES

SENTENCES_DIRECTORY: Final = "sentences"
CONFIG_SENTENCES_DIRECTORY: Final = "custom_sentences"
SENTENCES_FILE: Final = f"{DOMAIN}.yaml"
SHIPPED: Final = Path(__file__).parent / SENTENCES_DIRECTORY


def copy_sentences(source: Path, target: Path) -> JsonArrayType:
    """Copy the shipped sentences into the configuration. Blocking."""
    installed: JsonArrayType = []
    for language in sorted(item.name for item in source.iterdir() if item.is_dir()):
        origin = source / language / SENTENCES_FILE
        if not origin.is_file():
            continue
        destination = target / language
        destination.mkdir(parents=True, exist_ok=True)
        (destination / SENTENCES_FILE).write_text(origin.read_text("utf-8"), "utf-8")
        installed.append(language)
    return installed


def _outdated(source: Path, target: Path) -> tuple[str, bool]:
    """Return the shipped version, and whether a copy differs from it. Blocking.

    Only languages that were copied count: none copied is nothing to update.
    """
    shipped = hashlib.sha256()
    outdated = False
    for origin in sorted(source.glob(f"*/{SENTENCES_FILE}")):
        text = origin.read_text("utf-8")
        shipped.update(text.encode())
        copy = target / origin.parent.name / SENTENCES_FILE
        if copy.is_file() and copy.read_text("utf-8") != text:
            outdated = True
    return shipped.hexdigest()[:12], outdated


async def async_check_sentences(hass: HomeAssistant) -> None:
    """Raise a repair while a copy is older than what ships, and clear it after.

    One issue per shipped version, so one ignored is raised again by the next
    update that changes the sentences.
    """
    target = Path(hass.config.path(CONFIG_SENTENCES_DIRECTORY))
    version, outdated = await hass.async_add_executor_job(_outdated, SHIPPED, target)
    current = f"{ISSUE_SENTENCES}_{version}"
    for domain, issue_id in list(ir.async_get(hass).issues):
        stale = issue_id != current or not outdated
        if domain == DOMAIN and issue_id.startswith(ISSUE_SENTENCES) and stale:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    if outdated:
        ir.async_create_issue(
            hass,
            DOMAIN,
            current,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_SENTENCES,
        )


async def async_install_sentences(hass: HomeAssistant) -> JsonArrayType:
    """Copy the sentences and forget any issue about an old copy."""
    target = Path(hass.config.path(CONFIG_SENTENCES_DIRECTORY))
    installed = await hass.async_add_executor_job(copy_sentences, SHIPPED, target)
    await async_check_sentences(hass)
    return installed
