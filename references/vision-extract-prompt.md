# Vision extraction prompt (cookbook / photo recipes)

Use with `vision_analyze` before `scripts/ingest_image.py --json`.

## Question string

```
Extract the complete recipe from this image. Return ONLY valid JSON (no markdown fences) with this shape:

{
  "title": "Recipe name",
  "author": "optional — only if printed on the card/page",
  "yield": "servings or yield string",
  "tags": ["course or cuisine tags"],
  "ingredients": ["quantity and ingredient as plain strings", "..."],
  "instructions": ["ordered steps as plain strings", "..."],
  "notes": ["optional tips, variations, do-ahead notes"]
}

Use grouped objects when the page has sections:
  "ingredients": {"Section Name": ["2 cups flour", "..."]},
  "instructions": {"Phase Name": ["step text", "..."]}

Rules:
- Preserve quantities and fractions exactly (½, 1/3, etc.)
- Do not invent ingredients or steps not visible on the page
- Do NOT include a description field unless a one-line summary is explicitly printed on the page
- Put cookbook attribution in a separate field only if asked; otherwise the agent passes --source
- No HTML in strings
- For multi-photo recipes, extract only what is visible on THIS image; the agent merges JSON files
```

## Multi-photo (front + back of card)

```bash
cd ~/dev/recipe-runner
# Save one JSON per photo, then merge:
.venv/bin/python3 scripts/ingest_image.py \
  --json /tmp/recipe-front.json /tmp/recipe-back.json \
  --source "Handwritten recipe card"
```

## Single image

```bash
.venv/bin/python3 scripts/ingest_image.py --json /tmp/recipe-extract.json \
  --source "Cookbook Title (p. 42)"
```

Pipeline: JSON → RecipeMD → canonicalize → [[highlights]] → validate → `recipes/<slug>.md`

Optional flags: `--no-highlight`, `--add-missing-ingredients`, `--author "Name"`
