# Recipe Runner

A markdown-native recipe database with a Python static site generator and ingest
pipeline. Store recipes as plain text files, build a fast static site, and import
from URLs, pasted text, or vision-extracted JSON. No database, no framework, no
Hermes Agent required to run it.

## Quick Start

```
git clone https://github.com/XVVH/recipe-runner && cd recipe-runner
python3 -m venv .venv
.venv/bin/pip install -r site/requirements.txt
.venv/bin/python site/build.py --serve --port 4000
```

Open http://localhost:4000

## Adding a Recipe

### From a URL

```
.venv/bin/python scripts/ingest_url.py --added-by "You" https://example.com/recipe
```

Tries recipemd-extract, falls back to JSON-LD, falls back to Wayback CDX. Bot-walled
sites report status `blocked` rather than writing a bad file.

### From pasted text or a local file

```
.venv/bin/python scripts/ingest_text.py --added-by "You" /path/to/paste.md
```

First line `Title, by Author` is parsed automatically. Accepts plain text, HTML,
or existing RecipeMD format.

### From a photo (vision JSON)

Extract structured JSON from a recipe photo using the prompt in
`references/vision-extract-prompt.md`, then:

```
.venv/bin/python scripts/ingest_image.py --added-by "You" /path/to/extracted.json
```

Multi-photo recipes (e.g. card front + back) can be merged before ingest.
See `references/vision-extract-prompt.md` for the extraction prompt and JSON shape.

### From a PDF (text layer)

```bash
.venv/bin/python scripts/ingest_pdf.py /path/to/recipe.pdf --out /tmp/extract.txt
```

Structure as RecipeMD, then `ingest_text.py`. See `docs/pdf-ingest.md`.

## Recipe Format

Recipes are YAML frontmatter + an ingredients-first body with three `---` sections:
ingredients, instructions, and optional notes. `_template.md` is the canonical shape.
Ingredient highlights (`[[ingredient]]`) in instruction steps are applied automatically
on ingest.

See `recipes/_template.md` for the full format.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| RECIPE_RUNNER_SITE_URL | http://localhost:4000 | Base URL for sitemap and robots.txt |
| RECIPE_RUNNER_ADDED_BY | unknown | Default added_by when --added-by is not passed |

Set these as environment variables or in a `.env` file before running build or ingest.

## Deploy

Any static host that can run a Python build step or serve a pre-built `_site/` directory.

Netlify: `netlify.toml` is included. Set `RECIPE_RUNNER_SITE_URL` as a Netlify env var,
then deploy:

```
.venv/bin/python site/build.py && netlify deploy --prod --dir _site
```

## Validation

`site/build.py` validates all recipes at build time. Legacy-shaped recipes (body
description before ingredients) produce warnings but do not fail the build. Recipes
with structural errors fail hard so bad data never reaches production.

Run a strict check on a single file:

```python
from site.recipe_format import validate_recipe
issues = validate_recipe(open("recipes/my-recipe.md").read(), strict=True)
print(issues)
```

## Vision Ingest (Backlog)

The current vision path is manual: extract JSON from a photo using the prompt in
`references/vision-extract-prompt.md`, then pass the result to `ingest_image.py`.
An automated Hermes Agent workflow that handles the full photo-to-recipe pipeline
(camera roll -> extraction -> ingest -> build) is a tracked backlog item. Contributions
welcome.

## Hermes Agent Integration

A Hermes skill template is included at `docs/SKILL.md`. Copy it to
`~/.hermes/skills/productivity/recipe-runner/` along with the `docs/` reference files and
update the paths to match your setup. This wires the ingest pipeline into agent-driven
workflows: paste-to-recipe, vision photo ingest, and automated deploy via natural language.

## Documentation

| File | Contents |
|------|----------|
| `docs/recipe-format-contract.md` | Full YAML frontmatter spec and body shape |
| `docs/ingest-checklist.md` | Pre-commit ingest checklist |
| `docs/ingest-text-image.md` | Text paste and vision photo ingest guide |
| `docs/ingestion-fallback-chain.md` | URL ingest tier chain and outcome codes |
| `docs/anti-scraping-tiers.md` | Site-specific scraping tiers and workarounds |
| `docs/recipemd-format.md` | RecipeMD upstream format reference |
| `docs/ssg-design-tokens.md` | SSG theme design tokens |
| `docs/SKILL.md` | Hermes Agent skill template |

## Contributing

Fork, branch, PR. Keep your personal recipe data out of PRs; example recipes in
`recipes/` are for testing the engine, not for collecting community recipes. Bug fixes,
ingest improvements, and SSG features are all welcome.

See `PORTABLE.md` for notes on forking and adapting this project.
