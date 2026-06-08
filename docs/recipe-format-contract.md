# Recipe Runner — Format Contract

**Canonical sources in repo** (always prefer these over this file if they drift):
- `recipes/_template.md` — copy-paste starter
- `recipes/brown-butter-chocolate-chip-cookies.md` — flat ingredients, `##` instruction phases, `[[highlights]]`, notes bullets
- `recipes/caesar-style-kale-salad-with-roasted-onions.md` — `##` ingredient groups, same body shape

**Enforcement code** (single module — do not duplicate rules elsewhere):
- `site/recipe_format.py` — `canonicalize()`, `validate_recipe()`, `validate_recipe_file()`
- `tests/test_recipe_format.py` — golden fixtures

## Frontmatter

```yaml
---
title: Recipe Title              # required; no H1 in body
date: YYYY-MM-DD                  # publish or ingest date
author: Name                      # null if unknown
source: https://example.com/...   # URL or "Book, p.42"
recommended_by: null              # string or null
added_by: null                    # your name, or set via --added-by / $RECIPE_RUNNER_ADDED_BY
favorite: no                      # yes | no | true | false (build normalizes)
yield: 4 servings
tags:
  - tag-one
description: Optional one-liner   # frontmatter ONLY — never duplicate in body
---
```

## Body (ingredients-first, 2-3 sections)

Section 1 — **ingredients** (starts immediately after frontmatter `---`, no leading `---`, no H1, no prose description):

```
- *1 cup* (227 g) butter
## Optional group name
- *2 tsp* salt
```

Section 2 — **instructions** (after `\n---\n`):

```
## Phase name
Step text. Use [[butter]] for client-side highlights (literal match in step text).

## Next phase
Another step.
```

- Optional `## Phase name` headings group steps; the SSG renders **one continuous numbered list** (numbers do not restart per phase).
- **One non-empty line = one numbered step** (single newlines count; blank lines are ignored).
- Flat steps (no `##`) are valid for ingest; phases are optional polish.
- `[[Recipe Title]]` in steps or notes can link to other recipes when the title matches (build-time via `recipe_links.py`).
- `[[highlights]]` for ingredients are optional; `recipe.js` fills gaps client-side when brackets remain.

Section 3 — **notes** (optional, after second `\n---\n`):

```
- Do ahead: ...
- A note with ~~strikethrough~~
```

Notes may also come from frontmatter `notes: |` (merged at build). Ingest pulls "Do ahead:" / "Editor's note:" lines out of instructions into section 3.

## Validation modes

| Mode | When | Behavior |
|------|------|----------|
| `strict=False` | `build.py` on legacy files | Errors block build; warnings (body description, HTML in steps) print only |
| `strict=True` | ingest scripts before write | Warnings promoted to errors; requires non-empty `tags` |

**Rules that block (errors):** missing `title`/`date`; no ingredient section; ingredients don't look like `- *qty*` lines; no instruction steps; H1 in body; `*Source: url*` in body (use `source:` frontmatter).

**Legacy warnings (migrate away):** body description section; raw HTML in steps/notes.

## Ingest pipeline (deterministic)

```
recipemd-extract / ld+json → normalize() → canonicalize(source_url, added_by) → validate_recipe(strict=True) → write
```

- **Do not** use `migrate_to_frontmatter.migrate()` as the final ingest shape — it emits the old body layout.
- On failure: JSON `"status": "invalid_format"`, no file written, exit 1.
- `--dry-run` runs full pipeline but skips write/commit.

## Deploy

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 site/build.py    # validates all recipes first
netlify deploy --prod
```

Set `RECIPE_RUNNER_SITE_URL` in your Netlify env for correct sitemap/robots.txt output.

## Migration checklist (legacy -> canonical)

1. Hand-edit or re-ingest using canonical shape.
2. Add `added_by` when ready for strict validation on that file.
3. Remove body description (move to `description:` frontmatter only).
4. Promote notes from instruction steps to section 3 bullets.
5. Strip HTML from steps; use `[[highlights]]` instead of `<strong>` etc.
