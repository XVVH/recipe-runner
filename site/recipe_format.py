"""
Canonical recipe markdown format: validate + canonicalize.

Used by site/build.py (fail build on errors) and scripts/ingest_url.py (fail write on errors).
See recipes/_template.md for the author-facing contract.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import NamedTuple

import frontmatter
import yaml

# Ingredient line: - *qty* name  or  - name
INGR_RE = re.compile(r"^-\s+(?:\*([^*]*)\*)?\s*(.*)")

H1_RE = re.compile(r"^#\s+.+$", re.MULTILINE)
HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
SOURCE_TRAIL_RE = re.compile(r"^\*Source:\s*.+\*\s*$", re.MULTILINE)

REQUIRED_FM_STRICT = ("title", "date")
REQUIRED_FM_BUILD = ("title", "date")

FM_KEY_ORDER = (
    "title",
    "date",
    "author",
    "source",
    "recommended_by",
    "added_by",
    "favorite",
    "yield",
    "tags",
    "description",
    "notes",
)

SUSPICIOUS_YIELD_RE = re.compile(
    r"^(\d+)\s*(serving|servings|portion|portions)\b",
    re.IGNORECASE,
)


class ValidationIssue(NamedTuple):
    rule: str
    message: str
    level: str  # "error" | "warning"


def _load_migrate():
    import importlib.util

    scripts = Path(__file__).resolve().parent.parent / "scripts"
    spec = importlib.util.spec_from_file_location(
        "migrate_to_frontmatter",
        scripts / "migrate_to_frontmatter.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def block_looks_like_ingredients(text: str) -> bool:
    """True when a body section is an ingredient list, not prose."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("##"):
            continue
        if INGR_RE.match(line):
            return True
        return False
    return False


def split_body_sections(body: str) -> tuple[str, str, str, str]:
    """
    Return (description_block, ingredient_block, instruction_block, notes_block).
    description_block is non-empty only for legacy recipes with prose before ingredients.
    """
    body = body.strip()
    if body.startswith("---"):
        body = body.lstrip("-").lstrip()

    parts = re.split(r"\n---\n", body)
    has_description = bool(parts[0].strip()) and not block_looks_like_ingredients(parts[0])

    if has_description:
        return (
            parts[0].strip() if len(parts) > 0 else "",
            parts[1].strip() if len(parts) > 1 else "",
            parts[2].strip() if len(parts) > 2 else "",
            parts[3].strip() if len(parts) > 3 else "",
        )
    return (
        "",
        parts[0].strip() if len(parts) > 0 else "",
        parts[1].strip() if len(parts) > 1 else "",
        parts[2].strip() if len(parts) > 2 else "",
    )


def _strip_body_artifacts(body: str) -> str:
    """Remove H1, trailing source lines, and leading legacy separator."""
    body = H1_RE.sub("", body)
    body = SOURCE_TRAIL_RE.sub("", body)
    body = body.strip()
    if body.startswith("---"):
        body = body.lstrip("-").lstrip()
    return body.strip()


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
    """Pull Do ahead / Editor's note lines out of instruction steps."""
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


def _instruction_steps_from_block(instr_block: str) -> list[str]:
    """Split instruction markdown into steps (blank-line separated paragraphs)."""
    steps: list[str] = []
    for para in re.split(r"\n\s*\n", instr_block.strip()):
        para = para.strip()
        if not para:
            continue
        if para.startswith("##"):
            steps.append(para)
        else:
            steps.append(para)
    return steps


def _rebuild_instruction_block(steps: list[str]) -> str:
    return "\n\n".join(s for s in steps if s.strip())


def _notes_to_bullets(notes_block: str) -> str:
    if not notes_block.strip():
        return ""
    lines = []
    for para in re.split(r"\n\s*\n", notes_block.strip()):
        para = para.strip()
        if not para:
            continue
        for line in para.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("- "):
                lines.append(line)
            else:
                lines.append(f"- {line}")
    return "\n".join(lines)


def _is_empty_fm_value(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, (list, tuple)) and len(val) == 0:
        return True
    return False


def _prune_frontmatter(fm: dict) -> dict:
    """Drop null/empty keys (matches hand-edited golden recipes)."""
    return {k: v for k, v in fm.items() if not _is_empty_fm_value(v)}


def _author_name_from_schema(author_field) -> str | None:
    if author_field is None:
        return None
    if isinstance(author_field, dict):
        name = (author_field.get("name") or "").strip()
        return name or None
    if isinstance(author_field, list):
        for item in author_field:
            name = _author_name_from_schema(item)
            if name:
                return name
        return None
    if isinstance(author_field, str):
        s = author_field.strip()
        return s or None
    return None


