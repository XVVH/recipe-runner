# Syncing engine changes (private collection ↔ public Recipe Runner)

If you run a **private** recipe repo and **this** public engine, they diverge on purpose:

- Private fork may hardcode `SITE_URL` and default `added_by` to your name.
- Recipe Runner uses `RECIPE_RUNNER_SITE_URL` and `RECIPE_RUNNER_ADDED_BY`.

## Compare trees

```bash
for d in site scripts tests docs references; do
  diff -rq ~/dev/recipe-runner/$d ~/path/to/private-repo/$d 2>/dev/null \
    | grep -v __pycache__ || true
done
```

Ignore private-only: personal `recipes/*.md`, one-off migration scripts (`normalize_ingredients.py`, etc.).

## Merge rules

1. `diff -u recipe-runner/site/build.py private/site/build.py` — cherry-pick hunks (e.g. `recipe_links`, parser fixes). **Never** blind-copy whole `build.py`.
2. Same for `recipe_format.py` — port logic and tests together.
3. Port tests; sanitize fixture names (`You`, `Morgan`).
4. Port generic docs only; rewrite card/cookbook guides without private examples.
5. Run `pytest` and portability grep (`portability-audit.md`) before pushing public `main`.

## Verify

```bash
cd ~/dev/recipe-runner
.venv/bin/python site/build.py
.venv/bin/python -m pytest tests/ -q
```