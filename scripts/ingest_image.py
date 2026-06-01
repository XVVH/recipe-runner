#!/usr/bin/env python3
"""
ingest_image.py -- Ingest cookbook / photo recipes into a Recipe Runner collection.

Vision extraction runs in Hermes (vision_analyze); this script converts structured JSON
or pre-written RecipeMD into canonical recipes/*.md.

Workflow (Hermes agent):
  1. vision_analyze(image, question=<see references/vision-extract-prompt.md>)
  2. Save agent output as JSON (schema below) to /tmp/recipe-extract.json
  3. python3 scripts/ingest_image.py --json /tmp/recipe-extract.json [--source "Cookbook, p. 42"]

Usage:
    python3 scripts/ingest_image.py --json /tmp/recipe-extract.json
    python3 scripts/ingest_image.py --json front.json back.json --source "Handwritten card"
    python3 scripts/ingest_image.py --json /tmp/recipe-extract.json --source "Joy of Cooking, p. 210"
    python3 scripts/ingest_image.py --markdown /tmp/recipe.md   # already RecipeMD from vision
    python3 scripts/ingest_image.py --dry-run --json extract.json

JSON schema (minimum):
    {
      "title": "Recipe Name",
      "yield": "4 servings",
      "tags": ["Dinner", "Chicken"],
      "ingredients": ["2 cups flour", "1 tsp salt"],
      "instructions": ["Step one.", "Step two."],
      "notes": ["Optional note bullets"]
    }

    ingredients / instructions may be dicts for grouped sections:
      "ingredients": {"Salad": ["2 cups kale"], "Dressing": ["1 egg yolk"]}
      "instructions": {"Prep": ["Wash kale."], "Serve": ["Toss and serve."]}

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
    ingest_kwargs_from_args,
    merge_recipe_json,
    process_recipemd,
    report_line,
    structured_to_recipemd,
    write_result,
)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--json",
        metavar="FILE",
        nargs="+",
        help="Structured recipe JSON from vision (pass multiple files to merge)",
    )
    group.add_argument(
        "--markdown",
        metavar="FILE",
        help="RecipeMD markdown file (if vision returned markdown directly)",
    )
    parser.add_argument(
        "--source",
        help='Attribution: cookbook name + page, or URL (maps to frontmatter source:)',
    )
    parser.add_argument("--title", help="Override title")
    parser.add_argument("--slug", help="Override output slug")
    parser.add_argument("--added-by", default=os.environ.get("RECIPE_RUNNER_ADDED_BY", "unknown"), help="added_by frontmatter value")
    parser.add_argument("--author", help="Author name (overrides vision JSON author field)")
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

    source_url = ""
    source_label = args.source or ""
    if args.source and args.source.startswith(("http://", "https://")):
        source_url = args.source
        source_label = ""

    schema_meta: dict = {}
    try:
        if args.json:
            paths = [Path(p) for p in args.json]
            parts = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
            data = merge_recipe_json(parts) if len(parts) > 1 else parts[0]
            if data.get("author"):
                schema_meta["author"] = str(data["author"]).strip()
            if data.get("recommended_by"):
                schema_meta["recommended_by"] = str(data["recommended_by"]).strip()
            tags = data.get("tags")
            if tags:
                if isinstance(tags, str):
                    schema_meta["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
                else:
                    schema_meta["tags"] = [str(t).strip() for t in tags if str(t).strip()]
            y = data.get("yield") or data.get("servings")
            if y:
                schema_meta["yield"] = str(y).strip()
            md = structured_to_recipemd(data)
            label = ", ".join(str(p) for p in paths)
        else:
            path = Path(args.markdown)
            md = path.read_text(encoding="utf-8")
            label = str(path)
    except json.JSONDecodeError as e:
        out = {"status": "error", "error": f"invalid JSON: {e}"}
        print(json.dumps(out))
        sys.exit(1)
    except ValueError as e:
        out = {"status": "error", "error": str(e)}
        print(json.dumps(out))
        sys.exit(1)
    except OSError as e:
        out = {"status": "error", "error": str(e)}
        print(json.dumps(out))
        sys.exit(1)

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

    if r["status"] in ("error", "invalid_format", "exists"):
        sys.exit(1)


if __name__ == "__main__":
    main()
