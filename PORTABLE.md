# Portable Notes for Recipe Runner

## Forking this project

1. Clone the repo and create a venv: `python3 -m venv .venv && .venv/bin/pip install -r site/requirements.txt`
2. Set `RECIPE_RUNNER_SITE_URL` to your production URL before deploying.
3. Set `RECIPE_RUNNER_ADDED_BY` to your name (or pass `--added-by` on every ingest call).
4. Put your recipes in `recipes/`. Use `scripts/ingest_*` to add them — do not hand-author
   `recipes/*.md` files directly; the ingest pipeline enforces the canonical format.
5. Run `site/build.py` to build. Deploy `_site/` anywhere.

The four example recipes in `recipes/` are golden test fixtures. They are tested by
`tests/`. You can add your own recipes alongside them or replace them once you have
your own golden files.

## Hermes Agent skill

If you use Hermes Agent, you can adapt the `recipe-collection` skill as a starting point
for wiring the ingest pipeline into agent-driven workflows. Copy it to your own
`~/.hermes/skills/` directory and update the paths and site URL to match your setup.
A community-maintained recipe-runner skill is a planned contribution — not yet available.

## What is not included

- Personal recipe data. Bring your own.
- Legacy migration scripts (`migrate_to_frontmatter.py` ships for internal use by the
  ingest pipeline; the user-facing scripts `normalize_ingredients.py`,
  `fix_ingredient_units.py` are not included in the starter — they were purpose-built
  for a specific legacy collection and are not generally useful).
- Camoufox tier for bot-walled sites. The URL ingest chain currently ends at `blocked`
  for sites like Serious Eats that require browser-level rendering. Camoufox integration
  is a backlog item.

## Vision path status

Manual only. The prompt at `references/vision-extract-prompt.md` produces a JSON blob
that `ingest_image.py` can consume. There is no automated camera-roll-to-recipe pipeline
yet. A Hermes-native agent workflow for this is a tracked backlog item — see the
Contributing section in README.md.
