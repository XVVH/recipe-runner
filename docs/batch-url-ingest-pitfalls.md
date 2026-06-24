# Batch URL ingest pitfalls

Patterns for ingesting multiple recipe URLs in one session. Repo: `~/dev/recipe-runner`, always `.venv/bin/python`.

## Default batch loop

```bash
cd ~/dev/recipe-runner
for u in 'URL1' 'URL2' ...; do
  echo "=== $u"
  .venv/bin/python scripts/ingest_url.py --no-commit --added-by "$RECIPE_RUNNER_ADDED_BY" "$u"
done
.venv/bin/python site/build.py
```

Use `--no-commit` until the batch is reviewed.

## `added_by` on URL ingest

`ingest_url.py` accepts `--added-by` (default: `$RECIPE_RUNNER_ADDED_BY` or `unknown`). Pass it on every URL in a batch for consistent attribution.

## Serious Eats: `invalid_format` with "tags empty"

Direct URL ingest often **extracts OK** but fails strict validate because JSON-LD yields no tags (warnings → errors under `strict=True`).

**Fix (reliable):**

```bash
cd ~/dev/recipe-runner
.venv/bin/recipemd-extract 'https://www.seriouseats.com/...'

.venv/bin/python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'scripts'); sys.path.insert(0, 'site')
from ingest_common import process_recipemd
md = Path('extracted.md').read_text()
r = process_recipemd(
    md,
    source_url='https://www.seriouseats.com/...',
    added_by='You',
    title_override='Three-Bean Salad',
    yield_override='8 servings',
    schema_metadata={'tags': ['salad', 'beans', 'side dish']},
)
assert r['status'] == 'success', r.get('error')
Path(r['output_path']).write_text(r['md'], encoding='utf-8')
print(r['output_path'])
"
```

`web_extract` on Serious Eats often **fails to fetch** — do not rely on it for SE.

## Old blogs: `blocked` after recipemd + Wayback

**Fix:** `web_extract` (or user paste) → build canonical RecipeMD:

- First line: `Title, by Author` (parsed by `parse_title_author_from_plaintext`).
- Strip that line from body before `process_recipemd`, then prepend `# Title`.
- Body: ingredient groups with `- *qty* name`, `---`, step sections (see `_template.md`).
- Do **not** put `Yield:` prose before ingredients.
- Finish with `process_recipemd(..., source_label='<url>', schema_metadata={'tags': [...]})`.

## NYT Cooking

- Live `cooking.nytimes.com/recipes/...` often works with direct `ingest_url.py`.
- Wayback-wrapped NYT URLs also work when passed to `ingest_url.py`.
- Accented titles slugify oddly; rename slug manually if you care.

## Partial frontmatter in paste files

Do not prepend half-baked YAML to RecipeMD for `ingest_text` — prefer `# Title` in body or `--title` + `schema_metadata` via `process_recipemd`.

## After batch

1. `site/build.py` (exit 0).
2. Remove cwd artifacts (`extracted.md`, `tmp-*.md`).
3. Commit and deploy when ready.

## Sites where extract fails

Some sites need browser copy or full canonical rewrite with `##` groups + phased steps. See validator warnings in build output; rewrite steps/ingredients until `build.py` is clean.