#!/usr/bin/env python3
"""
ingest_url.py -- Ingest recipe URLs into the family-recipes RecipeMD collection.

Fallback chain per URL:
  1. recipemd-extract <url>          -- direct extract
  2. Wayback Machine CDX lookup      -- for blocked scrapers (402/403/429)
  3. Mark as blocked                 -- needs bookmarklet or manual entry

On success: normalizes ingredients, writes to recipes/<slug>.md.

Usage:
    python3 scripts/ingest_url.py <url> [<url2> ...]
    python3 scripts/ingest_url.py --url-file urls.txt
    python3 scripts/ingest_url.py --url-file urls.txt --dry-run

Output:
    JSON report to stdout (one JSON object per line).
    Summary line at end.
    On success, also writes recipes/<slug>.md.

    Status values: success, blocked, exists, error, invalid_format
    (invalid_format = extracted OK but failed canonicalize/validate; file not written).
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).resolve().parent
REPO_ROOT   = SCRIPT_DIR.parent
RECIPES_DIR = REPO_ROOT / "recipes"
SITE_DIR    = REPO_ROOT / "site"
if str(SITE_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_DIR))

from ingest_common import (  # noqa: E402
    add_ingest_cli_flags,
    ingest_kwargs_from_args,
    ldjson_from_html,
    process_recipemd,
)

# recipemd-extract lives in the same venv as this script's Python interpreter
_VENV_BIN = Path(sys.executable).parent
RECIPEMD_EXTRACT = _VENV_BIN / "recipemd-extract"
if not RECIPEMD_EXTRACT.exists():
    # fallback: search PATH
    found = shutil.which("recipemd-extract")
    RECIPEMD_EXTRACT = Path(found) if found else RECIPEMD_EXTRACT

# ── slug helpers ───────────────────────────────────────────────────────────────

# ── frontmatter migration ──────────────────────────────────────────────────────

_migrate_mod = None


def _load_migrate():
    global _migrate_mod
    if _migrate_mod is None:
        spec = importlib.util.spec_from_file_location(
            "migrate_to_frontmatter",
            SCRIPT_DIR / "migrate_to_frontmatter.py",
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _migrate_mod = mod
    return _migrate_mod


def _apply_migration(md: str) -> str:
    """Convert RecipeMD inline-metadata format to YAML frontmatter format.

    Injects today's date so the result has date: set, then strips the H1
    from the body since the title is now captured in frontmatter.
    """
    mod = _load_migrate()
    # Prepend a minimal frontmatter block so migrate() picks up today's date
    today = datetime.date.today().isoformat()
    md_with_date = f"---\ndate: {today}\n---\n\n{md}"
    new_content, _ = mod.migrate(md_with_date)
    # Strip H1 from body -- title is now in frontmatter
    fm_match = re.match(r'^---\s*\n.*?\n---\s*\n', new_content, re.DOTALL)
    if fm_match:
        fm_block    = new_content[:fm_match.end()]
        body        = new_content[fm_match.end():]
        body        = re.sub(r'^\n?#[^\n]+\n\n?', '', body)
        new_content = fm_block + body
    return new_content

# ── extraction ─────────────────────────────────────────────────────────────────

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _run_recipemd_extract(url: str) -> tuple[str | None, str]:
    """Run recipemd-extract against a URL. Returns (markdown, error_message).
    Falls back to direct ld+json extraction for @graph-structured pages that
    recipemd-extract's recipe_schema plugin can't handle, or when the CLI is missing.
    """
    if not RECIPEMD_EXTRACT.exists():
        md, err = _extract_from_ldjson(url)
        if md:
            return md, ""
        return None, f"recipemd-extract not found at {RECIPEMD_EXTRACT}; ld+json: {err}"
    try:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tf:
            tmp_path = Path(tf.name)
        result = subprocess.run(
            [str(RECIPEMD_EXTRACT), url, str(tmp_path)],
            capture_output=True, text=True, timeout=30
        )
        if tmp_path.exists():
            output = tmp_path.read_text(encoding="utf-8").strip()
            tmp_path.unlink(missing_ok=True)
        else:
            output = ""
        stderr_out = result.stderr.strip()
        if "Could not extract recipe" in stderr_out or not output or not output.startswith("#"):
            # Try direct ld+json fallback before giving up
            md, _err = _extract_from_ldjson(url)
            if md:
                return md, ""
        if "Could not extract recipe" in stderr_out:
            return None, stderr_out or f"exit code {result.returncode}"
        if not output or not output.startswith("#"):
            return None, f"empty or malformed output (stderr: {stderr_out[:120]})" if stderr_out else "empty or malformed output"
        return output, ""
    except subprocess.TimeoutExpired:
        return None, "recipemd-extract timed out"
    except Exception as e:
        return None, str(e)


def _extract_from_ldjson(url: str) -> tuple[str | None, str]:
    """
    Direct ld+json extraction for pages with @graph-structured schema.org Recipe data.
    Handles the case where recipemd-extract's recipe_schema plugin fails on list-type
    @graph arrays (e.g. themediterraneandish.com).
    Returns (recipemd_markdown, error).
    """
    try:
        req = urllib.request.Request(url, headers=_BROWSER_HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, f"fetch failed: {e}"
    return ldjson_from_html(html)


def _wayback_lookup(url: str) -> str | None:
    """
    Query Wayback CDX API for the most recent successful snapshot.
    Returns the archived URL string, or None if not found.
    """
    cdx = (
        "http://web.archive.org/cdx/search/cdx"
        f"?url={url}&output=json&limit=1&fl=timestamp"
        "&filter=statuscode:200&from=20200101&sort=reverse"
    )
    try:
        req  = urllib.request.Request(cdx, headers=_BROWSER_HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        rows = json.loads(resp.read().decode())
        if len(rows) < 2:
            return None
        timestamp = rows[1][0]
        return f"https://web.archive.org/web/{timestamp}/{url}"
    except Exception:
        return None


def extract(url: str, **ingest_kw) -> dict:
    added_by = ingest_kw.pop("added_by", "unknown")
    """
    Full fallback chain. Returns a result dict:
      status: "success" | "blocked" | "exists" | "error"
      url, wayback_used, slug, title, output_path, error
    """
    result = {
        "url":          url,
        "status":       None,
        "title":        None,
        "slug":         None,
        "output_path":  None,
        "wayback_used": False,
        "wayback_url":  None,
        "error":        None,
    }

    # ── step 1: direct extract ─────────────────────────────────────────────
    md, err = _run_recipemd_extract(url)

    # ── step 2: wayback fallback ───────────────────────────────────────────
    if md is None:
        result["error"] = f"direct: {err}"
        wb_url = _wayback_lookup(url)
        if wb_url:
            result["wayback_url"] = wb_url
            md, wb_err = _run_recipemd_extract(wb_url)
            if md:
                result["wayback_used"] = True
            else:
                result["error"] += f" | wayback: {wb_err}"
        else:
            result["error"] = (result["error"] or "") + " | wayback: no snapshot found"

    if md is None:
        result["status"] = "blocked"
        return result

    # ── success path ───────────────────────────────────────────────────────
    processed = process_recipemd(md, source_url=url, added_by=added_by, **ingest_kw)
    result.update(
        {k: processed[k] for k in ("status", "title", "slug", "output_path", "error") if k in processed}
    )
    if processed.get("md"):
        result["md"] = processed["md"]
    return result

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="*", help="Recipe URLs to ingest")
    parser.add_argument("--url-file", help="File of URLs, one per line")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and normalize but do not write files or commit")
    parser.add_argument("--no-commit", action="store_true",
                        help="Write files but skip git commit")
    parser.add_argument("--author", help="Override author (else from JSON-LD when available)")
    parser.add_argument("--recommended-by", help="recommended_by frontmatter")
    parser.add_argument("--yield", dest="yield_override", help="Override yield (e.g. '4 servings')")
    parser.add_argument(
        "--keep-description",
        action="store_true",
        help="Keep description in frontmatter (default: omit on ingest)",
    )
    parser.add_argument(
        "--added-by",
        default=os.environ.get("RECIPE_RUNNER_ADDED_BY", "unknown"),
        help="added_by frontmatter value (default: $RECIPE_RUNNER_ADDED_BY or 'unknown')",
    )
    add_ingest_cli_flags(parser)
    args = parser.parse_args()

    ingest_kw = ingest_kwargs_from_args(args)
    ingest_kw["added_by"] = args.added_by

    urls = list(args.urls)
    if args.url_file:
        with open(args.url_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

    if not urls:
        parser.error("provide at least one URL or --url-file")

    counts = {"success": 0, "blocked": 0, "exists": 0, "error": 0, "invalid_format": 0}
    written = []

    for url in urls:
        print(f"[ingest] {url}", file=sys.stderr)
        r = extract(url, **ingest_kw)

        # write file
        if r["status"] == "success" and not args.dry_run:
            RECIPES_DIR.mkdir(parents=True, exist_ok=True)
            Path(r["output_path"]).write_text(r["md"], encoding="utf-8")
            written.append(r["output_path"])

        # strip md from report (large, not useful in the log)
        report = {k: v for k, v in r.items() if k != "md"}
        print(json.dumps(report))
        counts[r["status"]] = counts.get(r["status"], 0) + 1

        time.sleep(1)  # polite delay between requests

    # git commit
    if written and not args.dry_run and not args.no_commit:
        titles = [Path(p).stem for p in written]
        msg = f"Add: {', '.join(titles)}"
        subprocess.run(["git", "-C", str(REPO_ROOT), "add"] + written, check=True)
        subprocess.run(["git", "-C", str(REPO_ROOT), "commit", "-m", msg], check=True)
        print(json.dumps({"status": "committed", "files": written, "message": msg}))

    # summary
    print(json.dumps({"status": "summary", "counts": counts, "total": len(urls)}))

    # exit non-zero if anything was blocked, errored, or failed validation
    if counts.get("blocked", 0) + counts.get("error", 0) + counts.get("invalid_format", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
