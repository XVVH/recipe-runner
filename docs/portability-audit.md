# Portability audit (public fork)

Run before the **first** public push and after copying content from a private collection.

## Grep (non-test, non-venv)

```bash
cd /path/to/your/recipe-runner-fork
grep -rn 'family.recipes\|family_recipes\|kartjob' \
  --include='*.py' --include='*.md' --include='*.html' --include='*.toml' \
  . | grep -v '.venv/' | grep -v '_site/' | grep -v tests/ || true

grep -rnE 'added_by: (null|Josh)' \
  --include='*.md' recipes/ || true
```

Add your own patterns (old domain, email, real names in notes).

## Rebuild `_site/`

Stale HTML can contain old titles or notes:

```bash
.venv/bin/python site/build.py
grep -r 'personal-pattern' _site/ || true
```

## Common leak locations

- Module docstrings in `scripts/ingest_*.py`
- `canonicalize()` docstring in `site/recipe_format.py`
- `references/vision-extract-prompt.md` — `cd` path examples
- Recipe **notes** bodies in `recipes/*.md`
- Commit messages — read `git log` before push

## Recipe Runner defaults (intentional)

| Setting | Public repo |
|---------|-------------|
| `SITE_URL` | `RECIPE_RUNNER_SITE_URL` env, default `http://localhost:4000` |
| `added_by` | `RECIPE_RUNNER_ADDED_BY` or `--added-by`; golden fixtures use `You` |
| Strict ingest | `added_by` required on new ingests |

Do not replace env-based `build.py` with a hardcoded production URL when porting from a private fork.

## Hermes skill

Copy `docs/SKILL.md` and all `docs/*.md` into `~/.hermes/skills/productivity/recipe-runner/references/`. Do not publish your personal paths in a public skill gist — use placeholders.