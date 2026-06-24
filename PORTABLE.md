# Portable Notes for Recipe Runner

**Canonical onboarding:** [`docs/REPLICATION.md`](docs/REPLICATION.md). **Hermes users:** [`docs/HERMES-AGENT.md`](docs/HERMES-AGENT.md) + `bash scripts/install-hermes-skill.sh`.

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

Copy `docs/SKILL.md`, all of `docs/*.md` into `~/.hermes/skills/productivity/recipe-runner/references/`, and `references/vision-extract-prompt.md` from the repo. See `docs/REPLICATION.md` §3.

## What is not included

- Personal recipe data. Bring your own.
- Legacy migration scripts (`migrate_to_frontmatter.py` ships for internal use by the
  ingest pipeline; the user-facing scripts `normalize_ingredients.py`,
  `fix_ingredient_units.py` are not included in the starter — they were purpose-built
  for a specific legacy collection and are not generally useful).
- Camoufox tier for bot-walled sites. The URL ingest chain currently ends at `blocked`
  for sites that require browser-level rendering. Camoufox integration
  is a backlog item.

## Vision path status

Manual/agent-driven. The prompt at `references/vision-extract-prompt.md` produces a JSON blob
that `ingest_image.py` can consume. Full multi-photo workflow is documented in `docs/ingest-text-image.md` and `docs/recipe-card-handwriting.md`.

## Maintaining engine parity

If you also run a private collection on the same engine, use `docs/upstream-sync.md` and `docs/portability-audit.md` when porting changes to or from this public repo.