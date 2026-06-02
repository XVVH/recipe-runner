# SSG Design Tokens — Heirloom Cookbook Theme

Implemented from Claude Design handoff (2026-05-28).
Source files: `site/static/style.css`, `site/templates/`.

## Color Palette (oklch)

| Token | oklch | ~hex | Usage |
|---|---|---|---|
| `--paper` | `oklch(0.985 0.009 75)` | `#FBF7F1` | page background |
| `--paper-2` | `oklch(0.965 0.012 75)` | `#F4EEE4` | table header / panel fill |
| `--ink` | `oklch(0.255 0.012 60)` | `#332E29` | primary text |
| `--ink-soft` | `oklch(0.45 0.014 60)` | `#5F564E` | secondary text |
| `--ink-faint` | `oklch(0.6 0.012 60)` | `#857B72` | tertiary / meta labels |
| `--rule` | `oklch(0.88 0.012 70)` | `#E2DBD1` | hairline borders, dotted rules |
| `--rule-strong` | `oklch(0.8 0.014 65)` | `#C9BFB2` | table outer border |
| `--orange` | `oklch(0.74 0.13 56)` | `#E2965B` | accent borders, star focus |
| `--orange-ink` | `oklch(0.56 0.15 47)` | `#B06A3B` | accent text (links, highlights, labels) |
| `--orange-soft` | `oklch(0.93 0.05 70)` | `#F5E7D6` | row hover, selection |
| `--orange-line` | `oklch(0.82 0.1 60)` | `#E8BB8E` | underlines on accent links |
| `--star` | `oklch(0.72 0.15 62)` | `#D89A4A` | filled favorite star |

Accent is Apricot (default). Two alternate palettes exist in handoff (Terracotta, Honey) but are not exposed to users.

## Typography

- `--font-display`: Spectral (weights 600/700/800 + italic 600) — titles, step numbers, ingredient group names
- `--font-body`: Source Serif 4 (400/600 + italic) — body copy, ingredient list, meta, search input
- Google Fonts import: `Spectral:ital,wght@0,400;0,600;0,700;0,800;1,400;1,600` + `Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400`
- Base size: 17px, line-height 1.6
- `font-variant-numeric: tabular-nums` on dates and quantities

## Layout

- Content max-width: 1040px, centered, 32px side padding (18px mobile)
- Square corners everywhere (border-radius: 0)
- Hairline borders: 1px solid
- No drop shadows
- Recipe body: `grid-template-columns: 300px 1fr` (sidebar); `1fr` (stacked)
- Ingredients column: sticky, 300px, right border, 36px padding
- Breakpoint: 720px → single column, date column hidden

## Key Class Names

- `.masthead` → centered header with `.kicker`, `h1`, `.sub`
- `.toolbar` → search + favorites filter + count
- `.recipe-table` → index table; `.cell-title`, `.cell-author`, `.cell-date`, `.cell-fav`
- `.star-btn` / `.fav-badge` → favorite toggles (localStorage)
- `.section-head` → uppercase label with trailing rule (`::after`)
- `.ingredient-list li` → 2-col grid `124px 1fr` for qty/name alignment
- `.steps` → CSS counter list; `::before` = 34×34 square orange-bordered number
- `.ing-ref` → `[[ingredient]]` highlight: bold + orange-ink
- `.comments-body` → notes blockquote: italic, 3px orange left border

## Ingredient Highlight Markup

In instruction step text, wrap ingredient mentions in double brackets:
`"Beat the [[butter]] and [[sugar]] until fluffy."`

`recipe.js` converts these at runtime to `<span class="ing-ref">butter</span>`.
This is authored markup — add it manually during content review for best results.
