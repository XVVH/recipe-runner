"""P1 ingest output shape: omit nulls, favorite unquoted, schema metadata, yield guards."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "site"))

from recipe_format import (  # noqa: E402
    canonicalize,
    metadata_from_schema,
    validate_recipe,
    yield_looks_suspicious,
)


def _errors(content: str, *, strict: bool = False):
    return [i for i in validate_recipe(content, strict=strict) if i.level == "error"]


def test_canonicalize_omits_null_author_and_uses_favorite_no():
    recipemd = """# Simple Toast

**1 serving**

---

- 1 slice bread

---

Toast the bread.
"""
    out = canonicalize(recipemd, source_url="https://example.com/t", added_by="You")
    assert "author: null" not in out
    assert "recommended_by: null" not in out
    assert "favorite: no\n" in out or out.endswith("favorite: no\n---")
    assert "favorite: 'no'" not in out
    assert "description:" not in out.split("---", 1)[0]


def test_canonicalize_applies_schema_metadata():
    recipemd = """# Noodle Bowl

---

- 2 cups noodles
- 1 cup peanut butter
- 2 tbsp soy sauce
- 1 tbsp vinegar
- 2 cloves garlic

---

Mix and serve.
"""
    schema = {
        "author": "Qi Ai",
        "tags": ["Noodles", "Chinese"],
        "yield": "1 serving",
    }
    out = canonicalize(
        recipemd,
        source_url="https://seriouseats.com/test",
        added_by="You",
        schema_metadata=schema,
    )
    assert "author: Qi Ai" in out
    assert "Noodles" in out
    assert "yield: 1 serving" not in out  # suspicious 1 serving + 5 ingredients


def test_metadata_from_schema_extracts_author_and_tags():
    recipe = {
        "@type": "Recipe",
        "name": "Test",
        "author": {"@type": "Person", "name": "Qi Ai"},
        "recipeCategory": ["Main", "Noodles"],
        "recipeCuisine": "Chinese",
        "keywords": "quick, easy",
        "recipeYield": "4 servings",
        "recipeIngredient": ["a", "b", "c"],
    }
    meta = metadata_from_schema(recipe, ingredient_count=3)
    assert meta["author"] == "Qi Ai"
    assert "Noodles" in meta["tags"]
    assert meta["yield"] == "4 servings"


def test_yield_looks_suspicious():
    assert yield_looks_suspicious("1 serving", ingredient_count=6)
    assert not yield_looks_suspicious("4 servings", ingredient_count=6)
    assert not yield_looks_suspicious("1 serving", ingredient_count=2)


def test_keep_description_flag():
    recipemd = """# Soup

*Soup*

**4 servings**

A tasty soup for winter.

---

- 1 cup broth

---

Simmer.
"""
    out = canonicalize(
        recipemd,
        source_url="https://example.com/s",
        added_by="You",
        keep_description=True,
    )
    fm_block = out.split("\n---\n", 1)[0]
    assert "description:" in fm_block
    assert "tasty soup" in fm_block
    assert _errors(out, strict=True) == []


def test_author_cli_override_wins():
    recipemd = """# Soup

---

- 1 cup broth

---

Simmer.
"""
    out = canonicalize(
        recipemd,
        added_by="You",
        author="Morgan",
        schema_metadata={"author": "Someone Else"},
    )
    assert "author: Morgan" in out
    assert "Someone Else" not in out
