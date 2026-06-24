---
name: recipe-runner
description: Manage a Recipe Runner collection. Canonical YAML-frontmatter + ingredients-first body, recipe_format.py validation, ingest pipeline (URL/text/image/PDF), Python SSG, static deploy. Generic — copy from the recipe-runner repo docs/.
version: 1.1.0
triggers:
  - recipe collection
  - recipe runner
  - recipe site
  - recipe import
  - ingest recipe
  - paste this recipe
  - import from photo
  - import from url
  - add a recipe
  - recipe format
  - handwritten recipe card
linked_files:
  references:
    - REPLICATION.md
    - recipe-format-contract.md
    - ingest-checklist.md
    - ingest-text-image.md
    - recipe-card-handwriting.md
    - pdf-ingest.md
    - ingredient-highlights.md
    - ssg-recipe-links.md
    - paste-ingest-fallback.md
    - cookbook-photo-ingest-pitfalls.md
    - batch-url-ingest-pitfalls.md
    - ingestion-fallback-chain.md
    - anti-scraping-tiers.md
    - recipemd-format.md
    - ssg-design-tokens.md
    - vision-extract-prompt.md
---

# Recipe Runner

## Setup

> **Install:** see `references/REPLICATION.md` in this skill folder. Summary: clone the repo, venv, copy this `SKILL.md` + all `references/*.md` + repo `references/vision-extract-prompt.md`.

Repo: `~/dev/recipe-runner` (your clone path)
Python SSG: `.venv/bin/python3 site/build.py` → `_site/`
Production URL: `RECIPE_RUNNER_SITE_URL` env var
Default ingest attribution: `RECIPE_RUNNER_ADDED_BY` or `--added-by "You"`

## Format contract

See `references/recipe-format-contract.md` (also in `docs/` in the repo).

Short form:
- YAML frontmatter: `title`, `date`, `author`, `source`, `recommended_by`, `added_by`, `favorite`, `yield`, `tags`
- Body: ingredients-first, three `---`-separated sections (ingredients / instructions / notes)
- `[[ingredient]]` in steps for client-side highlights
- Golden files: `recipes/brown-butter-chocolate-chip-cookies.md`, `recipes/caesar-style-kale-salad-with-roasted-onions.md`

**Never hand-author `recipes/*.md` for new recipes.** Always run through an ingest script so canonicalize() and validate_recipe(strict=True) gate the write.

## Ingest checklist

See `references/ingest-checklist.md`. Short form:

1. Use an ingest script (not hand-authored files)
2. Source set (`--source` for image/text)
3. Dry-run when unsure (`--dry-run`)
4. Strict validate passes (ingest enforces this)
5. Spot-check against `_template.md`
6. Local build exits 0
7. Deploy only after local build

## Adding a recipe

### From URL

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_url.py --added-by "You" https://example.com/recipe
```

Fallback chain: recipemd-extract → ld+json → Wayback CDX → `blocked`.
See `references/ingestion-fallback-chain.md` and `references/anti-scraping-tiers.md`.

### From pasted text

```bash
.venv/bin/python3 scripts/ingest_text.py --added-by "You" /tmp/recipe-ingest.md
```

Agent workflow: save paste to `/tmp/recipe-ingest.md`, run ingest_text.py.
First line `Title, by Author` is parsed automatically.
See `references/ingest-text-image.md`.

### From photo (vision path)

Handwritten cards: `references/recipe-card-handwriting.md`. Multi-page cookbook and index-card flows: `references/vision-extract-prompt.md`. Pitfalls: `references/cookbook-photo-ingest-pitfalls.md`.

1. `vision_analyze` each photo with Prompt A/B (cookbook) or C/D (index card)
2. Save JSON files (`page-01.json`, …) — markdown fences OK
3. Run:

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_image.py \
  --json-dir /tmp/recipe-pages \
  --recipe-type cookbook \
  --added-by "You" --source "Cookbook Title (p. 42–43)"
```

Single image: `--json /tmp/recipe-extract.json`. Index card: `--json front.json back.json --recipe-type index-card`.

See `references/ingest-text-image.md`.

### From PDF (text layer)

```bash
.venv/bin/python3 scripts/ingest_pdf.py /path/to/recipe.pdf --out /tmp/extract.txt
```

Structure RecipeMD → `ingest_text.py`. See `references/pdf-ingest.md`.

## Build and deploy

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 site/build.py          # validates + builds _site/
netlify deploy --prod                    # or your static host's deploy command
```

Always build locally first. Set `RECIPE_RUNNER_SITE_URL` before deploy for correct sitemap.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `RECIPE_RUNNER_SITE_URL` | `http://localhost:4000` | Base URL for sitemap/robots.txt |
| `RECIPE_RUNNER_ADDED_BY` | `unknown` | Default `added_by` when `--added-by` not passed |

## Format drift prevention

`site/build.py` validates every recipe at build time:
- Errors (missing title/date, no ingredients, H1 in body) → build fails
- Warnings (legacy body description, HTML in steps) → printed only

Strict mode (`validate_recipe(strict=True)`) runs on every ingest write. Invalid files are never written.

**Highlights:** `scripts/highlight_all_recipes.py` or `references/ingredient-highlights.md`. **Cross-links:** `references/ssg-recipe-links.md`. **Paste failures:** `references/paste-ingest-fallback.md`. **Batch URLs:** `references/batch-url-ingest-pitfalls.md`.

## Repo structure

```
recipe-runner/
  recipes/                 # *.md + _template.md (build skips recipes/_*.md)
  docs/                    # format contract, ingest guides, operational references
  site/                    # build.py, recipe_format.py, templates/, static/
  scripts/                 # ingest_url.py, ingest_text.py, ingest_image.py, ingest_common.py, highlight_all_recipes.py
  references/              # vision-extract-prompt.md (also copy into skill references/)
  tests/
  .venv/                   # project venv — always use for build/ingest
```

## Adapting this skill

1. Follow `references/REPLICATION.md` (clone repo, env vars, optional Hermes install).
2. Update repo path and `RECIPE_RUNNER_SITE_URL` in this file if needed.
3. Keep `references/` in sync with the repo's `docs/*.md` when the engine updates.
