#!/usr/bin/env python3
"""
Migrate RecipeMD inline metadata to YAML frontmatter.

Extracts from body into frontmatter:
  - title     (from H1)
  - tags      (from *tag, tag* italic paragraph)
  - yield     (from **yield** bold paragraph)
  - source    (from *Source: url* trailing line)
  - description (first non-metadata paragraph before first ---)

Preserves existing frontmatter fields (date etc).
Strips extracted inline metadata from body, leaving clean prose + ingredients + instructions.

Fields NOT extracted (require manual fill):
  - author
  - recommended_by

Usage:
  python3 scripts/migrate_to_frontmatter.py [--dry-run] [file ...]
  (no files = all recipes/*.md)
"""
import re
import sys
import yaml
from pathlib import Path

RECIPES_DIR = Path(__file__).parent.parent / "recipes"

FRONTMATTER_RE  = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
H1_RE           = re.compile(r'^#\s+(.+)$', re.MULTILINE)
TAGS_RE         = re.compile(r'^\*([^*\n]+)\*\s*$', re.MULTILINE)
YIELD_RE        = re.compile(r'^\*\*([^*\n]+)\*\*\s*$', re.MULTILINE)
SOURCE_RE       = re.compile(r'^\*Source:\s*(.+?)\*\s*$', re.MULTILINE)
HR_RE           = re.compile(r'^---\s*$', re.MULTILINE)


def parse_existing_frontmatter(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_without_frontmatter)."""
    m = FRONTMATTER_RE.match(content)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        return fm, content[m.end():]
    return {}, content


def extract_description(body_before_first_hr: str) -> str:
    """
    Extract description: first paragraph that is NOT the H1, NOT a tags line,
    NOT a yield line, NOT a source line, and NOT blank.
    """
    lines = body_before_first_hr.splitlines()
    paragraphs = []
    current = []
    for line in lines:
        if line.strip() == "":
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current).strip())

    for para in paragraphs:
        if H1_RE.match(para):
            continue
        if TAGS_RE.match(para):
            continue
        if YIELD_RE.match(para):
            continue
        if SOURCE_RE.match(para):
            continue
        return para
    return ""


def migrate(content: str) -> tuple[str, dict]:
    """
    Returns (new_content, extracted) where extracted is a dict of what was found.
    """
    fm, body = parse_existing_frontmatter(content)
    extracted = {}

    # Split body at first HR to isolate the metadata block
    hr_splits = list(HR_RE.finditer(body))
    if hr_splits:
        first_hr = hr_splits[0]
        meta_block = body[:first_hr.start()]
        rest = body[first_hr.end():]
    else:
        meta_block = body
        rest = ""

    # --- Extract title from H1 ---
    h1_m = H1_RE.search(meta_block)
    if h1_m and 'title' not in fm:
        fm['title'] = h1_m.group(1).strip()
        extracted['title'] = fm['title']
        meta_block = meta_block[:h1_m.start()] + meta_block[h1_m.end():]

    # --- Extract tags ---
    tags_m = TAGS_RE.search(meta_block)
    if tags_m and 'tags' not in fm:
        raw_tags = tags_m.group(1)
        tags = [t.strip() for t in re.split(r'[,;]', raw_tags) if t.strip()]
        if tags:
            fm['tags'] = tags
            extracted['tags'] = tags
        meta_block = meta_block[:tags_m.start()] + meta_block[tags_m.end():]

    # --- Extract yield ---
    yield_m = YIELD_RE.search(meta_block)
    if yield_m and 'yield' not in fm:
        fm['yield'] = yield_m.group(1).strip()
        extracted['yield'] = fm['yield']
        meta_block = meta_block[:yield_m.start()] + meta_block[yield_m.end():]

    # --- Extract source from trailing *Source: ...* line (may be in rest) ---
    for block_name, block in [('meta', meta_block), ('rest', rest)]:
        source_m = SOURCE_RE.search(block)
        if source_m and 'source' not in fm:
            fm['source'] = source_m.group(1).strip()
            extracted['source'] = fm['source']
            if block_name == 'meta':
                meta_block = meta_block[:source_m.start()] + meta_block[source_m.end():]
            else:
                rest = rest[:source_m.start()] + rest[source_m.end():]
            break

    # --- Extract description ---
    if 'description' not in fm:
        desc = extract_description(meta_block)
        if desc:
            fm['description'] = desc
            extracted['description'] = desc[:60] + ('...' if len(desc) > 60 else '')
            # Remove description from meta_block
            meta_block = meta_block.replace(desc, '', 1)

    # --- Ensure stub fields exist for manual fill ---
    for field in ('author', 'recommended_by'):
        if field not in fm:
            fm[field] = None

    # --- Rebuild body ---
    # Clean up the meta block (just the H1 title remains, already in frontmatter)
    # We keep it for readability but could strip -- let's keep the H1 in body too
    # so the markdown still renders standalone.
    h1_line = f"# {fm['title']}\n" if 'title' in fm else ""

    # Collapse multiple blank lines left by extractions
    meta_remainder = re.sub(r'\n{3,}', '\n\n', meta_block).strip()

    # Rebuild: H1 + optional description as body prose + HR + ingredients + rest
    body_parts = []
    if h1_line:
        body_parts.append(h1_line.rstrip())
    if fm.get('description'):
        body_parts.append(fm['description'])
    if meta_remainder:
        # Anything left in meta block that we didn't extract
        clean = re.sub(r'^#\s+.+$', '', meta_remainder, flags=re.MULTILINE)
        clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
        if clean:
            body_parts.append(clean)

    new_body = "\n\n".join(body_parts)
    if rest.strip():
        new_body = new_body + "\n\n---\n\n" + rest.strip()

    # --- Serialise frontmatter ---
    # Preserve field order: title, date, author, source, recommended_by, tags, yield, description
    ordered = {}
    for key in ('title', 'date', 'author', 'source', 'recommended_by', 'tags', 'yield', 'favorite', 'notes', 'description'):
        if key in fm:
            ordered[key] = fm[key]
    # any extra keys (future-proofing)
    for key, val in fm.items():
        if key not in ordered:
            ordered[key] = val

    fm_str = yaml.dump(ordered, allow_unicode=True, default_flow_style=False,
                       sort_keys=False).rstrip()

    new_content = f"---\n{fm_str}\n---\n\n{new_body}\n"
    return new_content, extracted


def main():
    dry_run = '--dry-run' in sys.argv
    file_args = [a for a in sys.argv[1:] if not a.startswith('--')]

    if file_args:
        files = [Path(f) for f in file_args]
    else:
        files = sorted(RECIPES_DIR.glob("*.md"))

    changed = 0
    for f in files:
        original = f.read_text(encoding='utf-8')
        new_content, extracted = migrate(original)

        if new_content == original:
            print(f"  unchanged: {f.name}")
            continue

        changed += 1
        tag_str = f"  extracted: {', '.join(extracted.keys())}"
        if dry_run:
            print(f"[dry-run] {f.name}")
            print(tag_str)
        else:
            f.write_text(new_content, encoding='utf-8')
            print(f"  migrated: {f.name}")
            print(tag_str)

    print(f"\n{'[dry-run] ' if dry_run else ''}Done. {changed}/{len(files)} files {'would be ' if dry_run else ''}changed.")


if __name__ == '__main__':
    main()
