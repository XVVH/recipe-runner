"""
Shared ingestion helpers for Recipe Runner.

Used by ingest_url.py, ingest_text.py, and ingest_image.py.
Pipeline: RecipeMD-ish markdown → normalize() → canonicalize() → validate(strict) → write.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RECIPES_DIR = REPO_ROOT / "recipes"
SITE_DIR = REPO_ROOT / "site"
if str(SITE_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_DIR))

from recipe_format import (  # noqa: E402
    append_missing_ingredients,
    apply_ingredient_highlights,
    canonicalize,
    find_missing_ingredients,
    format_issues,
    metadata_from_schema,
    split_body_sections,
    validate_recipe,
    _strip_body_artifacts,
)

COMMON_TYPOS: dict[str, str] = {
    "angle hair": "angel hair",
    "angle-hair": "angel-hair",
    "skippys": "Skippy's",
    "skippy s": "Skippy's",
}

# ── slug helpers ───────────────────────────────────────────────────────────────


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[''']", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def title_from_recipemd(md: str) -> str | None:
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def title_from_frontmatter(md: str) -> str | None:
    try:
        import frontmatter

        post = frontmatter.loads(md)
        t = post.metadata.get("title")
        return str(t).strip() if t else None
    except Exception:
        return None


def resolve_title(md: str, override: str | None = None) -> str | None:
    if override:
        return override.strip()
    return title_from_frontmatter(md) or title_from_recipemd(md)


def unique_slug(title: str, *, slug_override: str | None = None) -> str:
    base = slugify(slug_override or title)
    candidate = base
    i = 2
    while (RECIPES_DIR / f"{candidate}.md").exists():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


# ── ingredient normalization (same as ingest_url.py) ─────────────────────────

DECIMAL_TO_FRACTION = {
    "0.125": "1/8",
    "0.25": "1/4",
    "0.333": "1/3",
    "0.5": "1/2",
    "0.667": "2/3",
    "0.75": "3/4",
    ".125": "1/8",
    ".25": "1/4",
    ".333": "1/3",
    ".5": "1/2",
    ".667": "2/3",
    ".75": "3/4",
}

UNICODE_TO_FRACTION = {
    "½": "1/2",
    "¼": "1/4",
    "¾": "3/4",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
}

_UNICODE_PAT = re.compile("|".join(re.escape(k) for k in UNICODE_TO_FRACTION))

UNITS = {
    "cup",
    "cups",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "teaspoon",
    "teaspoons",
    "tsp",
    "pound",
    "pounds",
    "lb",
    "lbs",
    "ounce",
    "ounces",
    "oz",
    "gram",
    "grams",
    "g",
    "kilogram",
    "kilograms",
    "kg",
    "milliliter",
    "milliliters",
    "ml",
    "liter",
    "liters",
    "l",
    "quart",
    "quarts",
    "pint",
    "pints",
    "gallon",
    "gallons",
    "stick",
    "sticks",
    "bunch",
    "bunches",
    "clove",
    "cloves",
    "slice",
    "slices",
    "piece",
    "pieces",
    "can",
    "cans",
    "package",
    "packages",
    "pkg",
    "bag",
    "bags",
    "sprig",
    "sprigs",
    "leaf",
    "leaves",
    "pinch",
    "pinches",
    "dash",
    "dashes",
    "head",
    "heads",
    "bulb",
    "bulbs",
    "inch",
    "inches",
}

_NUMBER_PAT = (
    r"\d+\s+\d+\s*/\s*\d+"
    r"|[½¼¾⅓⅔⅛⅜⅝⅞]"
    r"|\d+\s*/\s*\d+"
    r"|\d+\.?\d*"
    r"|\.\d+"
)


def _normalize_fractions(text: str) -> str:
    def _replace(m: re.Match) -> str:
        return DECIMAL_TO_FRACTION.get(m.group(0)) or m.group(0)

    return re.sub(r"(?<![.\d])0?\.\d+", _replace, text)


def _parse_amount(line: str) -> str:
    if not line.startswith("- "):
        return line
    if re.match(r"- \*", line):
        return line
    body = line[2:].strip()
    num_match = re.match(_NUMBER_PAT, body)
    if not num_match:
        return line
    qty = num_match.group(0).strip()
    rest = body[num_match.end() :].lstrip()
    unit_match = re.match(r"^([A-Za-z]+\.?)(?=\s|,|$|\()", rest)
    if unit_match:
        unit_raw = unit_match.group(1)
        unit_lower = unit_raw.lower().rstrip(".")
        if unit_lower in UNITS or unit_raw.rstrip(".").lower() in UNITS:
            unit = unit_raw.rstrip(".")
            food = rest[unit_match.end() :].lstrip().lstrip(",").lstrip()
            amount = f"{qty} {unit}"
        else:
            amount = qty
            food = rest
    else:
        amount = qty
        food = rest
    if not food:
        return line
    return f"- *{amount}* {food}"


def apply_common_typos(text: str) -> str:
    """Fix frequent OCR / handwriting typos before canonicalize."""
    out = text
    for wrong, right in COMMON_TYPOS.items():
        out = re.sub(re.escape(wrong), right, out, flags=re.IGNORECASE)
    return out


def normalize(md: str, source_url: str = "") -> str:
    md = apply_common_typos(md)
    md = _UNICODE_PAT.sub(lambda m: UNICODE_TO_FRACTION[m.group(0)], md)
    _IMAGE_LINE = re.compile(r"^!\[.*?\]\(.*?\)\s*$")
    lines = md.splitlines()
    out = []
    for line in lines:
        if _IMAGE_LINE.match(line):
            continue
        if line.startswith("- "):
            line = _normalize_fractions(line)
        out.append(_parse_amount(line))
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).rstrip()
    if source_url:
        result += f"\n\n*Source: {source_url}*"
    return result + "\n"


# ── vision / structured JSON → RecipeMD ───────────────────────────────────────

NOTE_PREFIX = re.compile(
    r"^(Do\s+ahead|Make\s+ahead|Editor[''']?s?\s+note|Cook[''']?s?\s+note|"
    r"Food\s+stylist[''']?s?\s+note|Note|Notes|Tip|Tips)\s*:",
    re.IGNORECASE,
)
NOTE_SENTENCE = re.compile(
    r"\s+(Do\s+ahead|Make\s+ahead|Editor[''']?s?\s+note|Cook[''']?s?\s+note|"
    r"Food\s+stylist[''']?s?\s+note|Note|Notes|Tip|Tips)\s*:",
    re.IGNORECASE,
)


def extract_notes_from_steps(steps: list[str]) -> tuple[list[str], list[str]]:
    clean_steps: list[str] = []
    note_lines: list[str] = []
    for step in steps:
        if NOTE_PREFIX.match(step.strip()):
            note_lines.append(step.strip())
            continue
        m = NOTE_SENTENCE.search(step)
        if m:
            clean_steps.append(step[: m.start()].strip())
            note_lines.append(step[m.start() :].strip())
        else:
            clean_steps.append(step)
    return clean_steps, note_lines


def _ingredient_line(item: str) -> str:
    item = item.strip()
    if not item:
        return ""
    if item.startswith("- "):
        return item
    return f"- {item}"


def structured_to_recipemd(data: dict[str, Any]) -> str:
    """
    Convert vision-extraction JSON to RecipeMD for canonicalize().

    Expected keys:
      title (required), yield, tags (list or comma str), description,
      ingredients (list of str OR dict group -> list),
      instructions (list of str OR dict phase -> list),
      notes (list of str)
    """
    title = (data.get("title") or data.get("name") or "").strip()
    if not title:
        raise ValueError("structured recipe JSON missing title")

    lines: list[str] = [f"# {title}", ""]

    desc = (data.get("description") or "").strip()
    if desc:
        lines.extend([desc, ""])

    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,;]", tags) if t.strip()]
    if tags:
        lines.append(f"*{', '.join(tags)}*")
        lines.append("")

    yield_val = data.get("yield") or data.get("recipeYield") or data.get("servings") or ""
    if isinstance(yield_val, list):
        yield_val = yield_val[0] if yield_val else ""
    yield_val = str(yield_val).strip()
    if yield_val:
        lines.extend([f"**{yield_val}**", ""])

    lines.extend(["---", ""])

    ingredients = data.get("ingredients") or data.get("recipeIngredient") or []
    if isinstance(ingredients, dict):
        for group, items in ingredients.items():
            if group:
                lines.append(f"## {group}")
            for item in items or []:
                line = _ingredient_line(str(item))
                if line:
                    lines.append(line)
            lines.append("")
    else:
        for item in ingredients:
            line = _ingredient_line(str(item))
            if line:
                lines.append(line)
        lines.append("")

    lines.extend(["---", ""])

    instructions = data.get("instructions") or data.get("recipeInstructions") or []
    raw_steps: list[str] = []
    if isinstance(instructions, dict):
        for phase, steps in instructions.items():
            if phase:
                raw_steps.append(f"## {phase}")
            for step in steps or []:
                if isinstance(step, dict):
                    text = (step.get("text") or step.get("name") or "").strip()
                else:
                    text = str(step).strip()
                if text:
                    raw_steps.append(text)
    else:
        for step in instructions:
            if isinstance(step, dict):
                text = (step.get("text") or step.get("name") or "").strip()
            else:
                text = str(step).strip()
            if text:
                raw_steps.append(text)

    clean_steps, note_lines = extract_notes_from_steps(raw_steps)
    for step in clean_steps:
        lines.append(step)
        lines.append("")

    notes = data.get("notes") or []
    if isinstance(notes, dict):
        notes = [f"{k}: {v}" if k else str(v) for k, v in notes.items()]
    all_notes = list(notes) + note_lines
    if all_notes:
        lines.extend(["---", ""])
        for note in all_notes:
            note = str(note).strip()
            if not note:
                continue
            if note.startswith("- "):
                lines.append(note)
            else:
                lines.append(f"- {note}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def recipe_schema_to_recipemd(r: dict) -> str:
    """Convert schema.org Recipe dict to RecipeMD markdown."""
    lines: list[str] = []
    title = (r.get("name") or "Untitled Recipe").strip()
    lines.extend([f"# {title}", ""])

    desc = (r.get("description") or "").strip()
    if desc:
        lines.extend([desc, ""])

    keywords = r.get("keywords") or ""
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)
    keywords = str(keywords).strip().strip(",").strip()
    if keywords:
        lines.extend([f"*{keywords}*", ""])

    yield_val = r.get("recipeYield") or r.get("recipeServings") or ""
    if isinstance(yield_val, list):
        yield_val = yield_val[0] if yield_val else ""
    yield_val = str(yield_val).strip()
    if yield_val:
        lines.extend([f"**{yield_val}**", ""])

    lines.extend(["---", ""])
    for ing in r.get("recipeIngredient") or []:
        ing = str(ing).strip()
        if ing:
            lines.append(f"- {ing}")
    lines.append("")
    lines.extend(["---", ""])

    raw_steps: list[str] = []
    for step in r.get("recipeInstructions") or []:
        if isinstance(step, dict):
            text = (step.get("text") or step.get("name") or "").strip()
        else:
            text = str(step).strip()
        if text:
            raw_steps.append(text)

    clean_steps, note_lines = extract_notes_from_steps(raw_steps)
    for step in clean_steps:
        lines.append(step)
        lines.append("")

    if note_lines:
        lines.extend(["---", ""])
        for note in note_lines:
            lines.append(note)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def find_recipe_in_ldjson(html: str) -> dict | None:
    """Return first schema.org Recipe object from HTML ld+json blocks."""
    pat = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL,
    )
    for m in pat.findall(html):
        try:
            data = json.loads(m.strip())
            candidates: list = []
            if isinstance(data, dict):
                if data.get("@type") == "Recipe":
                    candidates = [data]
                elif "@graph" in data:
                    candidates = [
                        x
                        for x in data["@graph"]
                        if isinstance(x, dict) and x.get("@type") == "Recipe"
                    ]
            elif isinstance(data, list):
                candidates = [
                    x for x in data if isinstance(x, dict) and x.get("@type") == "Recipe"
                ]
            if candidates:
                return candidates[0]
        except Exception:
            continue
    return None


def ldjson_from_html(html: str) -> tuple[str | None, str]:
    """Extract first schema.org Recipe from HTML ld+json blocks."""
    recipe = find_recipe_in_ldjson(html)
    if recipe:
        return recipe_schema_to_recipemd(recipe), ""
    return None, "no schema.org Recipe found in ld+json"


def fetch_url_html(url: str, *, timeout: int = 15) -> tuple[str | None, str]:
    try:
        req = urllib.request.Request(url, headers=_BROWSER_HEADERS)
        html = urllib.request.urlopen(req, timeout=timeout).read().decode(
            "utf-8", errors="replace"
        )
        return html, ""
    except Exception as e:
        return None, str(e)


def fetch_recipe_schema(url: str) -> tuple[dict | None, str]:
    """Fetch URL and return schema.org Recipe dict from ld+json, if present."""
    html, err = fetch_url_html(url)
    if not html:
        return None, err or "fetch failed"
    recipe = find_recipe_in_ldjson(html)
    if recipe:
        return recipe, ""
    return None, "no schema.org Recipe in ld+json"


def parse_vision_json(text: str) -> dict[str, Any]:
    """
    Parse JSON from a vision model response, tolerating markdown fences and preamble.
    """
    raw = text.strip()
    if not raw:
        raise ValueError("empty vision JSON")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid vision JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("vision JSON must be an object")
    return data


def _extraction_page_index(part: dict[str, Any], fallback: int) -> int:
    idx = part.get("page_index")
    if idx is None:
        return fallback
    try:
        return int(idx)
    except (TypeError, ValueError):
        return fallback


def _extraction_page_role(part: dict[str, Any]) -> str:
    role = str(part.get("page_role") or "").strip().lower()
    if role in {"primary", "continuation", "index_front", "index_back"}:
        return role
    return ""


def sort_extraction_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order extractions by page_index when present; preserve input order as tiebreaker."""
    return sorted(
        enumerate(parts),
        key=lambda pair: (_extraction_page_index(pair[1], pair[0]), pair[0]),
    )


