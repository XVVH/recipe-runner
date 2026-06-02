# Recipe URL Ingestion -- Anti-Scraping Tier Architecture

Most popular recipe sites actively block server-side scrapers. This is the primary
operational challenge for batch URL import. The `scripts/ingest_url.py` script implements
a four-tier fallback chain; this file documents site-specific behavior and implementation
notes for each tier.

## Tier 1 -- recipemd-extract (direct)

Tool: `recipemd-extract <url> <output_file.md>`

CRITICAL: recipemd-extract writes to a FILE, not stdout. Must pass an explicit output
path (use tempfile.NamedTemporaryFile). Without it, writes to cwd with a random name.

Two plugins in recipemd-extract:
- `.recipe_schema`: handles top-level `{"@type": "Recipe"}` ld+json
- `.seriouseats`: site-specific parser (fragile -- fails if page structure changes)

Known crash pattern: `.recipe_schema` plugin crashes with
"expected string or bytes-like object, got 'list'" when the page uses
`{"@graph": [...]}` structure (common on Bon Appétit, Mediterranean Dish, etc.).
This triggers Tier 1b automatically.

## Tier 1b -- Direct ld+json extraction (ingest_url.py fallback)

Fires when Tier 1 produces no output or crashes. Does a direct HTTP fetch with
browser-like headers and parses the ld+json blocks directly.

Handles all three schema.org Recipe shapes:
- Top-level `{"@type": "Recipe", ...}`
- Graph array `{"@graph": [{"@type": "Recipe"}, ...]}`
- List `[{"@type": "Recipe"}, ...]`

Takes the first Recipe item found. Known limitation: pages with multiple Recipe
blocks (e.g. main recipe + sub-recipe for a sauce) may return the wrong one.
Signal: title is ALL CAPS or very short (<4 chars).

HTML entities (`&amp;`, `&#8217;` etc.) appear in description/instruction text --
cosmetic, renders fine in recipe-web. Could add `html.unescape()` in
`_recipe_schema_to_recipemd` if it becomes annoying.

## Tier 2 -- Wayback Machine CDX

CDX API: `http://web.archive.org/cdx/search/cdx?url=<url>&output=json&limit=1&fl=timestamp&filter=statuscode:200&from=20200101&sort=reverse`

Key parameters:
- `sort=reverse` -- CRITICAL. Without it, CDX returns oldest snapshot first (default behavior).
  `collapse=digest` has the same problem -- avoid.
- `from=20200101` -- avoids very old snapshots with sparse schema.org markup
- CDX timeout: 20s minimum. archive.org is slow, especially from non-residential IPs.
- Follow redirects: yes. archive.org redirect chain is safe.

Constructs archived URL as: `https://web.archive.org/web/<timestamp>/<original_url>`
Then runs Tier 1 extraction against the archived URL.

Site-specific behavior:
- **Serious Eats**: CDX finds snapshots, but archived pages have different ld+json
  structure than live pages. Both Tier 1 and Tier 1b fail on archived SE pages.
  Needs Tier 3 or Tier 4.
- **Food52**: CDX usually has snapshots. Structure is consistent, extraction works.
- **Bon Appétit**: Often blocked on live fetch, but Wayback usually works with @graph handling.

## Tier 3 -- Camoufox (NOT YET IMPLEMENTED)

Camoufox: Firefox-based stealth browser, Playwright API, open-source.
GitHub: https://github.com/daijro/camoufox

Install:
```bash
pip install camoufox[geoip]
python -m camoufox fetch
```

Usage pattern:
```python
from camoufox.sync_api import Camoufox
with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
# pass html to _extract_from_ldjson(url, html=html) -- needs function sig update
```

Status (May 2026): Firefox 138 introduced fingerprint inconsistencies that reduce
effectiveness. Camoufox is built on Firefox 135. Still better than raw scraping
but not a guaranteed bypass. Detected ~5% of the time on hardened sites.

Slot in ingest_url.py: between Wayback CDX and `blocked` return. The `_extract()`
function calls `_extract_from_ldjson(url)` which does its own HTTP fetch. For
Camoufox, fetch the HTML with Camoufox, then pass it to a modified extraction
function that takes raw HTML instead of fetching.

Must be tested in the recipe-worker profile environment -- verify headless mode
works and the venv has camoufox installed.

## Tier 4 -- Bookmarklet (manual)

Runs in a real browser as the logged-in user. Bypasses all bot detection.
Guaranteed to work. Requires human action per URL.

For RecipeMD ingestion (not Mealie): the bookmarklet would need to post the
rendered HTML to a local endpoint that runs `_extract_from_ldjson` and writes
the .md file. Not yet built. Current fallback: copy/paste the recipe manually
into a .md file.

## Site-Specific Notes

| Site | Tier 1 | Tier 1b | Tier 2 | Notes |
|------|--------|---------|--------|-------|
| themediterraneandish.com | fail (@graph crash) | works | n/a | @graph format, Tier 1b reliable |
| bonappetit.com | fail (blocked) | sometimes | works | @graph format; Wayback reliable |
| food52.com | fail (blocked) | n/a | works | Wayback reliable |
| epicurious.com | fail (blocked) | n/a | works | Wayback reliable |
| seriouseats.com | fail (402) | n/a | fail | Schema differs in archive. Needs Camoufox/bookmarklet |
| saveur.com | fail | fail | n/a | Empty/malformed schema |
| pauladeen.com | fail | fail | n/a | Empty/malformed schema |
| minimalistbaker.com | works (Wayback) | n/a | n/a | Multi-recipe block: title may be wrong (e.g. "SAUCE") |
| norecipes.com | works | n/a | n/a | |
| maangchi.com | works | n/a | n/a | Korean chars in title break slug word-overlap matching |

## Batch Result Interpretation

Script exits 1 if any URLs are blocked or errored -- this is expected behavior, not a failure.
JSON output per URL:
```json
{
  "url": "...",
  "status": "success|blocked|exists|error",
  "title": "...",
  "slug": "...",
  "output_path": "...",
  "wayback_used": true/false,
  "wayback_url": "...",
  "error": "direct: ... | wayback: ..."
}
```

The `error` field uses pipe-separated format to show which tier failed and why:
`"direct: <reason> | wayback: <reason>"` -- read both parts before diagnosing.
