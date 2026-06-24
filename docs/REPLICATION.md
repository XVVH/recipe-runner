# Replicate this recipe stack

Recipe Runner is a **self-contained** copy of the engine used for a private markdown recipe collection: same scripts, SSG, validation, ingest behavior, and golden tests — without anyone else's recipes or site URLs.

Give people **this repo** plus the steps below. They do not need your Hermes profile or vault.

## What matches a full production setup

| Capability | In this repo |
|------------|----------------|
| URL ingest (recipemd → JSON-LD → Wayback → `blocked`) | `scripts/ingest_url.py` |
| Paste / HTML / RecipeMD | `scripts/ingest_text.py` |
| Vision JSON (cookbook + index card, multi-page) | `scripts/ingest_image.py` + `references/vision-extract-prompt.md` |
| PDF text extract | `scripts/ingest_pdf.py` |
| Strict validate on ingest; validate all recipes on build | `site/recipe_format.py` |
| `[[ingredient]]` highlights + idempotent re-run | `apply_ingredient_highlights()` + `scripts/highlight_all_recipes.py` |
| Cross-recipe `[[Title]]` and `/slug/` links | `site/recipe_links.py` at build |
| Continuous numbered steps across `##` phases | `site/templates/recipe.html` + `style.css` |
| Hermes-oriented workflow | `docs/SKILL.md` + all `docs/*.md` |

## 1. Clone and run locally

```bash
git clone https://github.com/XVVH/recipe-runner.git
cd recipe-runner
python3 -m venv .venv
.venv/bin/pip install -r site/requirements.txt
export RECIPE_RUNNER_SITE_URL=http://localhost:4000
export RECIPE_RUNNER_ADDED_BY="Your Name"
.venv/bin/python site/build.py --serve --port 4000
```

Open http://localhost:4000

## 2. Add recipes (no agent)

Always ingest — do not hand-author new `recipes/*.md` without running a script:

```bash
.venv/bin/python scripts/ingest_url.py --added-by "$RECIPE_RUNNER_ADDED_BY" 'https://example.com/recipe'
.venv/bin/python scripts/ingest_text.py --added-by "$RECIPE_RUNNER_ADDED_BY" /tmp/paste.md
```

See `docs/ingest-text-image.md`, `docs/pdf-ingest.md`, `docs/recipe-card-handwriting.md`.

## 3. Optional: Hermes Agent

Hermes is **not** required. If you use [Hermes Agent](https://hermes-agent.nousresearch.com/docs), install the bundled skill:

```bash
mkdir -p ~/.hermes/skills/productivity/recipe-runner/references
cp docs/SKILL.md ~/.hermes/skills/productivity/recipe-runner/
cp docs/*.md ~/.hermes/skills/productivity/recipe-runner/references/
cp references/vision-extract-prompt.md ~/.hermes/skills/productivity/recipe-runner/references/
```

Edit `SKILL.md` **Setup** section: set your repo path, `RECIPE_RUNNER_SITE_URL`, and deploy command (Netlify, S3, etc.).

Triggers include "add a recipe", "import from photo", "paste this recipe" — see skill frontmatter.

Vision ingest: `vision_analyze` per photo using prompts in `references/vision-extract-prompt.md`, save JSON, then `ingest_image.py` (documented in skill + `ingest-text-image.md`).

## 4. Deploy

```bash
.venv/bin/python site/build.py
# static host of your choice, e.g.:
netlify deploy --prod --dir _site
```

Set `RECIPE_RUNNER_SITE_URL` to your production URL before build so sitemap/robots are correct.

## 5. Verify behavior (same as CI)

```bash
.venv/bin/python site/build.py
.venv/bin/python -m pytest tests/ -q
```

Expect all tests green on a clean clone.

## 6. Publish your own fork (privacy)

Before pushing a **public** fork with your recipes:

```bash
grep -rn 'kartjob\|family.recipes' --include='*.md' --include='*.py' . \
  | grep -v '.venv/' | grep -v '_site/' | grep -v tests/ || true
grep -rnE 'your-old-domain|personal-email' ...  # your own patterns
.venv/bin/python site/build.py
# grep _site/ if you previously built with personal content
```

See `docs/portability-audit.md` for a fuller checklist.

## Documentation map

| Doc | Use when |
|-----|----------|
| `docs/recipe-format-contract.md` | Format or validator rules |
| `docs/ingest-checklist.md` | Every ingest |
| `docs/ingest-text-image.md` | Paste, vision, multi-page |
| `docs/recipe-card-handwriting.md` | Index cards, 2+ photos |
| `docs/pdf-ingest.md` | PDF text layer |
| `docs/ingredient-highlights.md` | Step `[[highlights]]` misses |
| `docs/ssg-recipe-links.md` | `[[Other Recipe]]` links |
| `docs/paste-ingest-fallback.md` | `ingest_text` fails on good paste |
| `docs/cookbook-photo-ingest-pitfalls.md` | Vision → JSON crashes |
| `docs/batch-url-ingest-pitfalls.md` | Many URLs in one session |
| `docs/SKILL.md` | Hermes skill source |
| `docs/portability-audit.md` | Sanitizing a public fork |

## Maintainer note (private + public repos)

If you maintain a **private** collection and this **public** engine, port changes with `diff -rq` on `site/`, `scripts/`, `tests/`, and `docs/` — cherry-pick hunks; never blind-copy `build.py` (site URL and `added_by` defaults differ on purpose). Generic porting notes: `docs/upstream-sync.md`.