def _tags_from_schema(recipe: dict) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []

    def add(tag: str) -> None:
        tag = tag.strip()
        if not tag or tag.lower() in seen:
            return
        seen.add(tag.lower())
        tags.append(tag)

    for key in ("recipeCategory", "recipeCuisine"):
        val = recipe.get(key)
        if isinstance(val, list):
            for item in val:
                add(str(item))
        elif val:
            add(str(val))

    keywords = recipe.get("keywords") or ""
    if isinstance(keywords, list):
        for item in keywords:
            add(str(item))
    elif keywords:
        for part in re.split(r"[,;]", str(keywords)):
            add(part)

    return tags


def _yield_from_schema(recipe: dict) -> str | None:
    yield_val = recipe.get("recipeYield") or recipe.get("recipeServings") or ""
    if isinstance(yield_val, list):
        yield_val = yield_val[0] if yield_val else ""
    s = str(yield_val).strip()
    return s or None


def _count_ingredients_in_md(md: str) -> int:
    n = 0
    for line in md.splitlines():
        if INGR_RE.match(line.strip()):
            n += 1
    return n


def yield_looks_suspicious(yield_str: str | None, *, ingredient_count: int = 0) -> bool:
    """True when scraper yield is likely wrong (e.g. 1 serving on a large recipe)."""
    if not yield_str:
        return False
    m = SUSPICIOUS_YIELD_RE.match(yield_str.strip())
    if not m:
        return False
    servings = int(m.group(1))
    return servings == 1 and ingredient_count >= 5


def metadata_from_schema(recipe: dict, *, ingredient_count: int = 0) -> dict:
    """
    Pull author, tags, yield, recommended_by from schema.org Recipe JSON-LD.
    Omits yield when it looks like a bad scrape.
    """
    meta: dict = {}
    author = _author_name_from_schema(recipe.get("author"))
    if author:
        meta["author"] = author

    tags = _tags_from_schema(recipe)
    if tags:
        meta["tags"] = tags

    y = _yield_from_schema(recipe)
    if y and not yield_looks_suspicious(y, ingredient_count=ingredient_count):
        meta["yield"] = y

    return meta


def parse_favorite_value(val) -> str:
    """Normalize favorite to yes/no strings for frontmatter."""
    if val is True or val in ("yes", "true", "True", 1):
        return "yes"
    return "no"


def _serialize_frontmatter(fm: dict) -> str:
    fm = _prune_frontmatter(fm)
    lines: list[str] = []
    for key in FM_KEY_ORDER:
        if key not in fm:
            continue
        val = fm[key]
        if key == "favorite":
            fav = parse_favorite_value(val)
            lines.append(f"favorite: {fav}")
        elif key == "tags":
            tag_list = val if isinstance(val, list) else [val]
            if len(tag_list) == 1:
                lines.append("tags:")
                lines.append(f"  - {tag_list[0]}")
            else:
                lines.append("tags:")
                for tag in tag_list:
                    lines.append(f"  - {tag}")
        elif key in ("date", "title", "author", "source", "recommended_by", "added_by", "yield"):
            lines.append(f"{key}: {val}")
        elif key == "description":
            dumped = yaml.dump({key: val}, allow_unicode=True, default_flow_style=False).strip()
            lines.append(dumped)
        elif key == "notes":
            dumped = yaml.dump({key: val}, allow_unicode=True, default_flow_style=False).strip()
            lines.append(dumped)
        else:
            dumped = yaml.dump({key: val}, allow_unicode=True, default_flow_style=False).strip()
            lines.append(dumped)
    for key, val in fm.items():
        if key in FM_KEY_ORDER:
            continue
        dumped = yaml.dump({key: val}, allow_unicode=True, default_flow_style=False).strip()
        lines.append(dumped)
    return "\n".join(lines)


HIGHLIGHT_SPAN_RE = re.compile(r"\[\[[^\]]+\]\]")
HIGHLIGHT_INNER_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Food phrases in steps that often appear only in instructions (not ingredient list).
_STEP_ONLY_FOOD_RE = re.compile(
    r"\b(?:to|with|add(?:ed)?|into|on|over|serve\s+with)\s+(?:the\s+)?"
    r"((?:angel\s+hair\s+)?[\w\s'-]{0,32}(?:pasta|noodles))\b",
    re.IGNORECASE,
)


