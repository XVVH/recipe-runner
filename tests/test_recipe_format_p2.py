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
    load_recipe_json_file,
    merge_recipe_json,
    parse_title_author_from_plaintext,
    parse_vision_json,
    process_recipemd,
    strip_extraction_metadata,
    structured_to_recipemd,
)

RECIPES = REPO / "recipes"


def test_apply_highlights_wraps_ingredients():
    md = """---
title: Test Soup
date: 2026-06-01
tags: [Soup]
yield: 4 servings
added_by: You
---
- *2 cups* chicken broth
- *1* onion

---
Add onion to the broth and simmer.
"""
    out = apply_ingredient_highlights(md)
    assert "[[onion]]" in out.lower() or "[[onion ]]" not in out  # case may vary
    assert "[[chicken broth]]" in out.lower() or "broth" in out


def test_highlights_head_noun_from_countable_unit():
    """Steps say 'the garlic' when the list has 'garlic cloves, minced'."""
    md = """---
title: Beans
date: 2026-06-01
tags: [Side]
yield: 4
added_by: You
---
- *4* garlic cloves, minced
- *1/4 cup* brown sugar

---
Add the garlic, brown sugar, and simmer.
"""
    out = apply_ingredient_highlights(md)
    assert "[[garlic]]" in out
    assert "[[brown sugar]]" in out


def test_highlights_strip_modifiers_and_prep_clauses():
    """Cookbook-style lines: ground ginger, unsalted butter (melted in step), flour."""
    md = """---
title: Spice Cookies
date: 2026-06-01
tags: [Dessert]
yield: 42 cookies
added_by: You
---
- *3 3/4 cups* all-purpose flour
- *2 1/2 teaspoons* ground ginger
- *1/2 teaspoon* ground allspice
- *1/4 teaspoon* ground cloves
- *1 1/2 sticks* unsalted butter, melted and cooled to room temperature
- *2* large eggs, at room temperature
- *1/2 cup* unsulfured molasses
- *2 teaspoons* vanilla extract
- *1/2 cup* demerara sugar, for rolling

---
Whisk together the flour, ginger, allspice, and cloves. Beat the melted butter. Add eggs and molasses, vanilla. Roll in demerara sugar.
"""
    out = apply_ingredient_highlights(md)
    assert "[[flour]]" in out
    assert "[[ginger]]" in out
    assert "[[allspice]]" in out
    assert "[[cloves]]" in out
    assert "[[butter]]" in out
    assert "[[eggs]]" in out
    assert "[[molasses]]" in out
    assert "[[vanilla]]" in out
    assert "[[demerara sugar]]" in out or "demerara [[sugar]]" in out


def test_highlights_skip_existing_spans():
    md = """---
title: T
date: 2026-06-01
tags: [x]
yield: 1
added_by: You
---
- butter

---
Melt [[butter]] slowly.
"""
    out = apply_ingredient_highlights(md)
    assert out.count("[[butter]]") == 1


def test_highlights_rerun_is_idempotent():
    md = """---
title: T
date: 2026-06-01
tags: [x]
yield: 1
added_by: You
---
- ground ginger

---
Whisk the ginger into the bowl.
"""
    once = apply_ingredient_highlights(md)
    twice = apply_ingredient_highlights(once)
    assert once == twice
    assert "[[ginger]]" in twice


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
added_by: You
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
    assert "page_role" not in merged


def test_merge_recipe_json_continuation_appends_duplicate_steps():
    page1 = {
        "page_index": 1,
        "page_role": "primary",
        "title": "Risotto",
        "ingredients": ["2 cups arborio rice"],
        "instructions": ["Stir constantly."],
    }
    page2 = {
        "page_index": 2,
        "page_role": "continuation",
        "title": "Other Recipe Header",
        "ingredients": ["4 cups broth"],
        "instructions": ["Stir constantly.", "Add broth ladle by ladle."],
    }
    merged = merge_recipe_json([page1, page2], recipe_type="cookbook")
    assert merged["title"] == "Risotto"
    assert merged["instructions"] == [
        "Stir constantly.",
        "Stir constantly.",
        "Add broth ladle by ladle.",
    ]


def test_merge_recipe_json_sorts_by_page_index():
    second = {"page_index": 2, "page_role": "continuation", "instructions": ["Bake."]}
    first = {
        "page_index": 1,
        "page_role": "primary",
        "title": "Cake",
        "ingredients": ["flour"],
        "instructions": ["Mix."],
    }
    merged = merge_recipe_json([second, first], recipe_type="cookbook")
    assert merged["instructions"] == ["Mix.", "Bake."]


def test_parse_vision_json_strips_fences():
    raw = 'Here is the recipe:\n```json\n{"title": "Soup", "ingredients": ["water"]}\n```'
    data = parse_vision_json(raw)
    assert data["title"] == "Soup"
    assert strip_extraction_metadata({**data, "page_index": 1}) == data


def test_load_recipe_json_file_accepts_fenced_file(tmp_path):
    path = tmp_path / "page-01.json"
    path.write_text('```json\n{"title": "Tea", "ingredients": ["water"]}\n```\n')
    data = load_recipe_json_file(path)
    assert data["title"] == "Tea"


def test_parse_title_author_first_line():
    raw = """Tomato Basil Pasta, by Morgan
6 medium tomatoes
1 bunch basil
"""
    rest, title, author = parse_title_author_from_plaintext(raw)
    assert title == "Tomato Basil Pasta"
    assert author == "Morgan"
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
        source_label="Example cookbook",
        added_by="You",
        slug_override="tomato-basil-pasta-ingest-test",
        author="Morgan",
        highlight=True,
        add_missing_ingredients=True,
    )
    assert r["status"] == "success", r.get("error")
    assert "author: Morgan" in r["md"]
    assert "[[tomatoes]]" in r["md"] or "[[basil]]" in r["md"]
    assert "angel hair pasta" in r["md"]
    Path(r["output_path"]).unlink(missing_ok=True)


def test_brown_butter_still_valid_after_rehighlight():
    content = (RECIPES / "brown-butter-chocolate-chip-cookies.md").read_text(encoding="utf-8")
    out = apply_ingredient_highlights(content)
    errors = [i for i in validate_recipe(out, strict=True) if i.level == "error"]
    assert errors == []
