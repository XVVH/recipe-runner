# Recipe Ingestion Fallback Chain

## Outcome Categories

| Code | Meaning | Action |
|------|---------|--------|
| `success` | recipemd-extract got clean output | Write .md, normalize, report |
| `wayback-used` | Direct fetch failed, Wayback snapshot used | Write .md, note source |
| `blocked` | All fetches failed, no usable snapshot | Needs bookmarklet or manual entry |
| `no-schema` | Fetched HTML but no Recipe schema found | Mark for manual entry |

## Priority Chain

1. `recipemd-extract <url>` directly
2. CDX lookup + `recipemd-extract <wayback_url>`
3. `scrape_html(html, wild_mode=True)` with browser UA headers -> hand-build RecipeMD
4. Mark blocked

## Wayback CDX API Pattern

```python
import httpx, re

async def wayback_fetch_html(url: str) -> str | None:
    cdx_url = (
        "http://web.archive.org/cdx/search/cdx"
        f"?url={url}&output=json&limit=1&fl=timestamp"
        "&filter=statuscode:200&from=20200101&sort=reverse"
    )
    # sort=reverse is CRITICAL -- without it returns oldest snapshot first
    # drop collapse=digest -- it also keeps oldest unique snapshot
    async with httpx.AsyncClient(timeout=20.0) as client:
        cdx_resp = await client.get(cdx_url)
        rows = cdx_resp.json()
        if len(rows) < 2:
            return None  # no snapshot
        timestamp = rows[1][0]
    archived_url = f"https://web.archive.org/web/{timestamp}/{url}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(archived_url, headers=BROWSER_HEADERS)
        if not resp.is_success:
            return None
        return resp.text

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
```

## Sync version (for use in worker scripts)

```python
import httpx

def wayback_fetch_html_sync(url: str) -> str | None:
    cdx_url = (
        f"http://web.archive.org/cdx/search/cdx"
        f"?url={url}&output=json&limit=1&fl=timestamp"
        f"&filter=statuscode:200&from=20200101&sort=reverse"
    )
    with httpx.Client(timeout=20.0) as client:
        rows = client.get(cdx_url).json()
        if len(rows) < 2:
            return None
        timestamp = rows[1][0]
        archived_url = f"https://web.archive.org/web/{timestamp}/{url}"
        resp = client.get(archived_url, follow_redirects=True, timeout=20.0,
                          headers=BROWSER_HEADERS)
        return resp.text if resp.is_success else None
```

## Known blocked sites (as of 2026-05-22)

- Serious Eats: 402 on direct fetch (server-side), both recipemd-extract plugins fail
- Food52, NYT Cooking: 403/429 behind Cloudflare from datacenter IPs

## CDX Pitfalls

- `sort=reverse` is non-negotiable -- default returns oldest, not newest snapshot
- `collapse=digest` also keeps oldest unique snapshot -- drop it entirely
- CDX timeout needs 20s minimum -- archive.org is slow from datacenter IPs
- `from=20200101` avoids ancient snapshots with sparse schema.org markup
- Wayback HTML will have archive.org toolbar injected -- `recipemd-extract` handles this fine