def _food_text_cleanup(food: str) -> str:
    """Strip parentheticals for ingredient-name matching."""
    s = re.sub(r"\([^)]*\)", "", food)
    s = re.sub(r"\s+", " ", s).strip().strip(",").strip()
    return s


def _ingredient_variants(food: str) -> list[str]:
    """Search phrases derived from an ingredient line (longest match first)."""
    variants: list[str] = []
    cleaned = _food_text_cleanup(food)
    if not cleaned:
        return variants
    variants.append(cleaned)
    words = cleaned.split()
    if len(words) >= 2:
        tail2 = " ".join(words[-2:])
        if tail2.lower() != cleaned.lower():
            variants.append(tail2)
    if len(words) >= 3:
        tail1 = words[-1]
        if len(tail1) >= 4:
            variants.append(tail1)
    return variants


def ingredient_names_from_block(ing_block: str) -> list[str]:
    """Unique ingredient phrases for highlighting, longest first."""
    names: list[str] = []
    seen: set[str] = set()
    for line in ing_block.splitlines():
        line = line.strip()
        if not line or line.startswith("##"):
            continue
        m = INGR_RE.match(line)
        if m:
            food = (m.group(2) or "").strip()
        elif line.startswith("- "):
            food = line[2:].strip()
        else:
            continue
        if not food:
            continue
        for variant in _ingredient_variants(food):
            key = variant.lower()
            if key not in seen and len(key) >= 3:
                seen.add(key)
                names.append(variant)
    names.sort(key=len, reverse=True)
    return names


def _highlight_ranges(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in HIGHLIGHT_SPAN_RE.finditer(text)]


def _overlaps_ranges(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for a, b in ranges:
        if start < b and end > a:
            return True
    return False


def _find_phrase_match(text: str, phrase: str, start: int = 0) -> re.Match[str] | None:
    pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)
    return pattern.search(text, start)


def highlight_instruction_line(line: str, names: list[str]) -> str:
    """Wrap ingredient mentions in [[...]] on one instruction line."""
    if not line.strip() or line.strip().startswith("##"):
        return line
    occupied = _highlight_ranges(line)
    hits: list[tuple[int, int]] = []
    for name in names:
        pos = 0
        while True:
            m = _find_phrase_match(line, name, pos)
            if not m:
                break
            s, e = m.start(), m.end()
            if _overlaps_ranges(s, e, occupied):
                pos = e
                continue
            hits.append((s, e))
            occupied.append((s, e))
            pos = e
    for s, e in sorted(hits, key=lambda x: x[0], reverse=True):
        line = line[:s] + f"[[{line[s:e]}]]" + line[e:]
    return line


def apply_ingredient_highlights(content: str) -> str:
    """Add [[ingredient]] highlights to instruction steps from the ingredient list."""
    post = frontmatter.loads(content)
    body = _strip_body_artifacts(post.content)
    _desc, ing_block, instr_block, notes_block = split_body_sections(body)
    if not ing_block or not instr_block:
        return content

    names = ingredient_names_from_block(ing_block)
    if not names:
        return content

    new_instr = "\n".join(
        highlight_instruction_line(line, names) for line in instr_block.splitlines()
    )
    body_parts = [ing_block, new_instr]
    if notes_block:
        body_parts.append(notes_block)
    new_body = "\n\n---\n\n".join(body_parts)
    if new_body:
        new_body += "\n"
    fm = _serialize_frontmatter(dict(post.metadata))
    return f"---\n{fm}\n---\n\n{new_body}"


def _ingredient_name_set(ing_block: str) -> set[str]:
    return {n.lower() for n in ingredient_names_from_block(ing_block)}


def _phrase_in_ingredients(phrase: str, known: set[str]) -> bool:
    p = phrase.lower().strip()
    if not p:
        return True
    for k in known:
        if p in k or k in p:
            return True
    return False


def find_missing_ingredients(ing_block: str, instr_block: str) -> list[str]:
    """
    Ingredients referenced in steps but absent from the ingredient list.
    Used for warnings and --add-missing-ingredients.
    """
    known = _ingredient_name_set(ing_block)
    missing: list[str] = []
    seen: set[str] = set()

    # Only scan plain step text — existing [[highlights]] may be intentional aliases
    plain_instr = HIGHLIGHT_SPAN_RE.sub("", instr_block)
    for line in plain_instr.splitlines():
        if line.strip().startswith("##"):
            continue
        for m in _STEP_ONLY_FOOD_RE.finditer(line):
            phrase = m.group(1).strip()
            if phrase and not _phrase_in_ingredients(phrase, known):
                key = phrase.lower()
                if key not in seen:
                    seen.add(key)
                    missing.append(phrase)

    return missing


