"""Tests that the two documentation trees stay in step.

`CONTRIBUTING.md` promises that English and Dutch are kept side by side and
that a change to one belongs in the other. Nothing enforced that, and the way
it goes wrong is quiet: a section added to one language six months from now,
and a reader of the other never learns the feature exists.

The front page and the index of each language are held to listing every page.

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


def test_each_index_points_at_every_page() -> None:
    """Test that the front page and each language's index list every page.

    The front page is English; each docs folder opens on a README of its own,
    which is where the link to the Dutch documentation leads.
    """
    indexes = {
        "en": [DOCS.parent / "README.md", DOCS / "en" / "README.md"],
        "nl": [DOCS / "nl" / "README.md"],
    }
    for language, files in indexes.items():
        pages = {path.name for path in (DOCS / language).glob("*.md")} - {"README.md"}
        for index in files:
            linked = set(
                re.findall(
                    rf"(?:docs/{language}/)?([\w-]+\.md)\)", index.read_text("utf-8")
                )
            ) - {"README.md", "CONTRIBUTING.md"}
            assert linked == pages, (
                f"{index} misses {sorted(pages - linked)} "
                f"and links {sorted(linked - pages)}, which do not exist"
            )


_NUMBERS = {
    word: value
    for value, words in enumerate(
        [
            ("zero", "nul"),
            ("one", "een"),
            ("two", "twee"),
            ("three", "drie"),
            ("four", "vier"),
            ("five", "vijf"),
            ("six", "zes"),
            ("seven", "zeven"),
            ("eight", "acht"),
            ("nine", "negen"),
            ("ten", "tien"),
            ("eleven", "elf"),
            ("twelve", "twaalf"),
            ("thirteen", "dertien"),
            ("fourteen", "veertien"),
            ("fifteen", "vijftien"),
            ("sixteen", "zestien"),
            ("seventeen", "zeventien"),
            ("eighteen", "achttien"),
            ("nineteen", "negentien"),
            ("twenty", "twintig"),
        ]
    )
    for word in words
}


def _counted(paths: list[Path], patterns: list[str]) -> list[tuple[str, int]]:
    """Return every number these phrases give, written out, and where."""
    found = []
    for path in paths:
        text = path.read_text("utf-8")
        for pattern in patterns:
            for word in re.findall(pattern, text, flags=re.IGNORECASE):
                found.append((f"{path.name}: {word}", _NUMBERS[word.lower()]))
    return found


def test_the_counts_in_the_docs_follow_the_code() -> None:
    """Test that a number the docs spell out is the number there is.

    "Six questions" stayed on the front page for months after there were ten.
    """
    from custom_components.adsb_station.intent import QUESTIONS

    root = DOCS.parent
    questions = _counted(
        [
            root / "README.md",
            *(DOCS / language / "README.md" for language in LANGUAGES),
            *(DOCS / language / "voice.md" for language in LANGUAGES),
        ],
        [
            r"(\w+) questions for Assist",
            r"(\w+) vragen voor Assist",
            r"Assist can answer (\w+)",
            r"Assist beantwoordt er (\w+)",
            r"the same (\w+) answers",
            r"dezelfde (\w+) antwoorden",
        ],
    )
    pages = _counted(
        [root / "CONTRIBUTING.md", root / ".github/ISSUE_TEMPLATE/new_language.yml"],
        [r"(\w+) pages per language"],
    )

    # Found at all, or this would pass on docs that no longer say it.
    assert len(questions) >= 6
    assert len(pages) >= 2
    for where, count in questions:
        assert count == len(QUESTIONS), where
    page_count = len(list((DOCS / "en").glob("*.md")))
    for where, count in pages:
        assert count == page_count, where
