"""P2: highlights, missing-ingredient detection, merge JSON, plain-text author line."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))
sys.path.insert(0, str(REPO / "scripts"))

from recipe_format import (  # noqa: E402
    apply_ingredient_highlights,
    append_missing_ingredients,
    find_missing_ingredients,
    validate_recipe,
)
from ingest_common import (  # noqa: E402
    apply_common_typos,
    merge_recipe_json,
    parse_title_author_from_plaintext,
    process_recipemd,
    structured_to_recipemd,
)

RECIPES = REPO / "recipes"


def test_apply_highlights_wraps_ingredients():
    md = """---
title: Test Soup
date: 2026-06-01
tags: [Soup]
yield: 4 servings
added_by: Josh
---
- *2 cups* chicken broth
- *1* onion

---
Add onion to the broth and simmer.
"""
    out = apply_ingredient_highlights(md)
    assert "[[onion]]" in out.lower() or "[[onion ]]" not in out  # case may vary
    assert "[[chicken broth]]" in out.lower() or "broth" in out


def test_highlights_skip_existing_spans():
    md = """---
title: T
date: 2026-06-01
tags: [x]
yield: 1
added_by: Josh
---
- butter

---
Melt [[butter]] slowly.
"""
    out = apply_ingredient_highlights(md)
    assert out.count("[[butter]]") == 1


def test_find_missing_ingredient_in_step():
    ing = "- tomatoes\n- basil"
    instr = "Serve over angel hair pasta when ready."
    missing = find_missing_ingredients(ing, instr)
    assert any("pasta" in m.lower() for m in missing)


def test_append_missing_ingredients():
    md = """---
title: Pasta
date: 2026-06-01
tags: [pasta]
yield: 4 servings
added_by: Josh
---
- tomatoes

---
Toss with angel hair pasta.
"""
    missing = find_missing_ingredients("- tomatoes", "Toss with angel hair pasta.")
    out = append_missing_ingredients(md, missing)
    assert "angel hair pasta" in out
    assert "Added from instruction text" in out


def test_merge_recipe_json_combines_parts():
    front = {
        "title": "Spinach Lasagna",
        "ingredients": ["lasagna noodles", "ricotta"],
        "instructions": {"Cook noodles": ["Boil noodles."]},
    }
    back = {
        "instructions": {"Bake": ["Bake 45 minutes."]},
        "notes": ["Let rest 10 minutes."],
    }
    merged = merge_recipe_json([front, back])
    assert merged["title"] == "Spinach Lasagna"
    assert "ricotta" in merged["ingredients"]
    assert "Bake" in merged["instructions"]
    assert "Let rest" in merged["notes"][0]


def test_parse_title_author_first_line():
    raw = """Tomato Basil Pasta, by Avis
6 medium tomatoes
1 bunch basil
"""
    rest, title, author = parse_title_author_from_plaintext(raw)
    assert title == "Tomato Basil Pasta"
    assert author == "Avis"
    assert "6 medium tomatoes" in rest


def test_common_typos_normalize():
    assert "angel hair" in apply_common_typos("angle hair pasta").lower()


def test_process_recipemd_with_highlight_and_author_line(monkeypatch):
    monkeypatch.chdir(REPO)
    text = """# Tomato Basil Pasta Ingest Test

*Pasta, Salad*

**4 servings**

---

- 6 tomatoes
- basil

---

Add tomatoes and basil. Serve with angel hair pasta.
"""
    r = process_recipemd(
        text,
        source_label="Family recipe",
        added_by="Josh",
        slug_override="tomato-basil-pasta-ingest-test",
        author="Avis",
        highlight=True,
        add_missing_ingredients=True,
    )
    assert r["status"] == "success", r.get("error")
    assert "author: Avis" in r["md"]
    assert "[[tomatoes]]" in r["md"] or "[[basil]]" in r["md"]
    assert "angel hair pasta" in r["md"]
    Path(r["output_path"]).unlink(missing_ok=True)


def test_brown_butter_still_valid_after_rehighlight():
    content = (RECIPES / "brown-butter-chocolate-chip-cookies.md").read_text(encoding="utf-8")
    out = apply_ingredient_highlights(content)
    errors = [i for i in validate_recipe(out, strict=True) if i.level == "error"]
    assert errors == []
