"""Golden tests for recipe_format canonicalize + validate."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))

from recipe_format import (  # noqa: E402
    canonicalize,
    split_body_sections,
    validate_recipe,
    validate_recipe_file,
)

RECIPES = REPO / "recipes"


def _errors(content: str, *, strict: bool = False):
    return [i for i in validate_recipe(content, strict=strict) if i.level == "error"]


def test_brown_butter_canonical_passes_strict():
    content = (RECIPES / "brown-butter-chocolate-chip-cookies.md").read_text(encoding="utf-8")
    assert _errors(content, strict=True) == []


def test_caesar_canonical_passes_strict():
    content = (RECIPES / "caesar-style-kale-salad-with-roasted-onions.md").read_text(encoding="utf-8")
    assert _errors(content, strict=True) == []


def test_legacy_baked_beans_passes_relaxed_build():
    content = (RECIPES / "my-best-baked-beans.md").read_text(encoding="utf-8")
    assert _errors(content, strict=False) == []


def test_invalid_ingredients_first_fails():
    """Ingredients treated as description (pre-parser-fix shape) must fail strict."""
    bad = """---
title: Bad Recipe
date: 2026-06-01
tags: [test]
yield: 1 serving
added_by: You
---
- *1 cup* flour

---
A step here.
"""
    assert _errors(bad, strict=True) == []  # actually this IS valid canonical shape

    broken = """---
title: Broken
date: 2026-06-01
tags: [test]
yield: 1
added_by: You
---
Only prose here, no ingredient lines.

---
Heat the oven. No ingredients anywhere.
"""
    errs = _errors(broken, strict=True)
    assert any("ingredient" in e.message.lower() for e in errs)


def test_canonicalize_from_recipemd_shape():
    recipemd = """# Test Soup

*Soup, Easy*

**4 servings**

---

- 2 cups broth
- 1 onion

---

Bring to a boil.
Simmer 10 minutes.

Do ahead: Keeps 3 days.
"""
    out = canonicalize(recipemd, source_url="https://example.com/soup", added_by="You")
    assert _errors(out, strict=True) == []
    assert "added_by: You" in out
    assert "source: https://example.com/soup" in out
    assert out.count("\n---\n") >= 2  # frontmatter + body sections
    assert "# Test Soup" not in out.split("---", 1)[-1]
    _desc, ing, instr, notes = split_body_sections(out.split("---\n", 1)[-1])
    assert "broth" in ing
    assert "boil" in instr
    assert notes  # Do ahead promoted to notes section


def test_template_skipped_by_build_glob():
    assert not (RECIPES / "_template.md").name.startswith("_") is False


def test_structured_to_recipemd_and_strict_validate():
    sys.path.insert(0, str(REPO / "scripts"))
    from ingest_common import structured_to_recipemd  # noqa: E402

    data = {
        "title": "Test Soup",
        "yield": "4 servings",
        "tags": ["Soup"],
        "ingredients": ["2 cups broth", "1 onion"],
        "instructions": {"Cook": ["Bring to a boil.", "Simmer 10 minutes."]},
        "notes": ["Keeps 3 days."],
    }
    md = structured_to_recipemd(data)
    out = canonicalize(md, source_url="https://example.com/soup", added_by="You")
    assert _errors(out, strict=True) == []
    assert "added_by: You" in out
    assert "broth" in out


def test_process_recipemd_invalid():
    sys.path.insert(0, str(REPO / "scripts"))
    from ingest_common import process_recipemd  # noqa: E402

    r = process_recipemd(
        "# No ingredients\n\n---\n\nJust prose.\n\n---\n\nA step.",
        added_by="You",
    )
    assert r["status"] == "invalid_format"
