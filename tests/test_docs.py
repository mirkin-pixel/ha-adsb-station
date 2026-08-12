"""Tests that the two documentation trees stay in step.

`CONTRIBUTING.md` promises that English and Dutch are kept side by side and
that a change to one belongs in the other. Nothing enforced that, and the way
it goes wrong is quiet: a section added to one language six months from now,
and a reader of the other never learns the feature exists.

This checks the shape rather than the prose. Whether a paragraph says the
same thing in both languages is a matter for review; whether a page or a
heading exists in one and not the other is a matter of counting.
"""

from __future__ import annotations

from pathlib import Path
import re

DOCS = Path(__file__).parent.parent / "docs"
LANGUAGES = ("en", "nl")


def _headings(text: str) -> list[int]:
    """Return the level of every heading on a page, in order."""
    return [
        len(line) - len(line.lstrip("#"))
        for line in text.splitlines()
        if re.match(r"#{1,6} \S", line)
    ]


def test_both_languages_have_the_same_pages() -> None:
    """Test that neither tree has a page the other is missing."""
    pages = {
        language: {path.name for path in (DOCS / language).glob("*.md")}
        for language in LANGUAGES
    }

    assert pages["en"] == pages["nl"]
    # And that this is testing something at all.
    assert len(pages["en"]) > 5


def test_the_pages_have_the_same_shape() -> None:
    """Test that a section added to one language was added to the other."""
    for path in sorted((DOCS / "en").glob("*.md")):
        other = DOCS / "nl" / path.name
        english = _headings(path.read_text("utf-8"))
        dutch = _headings(other.read_text("utf-8"))
        assert english == dutch, (
            f"{path.name} has {len(english)} headings in English and "
            f"{len(dutch)} in Dutch"
        )


def test_every_page_starts_with_one_title() -> None:
    """Test that each page is a page rather than a fragment of one."""
    for language in LANGUAGES:
        for path in sorted((DOCS / language).glob("*.md")):
            levels = _headings(path.read_text("utf-8"))
            assert levels, f"{path} has no headings"
            assert levels[0] == 1, f"{path} does not open with a title"
            assert levels.count(1) == 1, f"{path} has more than one title"
