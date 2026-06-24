# Paste ingest failures and direct-write fallback

When `ingest_text.py` rejects a user paste, prefer fixing the input; if the paste is already complete recipe content, write canonical `recipes/<slug>.md` and gate with `site/build.py`.

## Common `invalid_format` / YAML errors

| Symptom | Cause | Fix |
|--------|--------|-----|
| `mapping values are not allowed` | Unquoted `source:` or body line with `key: value` | Put attribution in frontmatter `source:` only; quote values with colons |
| `body contains a description section` | Prose block before ingredients | Move narrative to frontmatter `description:` or notes; body starts with ingredient bullets |
| `missing instruction section` | No steps after ingredient `---` | Add `---` then steps (or `##` phase headings) |
| `tags empty` | No tags after canonicalize | Add tags in paste or `schema_metadata` via `process_recipemd` |
| `missing required field 'title'` on dry-run | Parser expected first line `Title, by Author` | First line: `Tomato Pasta, by Morgan` OR pass `--title` |
| Description + missing instructions together | Hand-transcribed paste with `*Yield:*` before ingredients | Body starts with `- *qty*` lines; use `--title` / `--yield` / `--author`; or direct write — see `recipe-card-handwriting.md` |

## When to use direct write (exception to checklist rule 1)

Use a careful write to `recipes/<slug>.md` when:

1. Paste is complete and matches `recipes/_template.md` or a golden example recipe.
2. `ingest_text.py --dry-run` still fails after one structured fix attempt.
3. You immediately run `.venv/bin/python site/build.py` — non-zero exit means fix before commit/deploy.

Default flow remains save `/tmp/…` → `ingest_text.py`.

## Cross-linking related recipes

Build-time resolution in `site/recipe_links.py` — see `ssg-recipe-links.md`.

- **In body:** `[[Other Recipe Title]]` in ingredients/steps → `<a class="recipe-ref">` when title/slug matches.
- **Notes:** `[[Title]]` and `/other-slug/`.
- **Step highlights (same recipe):** `ingredient-highlights.md`.

## Slug from title

`Perfect Weeknight Pasta` → `perfect-weeknight-pasta.md` (same rules as `slugify(title)` in ingest).