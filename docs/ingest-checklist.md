# Ingest Checklist

Run through this before considering an ingest done. Order matters.

## Before write

1. **Use an ingest script** — `ingest_url.py`, `ingest_text.py`, or `ingest_image.py` from `scripts/`. Do not create `recipes/*.md` by hand unless editing an existing file.
2. **Source set** — URL ingests get `source` from the URL; image/text need `--source` (URL or `"Book, p. N"`).
3. **Vision path** — photos: one JSON per image using `references/vision-extract-prompt.md`
   (Prompt A/B cookbook, C/D index card). Multi-page: `--json-dir DIR --recipe-type cookbook`
   or multiple `--json` files with `--recipe-type index-card`.
4. **Dry-run when unsure** — `ingest_* --dry-run` prints status without writing (`invalid_format`, `blocked`, `exists` are failures to fix).

## After write

5. **Strict validate passed** — ingest only writes on `validate_recipe(strict=True)` success; if you hand-edited, re-run ingest or `build.py`.
6. **Spot-check file** — open `recipes/<slug>.md` against `recipes/_template.md` / golden files (ingredients-first, `favorite: no` unquoted, no `*Source:*` in body, `source:` in frontmatter).
7. **Local build** — `.venv/bin/python3 site/build.py` exits 0.
8. **Deploy** — deploy only after local build succeeds.
9. **Smoke test** — open recipe on your production URL; check fonts/CSS load correctly.

## Optional follow-up

10. **Git commit** — ingest scripts can auto-commit; otherwise commit after review.
11. **Blocked URL** — status `blocked` → Wayback exhausted; try bookmarklet/manual (see `docs/ingestion-fallback-chain.md`).