def append_missing_ingredients(content: str, missing: list[str]) -> str:
    """Append ingredient lines and a notes bullet for items found only in steps."""
    if not missing:
        return content
    post = frontmatter.loads(content)
    body = _strip_body_artifacts(post.content)
    _desc, ing_block, instr_block, notes_block = split_body_sections(body)
    for item in missing:
        line = item if item.startswith("- ") else f"- {item}"
        ing_block = f"{ing_block.rstrip()}\n{line}".strip()
    note = "- Added from instruction text: " + "; ".join(missing)
    notes_block = f"{notes_block.rstrip()}\n{note}".strip() if notes_block else note
    body_parts = [p for p in (ing_block, instr_block, notes_block) if p]
    new_body = "\n\n---\n\n".join(body_parts) + "\n"
    fm = _serialize_frontmatter(dict(post.metadata))
    return f"---\n{fm}\n---\n\n{new_body}"


def canonicalize(
    md: str,
    *,
    source_url: str = "",
    added_by: str = "unknown",
    ingest_date: str | None = None,
    author: str | None = None,
    recommended_by: str | None = None,
    yield_override: str | None = None,
    keep_description: bool = False,
    schema_metadata: dict | None = None,
) -> str:
    """
    Convert normalized RecipeMD markdown to canonical Recipe Runner format.

    Expects md after normalize() (ingredient markup, optional *Source: url* trailer).
    Uses migrate_to_frontmatter for metadata extraction, then rewrites body to
    ingredients-first shape matching recipes/_template.md.
    """
    migrate = _load_migrate().migrate

    today = ingest_date or date.today().isoformat()
    md_with_date = f"---\ndate: {today}\n---\n\n{md}"
    migrated, _extracted = migrate(md_with_date)

    post = frontmatter.loads(migrated)
    fm = dict(post.metadata)
    for key in ("author", "recommended_by", "description"):
        if key in fm and fm.get(key) is None:
            del fm[key]
    body = _strip_body_artifacts(post.content)

    # Prefer explicit source_url over extracted / body trailer
    if source_url:
        fm["source"] = source_url
    elif fm.get("source"):
        pass
    else:
        m = SOURCE_TRAIL_RE.search(md)
        if m:
            fm["source"] = m.group(0).strip("*").replace("Source:", "", 1).strip()

    fm["added_by"] = added_by
    fm["favorite"] = parse_favorite_value(fm.get("favorite", "no"))

    if not fm.get("date"):
        fm["date"] = today

    ing_count = _count_ingredients_in_md(md)

    if schema_metadata:
        if schema_metadata.get("author") and not author and not fm.get("author"):
            fm["author"] = schema_metadata["author"]
        if schema_metadata.get("recommended_by") and not recommended_by and not fm.get(
            "recommended_by"
        ):
            fm["recommended_by"] = schema_metadata["recommended_by"]
        schema_tags = schema_metadata.get("tags")
        if schema_tags and not fm.get("tags"):
            fm["tags"] = schema_tags
        schema_yield = schema_metadata.get("yield")
        if (
            schema_yield
            and not yield_override
            and not fm.get("yield")
            and not yield_looks_suspicious(schema_yield, ingredient_count=ing_count)
        ):
            fm["yield"] = schema_yield

    if author:
        fm["author"] = author.strip()
    if recommended_by:
        fm["recommended_by"] = recommended_by.strip()
    if yield_override:
        fm["yield"] = yield_override.strip()
    elif fm.get("yield") and yield_looks_suspicious(str(fm["yield"]), ingredient_count=ing_count):
        del fm["yield"]

    tags = fm.get("tags")
    if isinstance(tags, str):
        fm["tags"] = [t.strip() for t in re.split(r"[,;]", tags) if t.strip()]

    desc_block, ing_block, instr_block, notes_block = split_body_sections(body)

    if keep_description and not fm.get("description") and desc_block:
        fm["description"] = desc_block
    elif not keep_description and "description" in fm:
        del fm["description"]

    if fm.get("notes") and not notes_block:
        notes_block = str(fm["notes"]).strip()
        del fm["notes"]

    if instr_block:
        steps = _instruction_steps_from_block(instr_block)
        clean_steps, extracted_notes = extract_notes_from_steps(steps)
        instr_block = _rebuild_instruction_block(clean_steps)
        if extracted_notes:
            extra = _notes_to_bullets("\n\n".join(extracted_notes))
            notes_block = f"{notes_block}\n{extra}".strip() if notes_block else extra

    notes_block = _notes_to_bullets(notes_block)

    body_parts = []
    if ing_block:
        body_parts.append(ing_block)
    if instr_block:
        body_parts.append(instr_block)
    if notes_block:
        body_parts.append(notes_block)

    new_body = "\n\n---\n\n".join(body_parts)
    if new_body:
        new_body += "\n"

    return f"---\n{_serialize_frontmatter(fm)}\n---\n\n{new_body}"


