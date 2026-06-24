# Hermes Agent — install playbook

**Audience:** Hermes Agent when the user wants Recipe Runner (markdown recipes, ingest, static site).

**Goal:** Clone repo (if needed), venv, install skill, verify — without asking the user to hand-copy files.

## When to run this playbook

- User asks to set up / install / use **recipe runner**, **recipe collection** (generic), or import recipes to a **markdown recipe site**
- User pasted a recipe URL, photo, or text and you need the ingest pipeline
- Skill `recipe-runner` is missing from `skills_list` or `skill_view` fails

Do **not** use this for unrelated cooking questions with no site/repo intent.

## Decision tree

1. **Repo on disk?**  
   - Prefer `references/local-config.md` → `repo_path` if skill already installed.  
   - Else check `~/dev/recipe-runner` or `RECIPE_RUNNER_REPO` env.  
   - If missing: `git clone https://github.com/XVVH/recipe-runner.git` into `~/dev/recipe-runner` (or user’s `~/dev`).

2. **Venv?**  
   From repo root:
   ```bash
   test -x .venv/bin/python || python3 -m venv .venv
   .venv/bin/pip install -r site/requirements.txt
   ```

3. **Hermes skill?**  
   From repo root:
   ```bash
   bash scripts/install-hermes-skill.sh
   ```
   Optional env before install: `RECIPE_RUNNER_SITE_URL`, `RECIPE_RUNNER_ADDED_BY`, `HERMES_RECIPE_RUNNER_SKILL_DIR`.

4. **Load skill**  
   `skill_view(name='recipe-runner')` then follow ingest checklist in `references/ingest-checklist.md`.

## Agent rules (after install)

| Rule | Detail |
|------|--------|
| Python for build/ingest | Repo `.venv/bin/python` only — **not** Hermes agent venv |
| Working directory | `terminal(..., workdir=<repo_path>)` from `local-config.md` |
| New recipes | `scripts/ingest_*.py` — never hand-author new `recipes/*.md` |
| Vision photos | `vision_analyze` + prompts in `references/vision-extract-prompt.md` → JSON → `ingest_image.py` |
| Strict gate | Ingest must pass `validate_recipe(strict=True)`; then `site/build.py` exit 0 before deploy |

## One-shot install (copy-paste for terminal)

Replace `REPO` if not `~/dev/recipe-runner`:

```bash
REPO="${RECIPE_RUNNER_REPO:-$HOME/dev/recipe-runner}"
if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/XVVH/recipe-runner.git "$REPO"
fi
cd "$REPO"
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/pip install -q -r site/requirements.txt
export RECIPE_RUNNER_SITE_URL="${RECIPE_RUNNER_SITE_URL:-http://localhost:4000}"
export RECIPE_RUNNER_ADDED_BY="${RECIPE_RUNNER_ADDED_BY:-You}"
bash scripts/install-hermes-skill.sh
.venv/bin/python site/build.py
.venv/bin/python -m pytest tests/ -q
```

## Verification checklist (agent)

- [ ] `$REPO/.venv/bin/python site/build.py` exits 0
- [ ] `$REPO/.venv/bin/python -m pytest tests/ -q` — all passed
- [ ] `~/.hermes/skills/productivity/recipe-runner/SKILL.md` exists
- [ ] `skill_view(name='recipe-runner')` returns content
- [ ] `references/local-config.md` has correct `repo_path`

## Tell the user (short)

- Repo path and that the **recipe-runner** skill is installed  
- How to add a recipe (URL / paste / photo) in one line  
- Local site: `.venv/bin/python site/build.py --serve --port 4000` unless they asked for deploy  

## Full human doc

`docs/REPLICATION.md` in the repo — share link if they want to read outside Hermes.

## Pitfalls

- **Cloning without venv** — ingest fails on missing `frontmatter` / deps  
- **Using Hermes venv for `build.py`** — wrong deps / paths  
- **Skipping skill install** — agent won’t load linked references on triggers  
- **Hardcoding someone else’s `repo_path`** — always read `local-config.md` after install script runs  