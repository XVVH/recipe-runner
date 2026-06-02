# RecipeMD Format Reference

Spec: https://recipemd.org/specification.html  
Version: 2.4.0 (updated Feb 2024)  
Python library: `pip install recipemd` (v5.0.0, May 2026, actively maintained)  
Scraper/importer: `pip install recipemd-extract`

## Minimal Example

```markdown
# Guacamole

A crowd-pleasing dip.

*sauce, vegan*
**4 Servings, 200g**

---

- *2* avocados
- *1 tsp* salt
- *.5* lime, juiced

---

Mash avocados with a fork, add salt and lime, season to taste.
```

## Full Structure

```
# Title                          (required, h1, first element)

Description paragraph(s)        (optional, plain text before tags/yield)

*tag1, tag2, tag3*               (optional, single italic paragraph)
**yield string**                 (optional, single bold paragraph)

---                              (first separator = start ingredients)

## Ingredient Section            (optional h2-h6 within ingredients)
- *amount* food, note            (list item; amount in italic)
- *1 1/2 cups* [stock](stock.md) (link to another recipe file)
- food with no amount            (amount is optional)

---                              (second separator = start instructions)

## Instruction Section           (optional h2-h6 within instructions)

Step text paragraph.

Another step paragraph.
```

## Amounts

Supported formats: integers (`2`), decimals (`1.5`), fractions (`1/2`, `1 1/2`), Unicode vulgar fractions (`½`, `¾`).

Amount wraps ONLY the quantity+unit in italic: `- *2 cups* flour` not `- *2 cups flour*`.

## Tags and Yield

- Tags: one italic paragraph, comma-separated. `*dessert, cookies, baking*`
- Yield: one bold paragraph. `**48 cookies**` or `**4 servings, 850g**`
- Both are optional. Order: tags before yield (convention, not enforced).

## Cross-Recipe Links

Ingredients can link to other recipe files:
```
- *1 cup* [chicken stock](chicken-stock.md)
```
Paths are relative to the current file.

## Language Implementations

- Python: `pip install recipemd` (reference implementation, LGPL v3)
- Rust: `recipemd-rs`
- TypeScript: `recipemd-ts`
- Swift: `recipemd-swift`
- Go: `recipemd-go`

## What RecipeMD Is NOT

- No YAML frontmatter (unlike nyum, my-online-cookbook)
- No strict section ordering beyond: title -> meta -> ingredients -> instructions
- No required fields beyond `# Title`
