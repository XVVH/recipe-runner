# Ingredient highlights in instruction steps

Site behavior: `site/recipe_format.py` → `apply_ingredient_highlights()` wraps **same-recipe** ingredient phrases in steps as `[[...]]` (rendered `ing-ref`). **Other recipes:** `[[Other Title]]` → `recipe-ref` links via `site/recipe_links.py` at build (`ssg-recipe-links.md`). Ingest runs highlights after `canonicalize()`; manual edits may need a re-run.

## Re-run highlights (one file or whole collection)

**All recipes** (idempotent):

```bash
cd ~/dev/recipe-runner
.venv/bin/python scripts/highlight_all_recipes.py
```

**Single file:**

```bash
cd ~/dev/recipe-runner
PYTHONPATH=site .venv/bin/python -c "
from pathlib import Path
from recipe_format import apply_ingredient_highlights
p = Path('recipes/your-slug.md')
p.write_text(apply_ingredient_highlights(p.read_text()), encoding='utf-8')
"
```

Legacy imports often had no `[[...]]` until this pass. **Pitfall:** prep in the ingredient line (`garlic, thinly sliced`) can yield bogus `[[sliced]]` in steps — shorten the ingredient name and re-run.

Then `site/build.py` before deploy.

## Shorter noun in steps than in the ingredient line

| Issue | What happened | Fix |
|--------|----------------|-----|
| Comma-cut modifiers | Line `chicken thighs, bone-in, skin-on` stayed one long phrase; head-noun logic never saw a clean `chicken thighs` pair | Use parentheses: `chicken thighs (bone-in, skin-on)` so `_food_text_cleanup()` keeps `chicken thighs` |
| Missing countable unit | `_maybe_head_noun()` only emits the first word when the **second** word is in `_COUNTABLE_UNIT_WORDS` (cloves, ribs, thighs, pieces, …) | Add the unit word to `_COUNTABLE_UNIT_WORDS` in `recipe_format.py` if needed |
| Steps only say "chicken" | Matcher had `chicken thighs` but not `chicken` | Fix phrasing or countable units, then re-run `apply_ingredient_highlights` |

**Rule of thumb:** If steps say a shorter noun than the ingredient line (chicken vs chicken thighs, garlic vs garlic cloves), either fix ingredient phrasing (parens not commas) or extend `_COUNTABLE_UNIT_WORDS`.

## Ingredient lines that already use `[[Recipe Title]]`

Cross-links to another recipe in the ingredient list are valid; the auto-highlighter may **not** re-wrap that title in a later step. Add `[[Sauce Base]]` manually in the step if needed. Notes Markdown links need `.comments-body a` styling — see `ssg-recipe-links.md`.

## Idempotent re-run

`apply_ingredient_highlights` strips prior `[[...]]` in the instruction block then re-applies from ingredients. Wiki-links to other recipes in ingredients are preserved; only the instruction section is rewritten.

## Verification

- Grep steps: intended nouns should be inside `[[...]]`.
- `pytest tests/test_recipe_format_p2.py -k highlight` after changing `_COUNTABLE_UNIT_WORDS`.