#!/usr/bin/env python3
"""
ingest_pdf.py -- Extract recipe text from PDF files (text layer first).

Does not write recipes/*.md. Output is plain text for an agent (or human) to
structure as RecipeMD, then run ingest_text.py.

For scanned PDFs with no text layer, render pages and use vision → ingest_image.py
(see docs/pdf-ingest.md).

Usage:
    python3 scripts/ingest_pdf.py recipe.pdf
    python3 scripts/ingest_pdf.py recipe.pdf --out /tmp/extracted.txt
    python3 scripts/ingest_pdf.py recipe.pdf --json   # metadata + paths only on stdout

Exit 1 if file missing or total extracted text below --min-chars (default 200).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None  # type: ignore


def fix_common_pdf_glyphs(text: str) -> str:
    """Repair frequent print-PDF ligature substitutions."""
    replacements = (
        ("!our", "flour"),
        ("!u", "flu"),
        ("!ake", "flake"),
        ("#ne", "fine"),
        ("#nishing", "finishing"),
        ("#tted", "fitted"),
        ("#rst", "first"),
        ('o"er', "offer"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def extract_pdf_text(path: Path, *, fix_glyphs: bool = True) -> tuple[str, list[dict]]:
    if pymupdf is None:
        raise RuntimeError("pymupdf not installed; pip install -r site/requirements.txt")
    doc = pymupdf.open(path)
    pages: list[dict] = []
    parts: list[str] = []
    for i in range(doc.page_count):
        raw = doc[i].get_text()
        if fix_glyphs:
            raw = fix_common_pdf_glyphs(raw)
        pages.append({"page": i + 1, "chars": len(raw)})
        parts.append(raw)
    return "\n\n".join(parts).strip(), pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("--out", type=Path, help="Write extracted text to this file")
    parser.add_argument("--no-fix-glyphs", action="store_true", help="Skip PDF glyph repairs")
    parser.add_argument(
        "--min-chars",
        type=int,
        default=200,
        help="Fail if total text shorter than this (likely scanned PDF)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary to stdout (text goes to --out or stderr preview)",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"not a file: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    try:
        text, pages = extract_pdf_text(args.pdf, fix_glyphs=not args.no_fix_glyphs)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    total = len(text)
    if total < args.min_chars:
        summary = {
            "status": "no_text_layer",
            "pdf": str(args.pdf.resolve()),
            "total_chars": total,
            "pages": pages,
            "hint": "Use vision fallback: render pages → vision JSON → ingest_image.py",
        }
        print(json.dumps(summary, indent=2))
        sys.exit(1)

    if args.out:
        args.out.write_text(text, encoding="utf-8")

    if args.json:
        out_path = str(args.out.resolve()) if args.out else None
        print(
            json.dumps(
                {
                    "status": "ok",
                    "pdf": str(args.pdf.resolve()),
                    "total_chars": total,
                    "pages": pages,
                    "text_path": out_path,
                },
                indent=2,
            )
        )
    elif args.out:
        print(f"Wrote {total} chars to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()