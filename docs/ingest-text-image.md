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

**First line `Title, by Author`** (e.g. `Tomato Basil Pasta, by Morgan`) is split into title + author before canonicalize (`parse_title_author_from_plaintext` in `ingest_common.py`).

## From cookbook photo / image

Handwritten **recipe cards** (ruled index cards, multiple photos, sticky notes, pencil cross-outs): see `docs/recipe-card-handwriting.md`. Prefer vision → canonical direct write + `build.py`; do not rely on `ingest_text.py` alone for tag/yield preamble lines.

Vision extraction is agent-driven; the script merges pages and writes the file.

**Single page:** Prompt A in `references/vision-extract-prompt.md` → save JSON → ingest.

**Multi-page cookbook:** Prompt A on page 1, Prompt B on pages 2+; save as
`page-01.json`, `page-02.json`, … then:

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_image.py \
  --json-dir /tmp/recipe-pages \
  --recipe-type cookbook \
  --source "Cookbook Title (p. 42–43)"
```

**Index card (front + back):** Prompts C and D → two JSON files:

```bash
.venv/bin/python3 scripts/ingest_image.py \
  --json /tmp/recipe-front.json /tmp/recipe-back.json \
  --recipe-type index-card \
  --source "Handwritten card"
```

Each JSON may include optional `page_index` and `page_role` (`primary`, `continuation`,
`index_front`, `index_back`). Merge order follows `page_index`, then file order.
Instructions append across pages (no dedupe); ingredients dedupe exact strings.

Vision responses wrapped in markdown fences are accepted — `ingest_image.py` parses them.

If the LLM returns RecipeMD markdown instead of JSON:

```bash
.venv/bin/python3 scripts/ingest_image.py --markdown /tmp/recipe.md --source "..."
```

Status values: `success`, `exists`, `error`, `invalid_format` (same as `ingest_url.py`).

## Hermes Agent workflow

See `references/vision-extract-prompt.md` § "Hermes agent workflow (multi-photo)".
Use `vision_analyze` once per photo with the matching prompt, save JSON files, then
`ingest_image.py --json-dir` or `--json file1 file2 …`.

## Automated vision workflow (backlog)

Direct `--images photo.jpg` without a vision step is not implemented (vision runs in
Hermes). The multi-photo merge + page-role prompts above are the supported path.
