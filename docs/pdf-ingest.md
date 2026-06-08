# PDF recipe ingest (Recipe Runner)

Text-first extraction for recipe PDFs. Vision is a **fallback** for scanned pages only.

## When to use

| PDF type | Path |
|----------|------|
| Selectable text (export, print-to-PDF, most publisher PDFs) | `ingest_pdf.py` → structure RecipeMD → `ingest_text.py` |
| Scanned / image-only (empty `get_text()`) | Render pages → vision JSON → `ingest_image.py` |

Do **not** run full-document vision on text-native PDFs — it often pulls layout chrome, equipment lists, and marketing into `notes`.

## Text path (default)

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_pdf.py /path/to/recipe.pdf --out /tmp/recipe-extract.txt
```

- Applies light glyph fixes (`!our` → flour, etc.) unless `--no-fix-glyphs`.
- Exits `1` with JSON hint if total text &lt; `--min-chars` (default 200) → use vision fallback.

Turn the extract into **RecipeMD** per `docs/recipemd-format.md`, then:

```bash
.venv/bin/python3 scripts/ingest_text.py /tmp/recipe-structured.md \
  --source "Publisher — Recipe title (PDF)" \
  --author "Name if known" \
  --added-by "You" \
  --dry-run
```

Remove `--dry-run` when valid.

## Vision fallback (scanned PDF)

1. Render pages (PyMuPDF `get_pixmap` or preview export).
2. One JSON per page via vision extraction and cookbook prompts in `references/vision-extract-prompt.md`.
3. Prompt addition: omit equipment, ads, and promos; `notes` = recipe tips only.
4. `ingest_image.py --json-dir ... --recipe-type cookbook --source "..."`

## Dependency

`pymupdf` in `site/requirements.txt` — install with `.venv/bin/pip install -r site/requirements.txt`.