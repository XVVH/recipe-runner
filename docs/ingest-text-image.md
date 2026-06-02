# Text and Image Ingestion

All ingest paths share `scripts/ingest_common.py` → `canonicalize()` → `validate_recipe(strict=True)`.

## From pasted text / RecipeMD file

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_text.py /path/to/recipe.md
.venv/bin/python3 scripts/ingest_text.py --dry-run recipe.md
cat recipe.md | .venv/bin/python3 scripts/ingest_text.py -
```

Options: `--title`, `--source` (URL or "Cookbook, p. 42"), `--slug`, `--added-by` (default: `$RECIPE_RUNNER_ADDED_BY` or `unknown`), `--no-commit`

From saved HTML (bookmarklet / page save):

```bash
.venv/bin/python3 scripts/ingest_text.py saved-page.html --from-html --source "https://original-url"
```

Agent workflow: user pastes RecipeMD or recipe text → agent saves to `/tmp/recipe-ingest.md` → run `ingest_text.py` (do not hand-write `recipes/*.md` without running the script).

**First line `Title, by Author`** (e.g. `Tomato Basil Pasta, by Avis`) is split into title + author before canonicalize (`parse_title_author_from_plaintext` in `ingest_common.py`).

## From cookbook photo / image

Vision extraction is manual; the script writes the file.

1. Use the prompt in `references/vision-extract-prompt.md` with any LLM that supports image input.
2. Save the returned JSON to `/tmp/recipe-extract.json`.
3. Run:

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_image.py --json /tmp/recipe-extract.json \
  --source "Cookbook Title (p. 42)"
```

If the LLM returns RecipeMD markdown instead of JSON:

```bash
.venv/bin/python3 scripts/ingest_image.py --markdown /tmp/recipe.md --source "..."
```

Multi-photo (e.g. front + back of a recipe card): pass multiple `--json` files; the script merges them before canonicalize.

Status values: `success`, `exists`, `error`, `invalid_format` (same as `ingest_url.py`).

## Hermes Agent (optional)

If you use Hermes Agent, the `vision_analyze` tool can drive step 1 of the image path directly. See `docs/SKILL.md` in this repo for a Hermes skill template you can adapt.

## Automated vision workflow (backlog)

A fully automated camera-roll → ingest pipeline (no manual JSON step) is a tracked backlog item. Contributions welcome.
