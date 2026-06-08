#!/usr/bin/env python3
"""Apply [[ingredient]] highlights to all recipes/*.md (idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))

from recipe_format import apply_ingredient_highlights  # noqa: E402

RECIPES = REPO / "recipes"


def main() -> int:
    updated: list[str] = []
    for path in sorted(RECIPES.glob("*.md")):
        if path.name.startswith("_"):
            continue
        before = path.read_text(encoding="utf-8")
        after = apply_ingredient_highlights(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            updated.append(path.name)
    print(f"Updated {len(updated)} recipe(s).")
    for name in updated:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())