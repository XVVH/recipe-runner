#!/usr/bin/env python3
# Run with: .venv/bin/python3 site/build.py  (see site/requirements.txt)
"""
Family Recipes SSG
Reads recipes/*.md, outputs _site/

Usage:
  python3 site/build.py              # build to _site/
  python3 site/build.py --serve      # build + serve on localhost:4000
  python3 site/build.py --watch --serve  # build + watch + serve
"""
import argparse
import http.server
import os
import re
import shutil
import sys
import threading
from pathlib import Path

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader

ROOT      = Path(__file__).parent.parent
RECIPES   = ROOT / "recipes"
SITE_DIR  = ROOT / "site"
TEMPLATES = SITE_DIR / "templates"
STATIC    = SITE_DIR / "static"
OUTPUT    = ROOT / "_site"
SITE_URL  = os.environ.get("RECIPE_RUNNER_SITE_URL", "http://localhost:4000")

# ── Ingredient parsing ─────────────────────────────────────────────────────────
# Matches RecipeMD-style: - *qty* name  or  - name (no qty)
INGR_RE = re.compile(r'^-\s+(?:\*([^*]*)\*)?\s*(.*)')


def block_looks_like_ingredients(text: str) -> bool:
    """True when a body section is an ingredient list (flat or ##-grouped), not prose."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("##"):
            continue
        if INGR_RE.match(line):
            return True
        return False
    return False


def parse_favorite(val) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("yes", "true", "1", "on")

def parse_ingredient_groups(md_block: str) -> list[dict]:
    """
    Parse the ingredient block (between first and second ---).
    Returns list of {name, items: [{qty, name}]}
    Supports ## headings for named groups.
    """
    groups = []
    current_group = {"name": None, "ingredients": []}

    for line in md_block.splitlines():
        line = line.strip()
        if not line:
            continue
        # Named group heading
        if line.startswith("##"):
            if current_group["ingredients"]:
                groups.append(current_group)
            current_group = {"name": line.lstrip("#").strip(), "ingredients": []}
            continue
        m = INGR_RE.match(line)
        if m:
            qty  = (m.group(1) or "").strip()
            name = m.group(2).strip()
            # Strip trailing comma artefacts
            name = name.rstrip(",").strip()
            current_group["ingredients"].append({"qty": qty, "name": name})

    if current_group["ingredients"]:
        groups.append(current_group)

    return groups or [{"name": None, "ingredients": []}]


# ── Instruction parsing ────────────────────────────────────────────────────────
def parse_instruction_sections(md_block: str) -> list[dict]:
    """
    Parse the instruction block (between ingredients and notes ---).
    ## headings start named sections; each other non-empty line is one step.
    Supports single-newline separation (## heading immediately followed by steps).
    """
    sections = []
    current_section = {"name": None, "steps": []}

    for line in md_block.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("##"):
            if current_section["steps"] or current_section["name"] is not None:
                sections.append(current_section)
            current_section = {"name": line.lstrip("#").strip(), "steps": []}
            continue
        current_section["steps"].append(line)

    if current_section["steps"] or current_section["name"] is not None:
        sections.append(current_section)

    return sections or [{"name": None, "steps": []}]


# ── Recipe loader ──────────────────────────────────────────────────────────────
def parse_source(raw) -> dict | None:
    """Convert source field (string URL or 'Book, p.N') to {text, url}."""
    if not raw:
        return None
    s = str(raw).strip()
    if s.startswith("http"):
        # Use domain as display text
        from urllib.parse import urlparse
        domain = urlparse(s).netloc.replace("www.", "")
        return {"text": domain, "url": s}
    return {"text": s, "url": None}


def format_date(iso: str | None) -> str:
    if not iso:
        return ""
    from datetime import date
    try:
        d = date.fromisoformat(str(iso))
        # Portable day (strftime %-d is BSD-only; breaks on Linux/Netlify builders)
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        return str(iso)


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return s.strip('-')


def validate_all_recipes() -> None:
    """Fail the build if any recipe violates the canonical contract."""
    from recipe_format import format_issues, validate_recipe_file

    all_issues = []
    for f in sorted(RECIPES.glob("*.md")):
        if f.name.startswith("_"):
            continue
        import frontmatter as _fm

        post = _fm.load(str(f))
        strict = bool(post.metadata.get("added_by"))
        all_issues.extend(validate_recipe_file(f, strict=strict))

    errors = [i for i in all_issues if i.level == "error"]
    warnings = [i for i in all_issues if i.level == "warning"]
    for w in warnings:
        print(f"  warning [{w.rule}]: {w.message}")
    if errors:
        print("Recipe validation failed:", file=sys.stderr)
        print(format_issues(errors), file=sys.stderr)
        sys.exit(1)


def load_recipes() -> list[dict]:
    recipes = []
    for f in sorted(RECIPES.glob("*.md")):
        if f.name.startswith("_"):
            continue
        post = frontmatter.load(str(f))
        fm   = post.metadata
        body = post.content.strip()

        # Strip leading --- if body starts with one (legacy: no description in body)
        if body.startswith("---"):
            body = body.lstrip("-").lstrip()

        # Split body on --- separators
        parts = re.split(r'\n---\n', body)

        # Description in body only when section 1 is prose, not ingredients
        has_description = bool(parts[0].strip()) and not block_looks_like_ingredients(parts[0])

        if has_description:
            # up to 4 parts: description, ingredients, instructions, notes
            description_block = parts[0].strip() if len(parts) > 0 else ""
            ingredient_block  = parts[1].strip() if len(parts) > 1 else ""
            instruction_block = parts[2].strip() if len(parts) > 2 else ""
            notes_block       = parts[3].strip() if len(parts) > 3 else ""
        else:
            # up to 3 parts: ingredients, instructions, notes (no description in body)
            description_block = ""
            ingredient_block  = parts[0].strip() if len(parts) > 0 else ""
            instruction_block = parts[1].strip() if len(parts) > 1 else ""
            notes_block       = parts[2].strip() if len(parts) > 2 else ""

        recipe = {
            "slug":             f.stem,
            "title":            fm.get("title") or f.stem.replace("-", " ").title(),
            "date":             str(fm["date"]) if fm.get("date") else None,
            "date_display":     format_date(str(fm["date"]) if fm.get("date") else None),
            "author":           fm.get("author"),
            "source":           parse_source(fm.get("source")),
            "recommended_by":   fm.get("recommended_by"),
            "added_by":         fm.get("added_by"),
            "tags":             fm.get("tags") or [],
            "yield":            fm.get("yield"),
            "description":      fm.get("description") or description_block or None,
            "favorite":         parse_favorite(fm.get("favorite")),
            "ingredient_groups":    parse_ingredient_groups(ingredient_block),
            "instruction_sections": parse_instruction_sections(instruction_block),
            "notes":            fm.get("notes") or notes_block or None,
            "notes_html":       markdown.markdown(fm.get("notes") or notes_block or ""),
            "comments":         fm.get("comments") or None,
        }
        recipes.append(recipe)
    return recipes


def all_tags(recipes: list[dict]) -> list[str]:
    tags: set[str] = set()
    for r in recipes:
        tags.update(r["tags"])
    return sorted(tags, key=str.lower)


# ── Build ──────────────────────────────────────────────────────────────────────
def build():
    validate_all_recipes()

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()

    if STATIC.exists():
        shutil.copytree(STATIC, OUTPUT / "static")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    env.filters["slugify"] = slugify

    from datetime import date as _date
    built = _date.today().isoformat()

    recipes = load_recipes()
    tags    = all_tags(recipes)

    # Index
    (OUTPUT / "index.html").write_text(
        env.get_template("index.html").render(recipes=recipes, tags=tags, built=built),
        encoding="utf-8"
    )

    # Recipe pages
    for recipe in recipes:
        d = OUTPUT / recipe["slug"]
        d.mkdir()
        (d / "index.html").write_text(
            env.get_template("recipe.html").render(recipe=recipe, built=built),
            encoding="utf-8"
        )

    # Tag pages
    tags_dir = OUTPUT / "tags"
    tags_dir.mkdir()
    for tag in tags:
        tagged  = [r for r in recipes if tag in r["tags"]]
        tag_dir = tags_dir / slugify(tag)
        tag_dir.mkdir(exist_ok=True)
        (tag_dir / "index.html").write_text(
            env.get_template("tag.html").render(tag=tag, recipes=tagged, built=built),
            encoding="utf-8"
        )

    write_robots()
    write_sitemap(recipes, tags)
    write_favicon()

    print(f"Built {len(recipes)} recipes · {len(tags)} tags → {OUTPUT}")
    return recipes


def write_robots():
    (OUTPUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_sitemap(recipes: list[dict], tags: list[str]):
    """Emit sitemap.xml for crawlers (index, recipes, tag pages)."""
    urls = [f"{SITE_URL}/"]
    urls += [f"{SITE_URL}/{r['slug']}/" for r in recipes]
    urls += [f"{SITE_URL}/tags/{slugify(t)}/" for t in tags]
    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )
    (OUTPUT / "sitemap.xml").write_text(xml, encoding="utf-8")


def write_favicon():
    """Copy SVG favicon to site root (linked from base template)."""
    src = STATIC / "favicon.svg"
    if src.exists():
        shutil.copy(src, OUTPUT / "favicon.svg")


# ── Dev server ─────────────────────────────────────────────────────────────────
def serve(port: int = 4000):
    import os, socket
    # Check port availability before binding
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("", port)) == 0:
            print(f"Port {port} already in use -- kill the existing server or use --port N")
            return
    os.chdir(OUTPUT)
    handler = http.server.SimpleHTTPRequestHandler
    with http.server.HTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Serving http://localhost:{port}  (Ctrl-C to stop)")
        httpd.serve_forever()


def watch_and_build():
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watchdog not installed: pip install watchdog")
        sys.exit(1)

    class Handler(FileSystemEventHandler):
        def on_modified(self, e):
            if e.is_directory:
                return
            p = e.src_path
            if any(p.endswith(x) for x in (".md", ".html", ".css", ".js")):
                print(f"↻  {p}")
                try:
                    build()
                except Exception as ex:
                    print(f"Build error: {ex}")

    obs = Observer()
    for watch_dir in (RECIPES, TEMPLATES, STATIC):
        if watch_dir.exists():
            obs.schedule(Handler(), str(watch_dir), recursive=True)
    obs.start()
    return obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--port",  type=int, default=4000)
    args = ap.parse_args()

    build()

    observer = None
    if args.watch:
        observer = watch_and_build()

    if args.serve:
        if args.watch:
            t = threading.Thread(target=serve, args=(args.port,), daemon=True)
            t.start()
            try:
                while True:
                    import time; time.sleep(1)
            except KeyboardInterrupt:
                if observer:
                    observer.stop()
        else:
            serve(args.port)


if __name__ == "__main__":
    main()
