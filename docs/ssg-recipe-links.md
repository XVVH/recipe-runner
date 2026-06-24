# SSG cross-recipe links and notes link styling

Implemented in `site/recipe_links.py`, invoked from `site/build.py` after `load_recipes()` via `apply_recipe_links(recipes, slugify)`.

## What authors write

| Syntax | Resolves when |
|--------|----------------|
| `[[Exact Title]]` | Title (case-insensitive) or `slugify(title)` matches another recipe's slug |
| `/recipe-slug/` in notes | Slug exists in `recipes/*.md` (filename stem) |

Same-recipe `[[Title]]` on that recipe's page stays a **highlight** (`<span class="ing-ref">`), not a self-link.

**Do not rely on** frontmatter `related:` — not in the format contract; no "see also" block is rendered.

## Build behavior

1. **Index:** slug, `title.lower()`, `slugify(title)` → slug.
2. **Ingredients / steps:** `linkify_brackets_html()` → `<a href="/slug/" class="recipe-ref">` or `ing-ref` span. Template uses `| safe` on `item.name` and step text.
3. **Notes:** Markdown path — bracket → `[title](/slug/)`, `/slug/` → `[/{slug}/](/slug/)`, then `markdown.markdown()`. Plain `<a>` from MD **does not** get `recipe-ref` unless tagged.
4. **`tag_internal_recipe_links_html()`** — after MD, adds `class="recipe-ref"` to `<a href="/known-slug/">`.
5. **Leftover `[[...]]` in HTML** — second pass `linkify_brackets_html` on notes HTML.

## Notes CSS pitfall

Notes body is italic (`.comments-body p`). Markdown links were unstyled `<a>` → browser default purple.

**Fix (both required):**
- `site/static/style.css`: `.comments-body a, .comments-body a:visited` match `a.recipe-ref` (orange-ink, bold, **font-style: normal**, underline).
- Build tags internal note links with `recipe-ref` (see above).

**Client JS:** `recipe.js` only wraps leftover `[[...]]` in steps/notes when no `a.recipe-ref` present; primary linking is build-time.

## Deploy check

```bash
cd ~/dev/recipe-runner
.venv/bin/python site/build.py
rg 'recipe-ref' _site/ -g '*.html' | head
```

## Tests

`tests/test_recipe_links.py` — bracket resolves to other recipe's href.