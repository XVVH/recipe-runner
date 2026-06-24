# Handwritten recipe cards (vision → repo)

Session pattern: two photos (ingredients card + instruction sheet), sticky notes, cross-outs.

## Capture flow (recommended)

1. **Vision transcribe each image** — literal text; flag ambiguities.
2. **Merge pages** — page 1 often ends mid-sentence; page 2 has bake/layer/cool steps.
3. **Human judgment** — sticky notes → steps/notes; **drop** crossed-out lines.
4. **Resolve quantities** — confirm with the card author when overwritten; after confirm, notes bullet `*qty* confirmed with Author (date).`
5. **Direct canonical write** + `site/build.py` when `ingest_text.py` fails (odd tag/yield preamble lines).

## Quantity confirmation

When a quantity was illegible or overwritten on the card, note the resolved value in the recipe notes after family confirmation — do not change the ingredient line silently without documenting it.