def strip_extraction_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """Remove vision workflow keys before RecipeMD conversion."""
    return {k: v for k, v in data.items() if k not in {"page_index", "page_role"}}


def merge_recipe_json(
    parts: list[dict[str, Any]],
    *,
    recipe_type: str | None = None,
) -> dict[str, Any]:
    """
    Merge multiple vision-extraction JSON blobs (cookbook pages, index card front/back).

    Optional per-part metadata (stripped before write):
      page_index: int — merge order (default: argument order)
      page_role: primary | continuation | index_front | index_back

    Ingredients dedupe exact strings; instructions append in page order without dedupe
    so repeated steps (e.g. "stir") on continuation pages are preserved.
    """
    if not parts:
        raise ValueError("no recipe JSON to merge")
    ordered = [p for _, p in sort_extraction_parts(parts)]
    if len(ordered) == 1:
        return strip_extraction_metadata(ordered[0])

    def _as_list(val) -> list:
        if val is None:
            return []
        if isinstance(val, list):
            return list(val)
        return [val]

    def _dedupe_append_lists(a, b) -> list:
        out = list(_as_list(a))
        for item in _as_list(b):
            if item not in out:
                out.append(item)
        return out

    def _append_lists(a, b) -> list:
        return list(_as_list(a)) + list(_as_list(b))

    def _merge_dict_of_lists(a, b, *, dedupe: bool) -> dict:
        merge_fn = _dedupe_append_lists if dedupe else _append_lists
        out: dict = {}
        if isinstance(a, dict):
            out.update({k: list(v or []) for k, v in a.items()})
        elif isinstance(a, list):
            out["Ingredients"] = list(a)
        if isinstance(b, dict):
            for k, v in b.items():
                out[k] = merge_fn(out.get(k, []), v or [])
        elif isinstance(b, list):
            out["Ingredients"] = merge_fn(out.get("Ingredients", []), b)
        return out

    def _title_from_part(part: dict[str, Any]) -> str:
        return str(part.get("title") or part.get("name") or "").strip()

    def _is_continuation(part: dict[str, Any]) -> bool:
        role = _extraction_page_role(part)
        if role in {"continuation", "index_back"}:
            return True
        if recipe_type == "cookbook" and role == "":
            idx = part.get("page_index")
            if idx is not None:
                try:
                    return int(idx) > 1
                except (TypeError, ValueError):
                    pass
        return False

    merged: dict[str, Any] = {}
    for i, part in enumerate(ordered):
        role = _extraction_page_role(part)
        title = _title_from_part(part)
        if title and not _is_continuation(part):
            if not merged.get("title"):
                merged["title"] = title
        elif title and not merged.get("title") and role in {"primary", "index_front", ""}:
            merged["title"] = title

        for key in ("yield", "author", "description", "recommended_by", "servings"):
            if not merged.get(key) and part.get(key):
                merged[key] = part[key]

        merged_tags = _as_list(merged.get("tags"))
        for tag in _as_list(part.get("tags")):
            if tag not in merged_tags:
                merged_tags.append(tag)
        if merged_tags:
            merged["tags"] = merged_tags

        for key in ("ingredients", "recipeIngredient"):
            a, b = merged.get(key), part.get(key)
            if isinstance(a, dict) or isinstance(b, dict):
                merged[key] = _merge_dict_of_lists(a, b, dedupe=True)
            else:
                merged[key] = _dedupe_append_lists(a, b)

        for key in ("instructions", "recipeInstructions"):
            a, b = merged.get(key), part.get(key)
            if isinstance(a, dict) or isinstance(b, dict):
                merged[key] = _merge_dict_of_lists(a, b, dedupe=False)
            else:
                merged[key] = _append_lists(a, b)

        merged["notes"] = _dedupe_append_lists(merged.get("notes"), part.get("notes"))

    if not merged.get("title"):
        for part in ordered:
            title = _title_from_part(part)
            if title:
                merged["title"] = title
                break

    return strip_extraction_metadata(merged)


