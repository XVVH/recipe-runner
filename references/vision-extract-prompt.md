# Vision extraction prompts (cookbook pages & recipe cards)

Use with `vision_analyze` before `scripts/ingest_image.py --json` or `--json-dir`.

Save **one JSON file per photo**. For multi-photo recipes, include `page_index` and
`page_role` so merge preserves order (instructions append; ingredients dedupe).

## Shared JSON shape

```json
{
  "page_index": 1,
  "page_role": "primary",
  "title": "Recipe name",
  "author": "optional — only if printed on the card/page",
  "yield": "servings or yield string",
  "tags": ["course or cuisine tags"],
  "ingredients": ["quantity and ingredient as plain strings"],
  "instructions": ["ordered steps as plain strings"],
  "notes": ["optional tips, variations, do-ahead notes"]
}
```

Grouped sections when the page has headings:

```json
"ingredients": {"Salad": ["2 cups kale"], "Dressing": ["1 egg yolk"]},
"instructions": {"Prep": ["Wash kale."], "Serve": ["Toss and serve."]}
```

Common rules (all prompts):
- Preserve quantities and fractions exactly (½, 1/3, etc.)
- Do not invent ingredients or steps not visible on the page
- Do NOT include `description` unless a one-line summary is explicitly printed
- Cookbook attribution: agent passes `--source`; do not guess book names
- Return ONLY valid JSON (no markdown fences)
- Extract only what is visible on **this** image

---

## Prompt A — single page or first cookbook page (`page_role: primary`)

Use when the photo is one full recipe page, or the **first** page of a multi-page recipe.

```
Extract the complete recipe visible on this image. Return ONLY valid JSON with:
page_index, page_role ("primary"), title, optional author/yield/tags,
ingredients, instructions, notes — as described in the schema.

If the recipe clearly continues on another page (ingredients or steps cut off mid-page),
still extract everything visible here and set page_role to "primary". Do not invent
content from pages you cannot see.
```

---

## Prompt B — cookbook continuation page (`page_role: continuation`)

Use for page 2, 3, … when a recipe spans multiple cookbook pages.

```
This image is a CONTINUATION page of a cookbook recipe (not the first page).
Return ONLY valid JSON with:
  "page_index": <number>,
  "page_role": "continuation",
  ingredients and/or instructions and/or notes visible on THIS page only.

Do NOT include title unless the recipe name is repeated on this page as a running header
(and only then if clearly the same recipe). Do NOT include yield unless printed on this page.
Do not repeat ingredients or steps already implied from a previous page unless they are
printed again on this page. Preserve step order as printed.
```

---

## Prompt C — index card front (`page_role: index_front`)

```
This is the FRONT of a handwritten or printed recipe index card.
Return ONLY valid JSON with page_role "index_front", page_index 1, title (if visible),
ingredients (and yield if shown). Instructions are usually on the back — omit them unless
printed on this side.
```

---

## Prompt D — index card back (`page_role: index_back`)

```
This is the BACK of a recipe index card (often instructions only).
Return ONLY valid JSON with page_role "index_back", page_index 2,
instructions and notes visible on this side. Omit title unless repeated.
Do not invent ingredients.
```

---

## Hermes agent workflow (multi-photo)

1. Decide type: **cookbook** (ordered pages) or **index-card** (front + back).
2. For each image in order, `vision_analyze` with Prompt A/B or C/D.
3. Save responses to a temp dir, e.g. `/tmp/recipe-pages/page-01.json` (vision JSON may
   include markdown fences — `ingest_image.py` tolerates that).
4. Merge + ingest:

```bash
cd ~/dev/recipe-runner
.venv/bin/python3 scripts/ingest_image.py \
  --json-dir /tmp/recipe-pages \
  --recipe-type cookbook \
  --source "Joy of Cooking (p. 210–211)" \
  --added-by "$RECIPE_RUNNER_ADDED_BY"
```

Index card (two files):

```bash
.venv/bin/python3 scripts/ingest_image.py \
  --json /tmp/recipe-front.json /tmp/recipe-back.json \
  --recipe-type index-card \
  --source "Grandma's card"
```

Single image:

```bash
.venv/bin/python3 scripts/ingest_image.py --json /tmp/recipe-extract.json \
  --source "Cookbook Title (p. 42)"
```

Pipeline: JSON → merge (if multi) → RecipeMD → canonicalize → [[highlights]] → validate → `recipes/<slug>.md`

Optional flags: `--no-highlight`, `--add-missing-ingredients`, `--author "Name"`, `--dry-run`
