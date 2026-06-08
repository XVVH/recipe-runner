"""Resolve [[Recipe Title]] and /recipe-slug/ references to internal recipe URLs."""
from __future__ import annotations

import html
import re
from typing import Callable

BRACKET_RE = re.compile(r"\[\[([^\]]+)\]\]")
SLUG_PATH_RE = re.compile(r"(?<![\w/])/([a-z0-9][a-z0-9-]*)/")


def recipe_link_index(recipes: list[dict], slugify: Callable[[str], str]) -> dict[str, str]:
    """Map lookup keys (slug, slugified title, lower title) to canonical slug."""
    index: dict[str, str] = {}
    for r in recipes:
        slug = r["slug"]
        index[slug] = slug
        title = (r.get("title") or "").strip()
        if title:
            index[title.lower()] = slug
            sk = slugify(title)
            if sk:
                index[sk] = slug
    return index


def lookup_recipe_slug(phrase: str, index: dict[str, str], slugify: Callable[[str], str]) -> str | None:
    phrase = phrase.strip()
    if not phrase:
        return None
    for key in (phrase.lower(), slugify(phrase)):
        if key and key in index:
            return index[key]
    return None


def linkify_brackets_html(
    text: str,
    index: dict[str, str],
    current_slug: str,
    slugify: Callable[[str], str],
) -> str:
    """Replace [[...]] with <a class=\"recipe-ref\"> or <span class=\"ing-ref\">."""

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        target = lookup_recipe_slug(inner, index, slugify)
        safe = html.escape(inner)
        if target and target != current_slug:
            return f'<a href="/{target}/" class="recipe-ref">{safe}</a>'
        return f'<span class="ing-ref">{safe}</span>'

    return BRACKET_RE.sub(repl, text)


def linkify_slug_paths_markdown(text: str, slugs: set[str]) -> str:
    """Turn /my-recipe-slug/ into markdown links when slug exists."""

    def repl(m: re.Match[str]) -> str:
        slug = m.group(1)
        if slug in slugs:
            return f"[/{slug}/](/{slug}/)"
        return m.group(0)

    return SLUG_PATH_RE.sub(repl, text)


def _bracket_to_md_link(
    m: re.Match[str],
    index: dict[str, str],
    current_slug: str,
    slugify: Callable[[str], str],
) -> str:
    inner = m.group(1)
    target = lookup_recipe_slug(inner, index, slugify)
    if target and target != current_slug:
        return f"[{inner}](/{target}/)"
    return m.group(0)


def tag_internal_recipe_links_html(html: str, slugs: set[str]) -> str:
    """Markdown notes emit <a href=\"/slug/\"> without recipe-ref; add the class."""
    for slug in sorted(slugs, key=len, reverse=True):
        html = html.replace(
            f'<a href="/{slug}/">',
            f'<a href="/{slug}/" class="recipe-ref">',
        )
    return html


def apply_recipe_links(
    recipes: list[dict],
    slugify: Callable[[str], str],
) -> None:
    """Mutate recipe dicts: linkify steps, ingredient names, and notes HTML."""
    import markdown as md

    index = recipe_link_index(recipes, slugify)
    slugs = set(index.values())

    for r in recipes:
        cur = r["slug"]
        for group in r.get("ingredient_groups") or []:
            for item in group.get("ingredients") or []:
                name = item.get("name") or ""
                if "[[" in name:
                    item["name"] = linkify_brackets_html(name, index, cur, slugify)

        for section in r.get("instruction_sections") or []:
            section["steps"] = [
                linkify_brackets_html(s, index, cur, slugify) for s in section.get("steps") or []
            ]

        notes_raw = r.get("notes") or ""
        if notes_raw:
            prepped = linkify_slug_paths_markdown(notes_raw, slugs)
            prepped = BRACKET_RE.sub(
                lambda m: _bracket_to_md_link(m, index, cur, slugify),
                prepped,
            )
            html_out = md.markdown(prepped)
            html_out = tag_internal_recipe_links_html(html_out, slugs)
            r["notes_html"] = linkify_brackets_html(html_out, index, cur, slugify)
        elif r.get("notes_html"):
            r["notes_html"] = linkify_brackets_html(r["notes_html"], index, cur, slugify)