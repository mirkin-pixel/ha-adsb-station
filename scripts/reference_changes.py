"""Say what a regeneration of the reference tables changed, for a pull request.

Compares each table as committed with the one in the working tree, after
`scripts/build_reference.py` has run, and prints a Markdown summary. Prints
nothing when nothing changed.

    python scripts/reference_changes.py
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
TABLES = {
    "airlines.json": ("airlines", "Airlines"),
    "aircraft_models.json": ("models", "Aircraft types"),
    "code_blocks.json": ("blocks", "Address blocks"),
    "airports.json": ("airports", "Airports"),
}


def _committed(path: Path) -> dict[str, object]:
    relative = path.relative_to(ROOT).as_posix()
    shown = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return json.loads(shown.stdout) if shown.returncode == 0 else {}


def main() -> None:
    """Print a line per table that changed."""
    lines = []
    for name, (key, label) in TABLES.items():
        path = ROOT / "custom_components" / "adsb_station" / name
        before = _committed(path).get(key) or {}
        after = json.loads(path.read_text("utf-8")).get(key) or {}
        assert isinstance(before, dict)
        assert isinstance(after, dict)
        added = len(after.keys() - before.keys())
        removed = len(before.keys() - after.keys())
        changed = sum(1 for k in after.keys() & before.keys() if after[k] != before[k])
        if added or removed or changed:
            lines.append(
                f"| {label} | {len(after)} | +{added} | -{removed} | {changed} |"
            )
    if lines:
        print("| Table | Entries | Added | Removed | Changed |")
        print("|---|---|---|---|---|")
        print("\n".join(lines))


if __name__ == "__main__":
    main()
