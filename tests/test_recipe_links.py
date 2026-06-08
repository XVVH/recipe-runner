import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))

from recipe_links import linkify_brackets_html, recipe_link_index


def slugify(s: str) -> str:
    import re

    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")


def test_bracket_links_to_other_recipe():
    recipes = [
        {"slug": "sauce-base", "title": "Sauce Base"},
        {"slug": "main-dish", "title": "Main Dish"},
    ]
    index = recipe_link_index(recipes, slugify)
    out = linkify_brackets_html(
        "Add [[Sauce Base]] to the pan.",
        index,
        "main-dish",
        slugify,
    )
    assert 'href="/sauce-base/"' in out
    assert "recipe-ref" in out


def test_bracket_same_recipe_stays_highlight():
    recipes = [{"slug": "sauce-base", "title": "Sauce Base"}]
    index = recipe_link_index(recipes, slugify)
    out = linkify_brackets_html("Use [[Sauce Base]] again.", index, "sauce-base", slugify)
    assert "recipe-ref" not in out
    assert "ing-ref" in out