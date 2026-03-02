# SDD-026: Find Similar Inline Expansion — Technical Design

## Architecture: Expandable Grid Slots + HTMX Fragment Loading

### Core Technique
- Keep existing vertical card visual structure.
- For each face card item, render a paired empty expansion slot immediately after it in source order.
- Expansion slot uses `grid-column: 1 / -1` when populated to span full grid width.
- HTMX `hx-get` loads HTML fragment into the paired slot.
- Slot empties on close/toggle to collapse with CSS `:empty` hiding.

### Why This Approach
- No absolute-position JS layout math.
- Maintains accessibility/source order.
- Naturally supports multiple simultaneously open panels.
- Compatible with existing FastHTML + HTMX architecture.

## Animation Decision
Use native CSS transitions and panel fade/slide for deterministic behavior across current HTMX swaps. Defer animate-css-grid/View Transitions to a later enhancement unless benchmarked benefit clearly exceeds complexity.

## DOM Pattern
- `face_card_grid` emits:
  - `.face-card-item` (card)
  - `.expansion-panel` with deterministic id `expand-{face_css_id}`

## Endpoint Contract
`GET /api/find-similar/{face_id}` returns **HTML fragment only** for inline injection.

Fragment includes:
- source hero card
- horizontal similar-face tile row
- actions per tile: Compare, Merge, Not Same
- close button (clears panel target)

## CSS Rules
- `.expansion-panel:empty { display:none; }`
- `.expansion-panel:not(:empty) { grid-column: 1/-1; ... }`
- `.similar-faces { display:flex; overflow-x:auto; }`
- `.similar-face-tile { flex:0 0 auto; width:160px; }`

## Non-Goals
- Changing admin face card orientation (must remain vertical)
- Replacing public `/people/{id}/similar` page behavior