def validate_recipe(
    content: str,
    *,
    strict: bool = False,
    path: str | None = None,
) -> list[ValidationIssue]:
    """
    Validate recipe markdown against the canonical contract.

    strict=False (build during legacy migration): errors block build; warnings print.
    strict=True (ingest output): warnings become errors.
    """
    issues: list[ValidationIssue] = []
    prefix = f"{path}: " if path else ""

    try:
        post = frontmatter.loads(content)
    except Exception as e:
        issues.append(ValidationIssue("parse", f"{prefix}invalid frontmatter: {e}", "error"))
        return issues

    fm = post.metadata
    body = _strip_body_artifacts(post.content)

    def add(rule: str, msg: str, level: str = "error"):
        if strict and level == "warning":
            level = "error"
        issues.append(ValidationIssue(rule, f"{prefix}{msg}", level))

    for key in REQUIRED_FM_BUILD:
        if not fm.get(key):
            add("frontmatter", f"missing required field '{key}'")

    if strict:
        for key in REQUIRED_FM_STRICT:
            if key not in fm or fm.get(key) in (None, "", []):
                add("frontmatter", f"missing required field '{key}' (strict ingest)")

    if H1_RE.search(body):
        add("body", "body must not contain H1 (# title); title belongs in frontmatter only")

    if re.search(r"^\*Source:\s*.+\*\s*$", body, re.MULTILINE):
        add("body", "body must not contain *Source: ...* line; use frontmatter source:")

    desc_block, ing_block, instr_block, notes_block = split_body_sections(body)

    if desc_block:
        add(
            "body",
            "body contains a description section; use frontmatter description: only",
            "warning",
        )

    if not ing_block:
        add("ingredients", "missing ingredient section")
    elif not block_looks_like_ingredients(ing_block):
        add("ingredients", "section 1 does not look like an ingredient list")

    if not instr_block:
        add("instructions", "missing instruction section")
    else:
        step_lines = [
            ln.strip()
            for ln in instr_block.splitlines()
            if ln.strip() and not ln.strip().startswith("##")
        ]
        if not step_lines:
            add("instructions", "instruction section has no steps")

    # Raw HTML in instructions/notes (allow [[...]] only)
    for section_name, block in (
        ("instructions", instr_block),
        ("notes", notes_block),
    ):
        if not block:
            continue
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("##"):
                continue
            # Remove [[highlight]] spans before HTML check
            without_highlights = re.sub(r"\[\[[^\]]+\]\]", "", stripped)
            if HTML_RE.search(without_highlights):
                add(
                    section_name,
                    f"raw HTML not allowed: {stripped[:60]}...",
                    "error" if strict else "warning",
                )
                break

    if strict and fm.get("added_by") is not None and not fm.get("added_by"):
        add("frontmatter", "missing added_by (required for ingested recipes)")

    tags = fm.get("tags")
    if strict and (not tags or (isinstance(tags, list) and len(tags) == 0)):
        add("frontmatter", "tags empty; add manually or improve ld+json extraction", "warning")

    if strict and not fm.get("yield"):
        add("frontmatter", "missing yield; add manually or pass --yield", "warning")

    if ing_block and instr_block:
        for phrase in find_missing_ingredients(ing_block, instr_block):
            add(
                "ingredients",
                f"step may reference '{phrase}' not in ingredient list",
                "warning",
            )

    return issues


def validate_recipe_file(path: Path, *, strict: bool = False) -> list[ValidationIssue]:
    return validate_recipe(path.read_text(encoding="utf-8"), strict=strict, path=str(path))


def format_issues(issues: list[ValidationIssue]) -> str:
    return "\n".join(f"  [{i.level}] {i.rule}: {i.message}" for i in issues)


def exit_if_errors(issues: list[ValidationIssue]) -> None:
    errors = [i for i in issues if i.level == "error"]
    if errors:
        import sys

        print("Recipe validation failed:", file=sys.stderr)
        print(format_issues(errors), file=sys.stderr)
        sys.exit(1)