def load_recipe_json_file(path: Path) -> dict[str, Any]:
    """Load structured recipe JSON from disk, parsing vision responses if needed."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = parse_vision_json(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def collect_json_paths(
    json_files: list[Path] | None = None,
    json_dir: Path | None = None,
) -> list[Path]:
    """Resolve ordered JSON paths from explicit files or a directory."""
    if json_files:
        return list(json_files)
    if json_dir is None:
        raise ValueError("no JSON inputs")
    if not json_dir.is_dir():
        raise ValueError(f"not a directory: {json_dir}")
    paths = sorted(json_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"no *.json files in {json_dir}")
    return paths


AUTHOR_FIRST_LINE_RE = re.compile(
    r"^(.+?)\s*,\s*by\s+(.+?)\s*$",
    re.IGNORECASE,
)


def parse_title_author_from_plaintext(raw: str) -> tuple[str, str | None, str | None]:
    """
    If the first non-empty line is 'Title, by Author', return (remaining_text, title, author).
    Otherwise (raw, None, None).
    """
    lines = raw.splitlines()
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return raw, None, None
    first = lines[idx].strip()
    if first.startswith("#") or first.startswith("---"):
        return raw, None, None
    m = AUTHOR_FIRST_LINE_RE.match(first)
    if not m:
        return raw, None, None
    title, author = m.group(1).strip(), m.group(2).strip()
    rest = "\n".join(lines[:idx] + lines[idx + 1 :])
    return rest.strip() + ("\n" if rest.endswith("\n") else ""), title, author


def schema_metadata_for_url(url: str) -> dict:
    """Author, tags, yield from page JSON-LD (for canonicalize)."""
    recipe, _ = fetch_recipe_schema(url)
    if not recipe:
        return {}
    n_ing = len(recipe.get("recipeIngredient") or [])
    return metadata_from_schema(recipe, ingredient_count=n_ing)


# ── canonical pipeline ────────────────────────────────────────────────────────


def add_ingest_cli_flags(parser) -> None:
    """Shared flags for ingest_url / ingest_text / ingest_image."""
    parser.add_argument(
        "--highlight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Wrap ingredient names in [[...]] in steps (default: on)",
    )
    parser.add_argument(
        "--add-missing-ingredients",
        action="store_true",
        help="Append ingredients referenced in steps but missing from the list",
    )


def ingest_kwargs_from_args(args) -> dict:
    return {
        "author": getattr(args, "author", None),
        "recommended_by": getattr(args, "recommended_by", None),
        "yield_override": getattr(args, "yield_override", None),
        "keep_description": getattr(args, "keep_description", False),
        "highlight": getattr(args, "highlight", True),
        "add_missing_ingredients": getattr(args, "add_missing_ingredients", False),
    }


def process_recipemd(
    md: str,
    *,
    source_url: str = "",
    source_label: str = "",
    added_by: str = "unknown",
    slug_override: str | None = None,
    title_override: str | None = None,
    author: str | None = None,
    recommended_by: str | None = None,
    yield_override: str | None = None,
    keep_description: bool = False,
    schema_metadata: dict | None = None,
    highlight: bool = True,
    add_missing_ingredients: bool = False,
) -> dict:
    """
    Normalize → canonicalize → strict validate.
    Returns result dict with status: success | exists | error | invalid_format
    """
    result: dict = {
        "status": None,
        "title": None,
        "slug": None,
        "output_path": None,
        "error": None,
        "source": source_label or source_url or None,
    }

    title = resolve_title(md, title_override)
    if not title:
        result["status"] = "error"
        result["error"] = "could not determine title (use --title or RecipeMD # heading)"
        return result

    slug = unique_slug(title, slug_override=slug_override)
    out_path = RECIPES_DIR / f"{slug}.md"

    if out_path.exists():
        result.update(
            {
                "status": "exists",
                "title": title,
                "slug": slug,
                "output_path": str(out_path),
            }
        )
        return result

    src = source_url or source_label
    normalized = normalize(md, source_url=source_url)
    meta = dict(schema_metadata or {})
    if source_url and not meta:
        meta = schema_metadata_for_url(source_url)
    canonical = canonicalize(
        normalized,
        source_url=src,
        added_by=added_by,
        author=author,
        recommended_by=recommended_by,
        yield_override=yield_override,
        keep_description=keep_description,
        schema_metadata=meta or None,
    )
    if highlight:
        canonical = apply_ingredient_highlights(canonical)
    if add_missing_ingredients:
        import frontmatter

        post = frontmatter.loads(canonical)
        _d, ing_block, instr_block, _n = split_body_sections(
            _strip_body_artifacts(post.content)
        )
        missing = find_missing_ingredients(ing_block, instr_block)
        if missing:
            canonical = append_missing_ingredients(canonical, missing)
    issues = validate_recipe(canonical, strict=True)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        result["status"] = "invalid_format"
        result["error"] = format_issues(errors)
        return result

    result.update(
        {
            "status": "success",
            "title": title,
            "slug": slug,
            "output_path": str(out_path),
            "md": canonical,
        }
    )
    return result


def write_result(
    result: dict,
    *,
    dry_run: bool = False,
    no_commit: bool = False,
) -> str | None:
    """Write successful result to recipes/. Returns output_path or None."""
    if result.get("status") != "success" or dry_run:
        return None
    path = result["output_path"]
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(result["md"], encoding="utf-8")
    if not no_commit:
        msg = f"Add: {Path(path).stem}"
        subprocess.run(["git", "-C", str(REPO_ROOT), "add", path], check=True)
        subprocess.run(["git", "-C", str(REPO_ROOT), "commit", "-m", msg], check=True)
    return path


def report_line(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "md"}
