#!/usr/bin/env python3
"""
ingest_text.py -- Ingest recipe text into a Recipe Runner collection (pasted RecipeMD, saved HTML, or file).

Use when the user provides recipe text in chat, a bookmarklet HTML save, or a hand-written
RecipeMD file. Same pipeline as ingest_url.py: normalize → canonicalize → strict validate.

Usage:
    python3 scripts/ingest_text.py path/to/recipe.md
    python3 scripts/ingest_text.py --file path/to/page.html --from-html
    cat recipe.md | python3 scripts/ingest_text.py -
    python3 scripts/ingest_text.py --dry-run recipe.md

Options:
    --title       Override title (otherwise from # heading or frontmatter title:)
    --source      Source URL or attribution string (frontmatter source:)
    --slug        Force output slug (default: slugify title, uniquify)
    --added-by    added_by frontmatter (default: $RECIPE_RUNNER_ADDED_BY or 'unknown')
    --dry-run     Parse/validate only; do not write
    --no-commit   Write file but skip git commit

Output: one JSON object on stdout. Exit 1 on error/invalid_format.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ingest_common import (
    add_ingest_cli_flags,
    find_recipe_in_ldjson,
    ingest_kwargs_from_args,
    ldjson_from_html,
    parse_title_author_from_plaintext,
    process_recipemd,
    report_line,
    write_result,
)

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
if str(SITE_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_DIR))
from recipe_format import metadata_from_schema  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Recipe markdown file, HTML file (with --from-html), or - for stdin",
    )
    parser.add_argument("--file", help="Alias for input path")
    parser.add_argument(
        "--from-html",
        action="store_true",
        help="Treat input as HTML; extract schema.org Recipe ld+json",
    )
    parser.add_argument("--title", help="Override recipe title")
    parser.add_argument("--source", help="Source URL or attribution (e.g. cookbook, p. 42)")
    parser.add_argument("--slug", help="Override output slug")
    parser.add_argument("--added-by", default=os.environ.get("RECIPE_RUNNER_ADDED_BY", "unknown"), help="added_by frontmatter value")
    parser.add_argument("--author", help="Author name (overrides JSON-LD when using --from-html)")
    parser.add_argument("--recommended-by", help="recommended_by frontmatter")
    parser.add_argument("--yield", dest="yield_override", help="Override yield")
    parser.add_argument(
        "--keep-description",
        action="store_true",
        help="Keep description in frontmatter (default: omit on ingest)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    add_ingest_cli_flags(parser)
    args = parser.parse_args()

    path_arg = args.file or args.input
    if not path_arg:
        parser.error("provide a file path or - for stdin")

    if path_arg == "-":
        raw = sys.stdin.read()
        label = "stdin"
    else:
        p = Path(path_arg)
        if not p.is_file():
            parser.error(f"not a file: {path_arg}")
        raw = p.read_text(encoding="utf-8")
        label = str(p)

    source_url = ""
    source_label = args.source or ""
    if args.source and args.source.startswith(("http://", "https://")):
        source_url = args.source
        source_label = ""

    schema_meta: dict = {}
    if args.from_html:
        recipe = find_recipe_in_ldjson(raw)
        if recipe:
            schema_meta = metadata_from_schema(
                recipe, ingredient_count=len(recipe.get("recipeIngredient") or [])
            )
        md, err = ldjson_from_html(raw)
        if not md:
            out = {
                "status": "error",
                "input": label,
                "error": err or "ld+json extraction failed",
            }
            print(json.dumps(out))
            sys.exit(1)
    else:
        md = raw
        parsed_md, parsed_title, parsed_author = parse_title_author_from_plaintext(md)
        if parsed_title:
            md = parsed_md
            if not args.title:
                args.title = parsed_title
            if not args.author and parsed_author:
                args.author = parsed_author

    r = process_recipemd(
        md,
        source_url=source_url,
        source_label=source_label,
        added_by=args.added_by,
        slug_override=args.slug,
        title_override=args.title,
        schema_metadata=schema_meta or None,
        **ingest_kwargs_from_args(args),
    )
    r["input"] = label

    if r["status"] == "success" and not args.dry_run:
        write_result(r, dry_run=False, no_commit=args.no_commit)

    print(json.dumps(report_line(r)))

    if r["status"] in ("error", "invalid_format"):
        sys.exit(1)
    if r["status"] == "exists":
        sys.exit(1)


if __name__ == "__main__":
    main()
