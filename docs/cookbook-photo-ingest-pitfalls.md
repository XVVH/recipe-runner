# Cookbook photo ingest — pitfalls

Prompts: `references/vision-extract-prompt.md` in this repo.

## When vision text is already in chat

If a prior `vision_analyze` already returned structured recipe text, build one JSON file matching the shared schema (`page_role: primary`, `ingredients`, `instructions`, `notes`) and run:

```bash
cd ~/dev/recipe-runner
.venv/bin/python scripts/ingest_image.py --json /tmp/slug.json \
  --recipe-type cookbook \
  --added-by "$RECIPE_RUNNER_ADDED_BY" \
  --source "Cookbook Title, p. N"
.venv/bin/python scripts/ingest_image.py ... --dry-run   # first when unsure
```

Use `--no-commit` until reviewed; then `site/build.py` and deploy.

## YAML / frontmatter crash on `--keep-description`

**Symptom:** `ingest_image.py` dies in `apply_ingredient_highlights` with `yaml.scanner.ScannerError: mapping values are not allowed in this context` (often `description:`).

**Cause:** Long cookbook intros in frontmatter `description:` contain unescaped `:` or apostrophes.

**Fix:**
- Default: **omit** `--keep-description`; put intro in `notes` as a short bullet, or skip it.
- If description must stay in frontmatter, quote it properly or shorten after write.

## Yield mangling: `1½` → `11/2`

**Symptom:** `yield: about 11/2 cups` instead of `about 1½ cups`.

**Fix:** Spot-check `yield:` after ingest; patch to Unicode fraction or `1 1/2`. Re-run `site/build.py`.

## Source attribution

Photos rarely include book title on the page. Use `--source` with an honest placeholder (`Cookbook photo — subtitle`) and replace when you know title + page.

## Author

Only set `author` when printed on the page. Cookbook intros in first person do not imply a known `author` field.