# Family Tree UX Research — Session 80

## Date: 2026-02-28
## Purpose: Inform Rhodesli tree redesign (AD-185)

---

## Industry Standard Patterns

### 1. Ancestry.com (Market Leader)
- **Layout**: Horizontal pedigree — focal person center, ancestors above, descendants below
- **Couples**: Horizontal line connects married/partnered pairs side-by-side
- **Children**: Bracket drops from couple's horizontal line to children row below
- **Expand arrows**: Small arrows at edges of visible tree (up for ancestors, down for descendants)
- **Click behavior**: Click a person card → shows info popup with options (edit, navigate, etc.)
- **Zoom**: Mouse wheel + buttons. At max zoom-out, shows thumbnail boxes
- **Multiple views**: Pedigree (horizontal), Family (vertical), Fan chart, Map view
- **Person cards**: Rectangle with photo, name, birth/death dates. Couples share a horizontal connector

### 2. MyHeritage
- **Family View**: Each row = one generation. Lines connect spouses and children
- **Pedigree View**: Direct ancestors only (no siblings/cousins). Expand arrows reveal more generations
- **Fan View**: Radial/semicircle layout centered on focal person
- **Expand/collapse**: Click arrows at tree edges to expand branches. Arrows reverse to collapse
- **Person cards**: Photo + name + dates in a card/box format
- **Hover**: At maximum zoom-out, names appear only on hover

### 3. FamilySearch
- **Portrait view**: Vertical pedigree. You and descendants at bottom, ancestors above
- **Landscape view**: Horizontal. You in center, descendants left, ancestors right
- **Fan chart**: Semicircle with you at center, ancestors radiating outward
- **Interactive**: Click any person in chart → can refocus tree on them
- **Generations selector**: Choose how many generations to display
- **Color coding**: Can color by family lines, birthplace, sources, etc.

---

## Key Design Principles (Synthesized)

### Visual Hierarchy
1. **Couples are a UNIT**: Always displayed side-by-side connected by a horizontal line
2. **Generations are rows**: Each generation occupies one horizontal band
3. **Vertical lines** connect couples to their children below
4. **The "T-shape"**: Horizontal spouse connector + vertical drop to children is universal

### The Standard Family Connection Pattern
```
   [Father] ─── [Mother]     ← Couple: side by side, horizontal line
              │
    ┌─────────┼──────────┐   ← Vertical line drops from couple midpoint
    │         │          │
 [Child1]  [Child2]  [Child3] ← Children spread horizontally below
```

### Interaction Patterns
1. **Click person** → info panel / popup (NOT navigate away from tree)
2. **Double-click / dedicated button** → navigate to person's detail page
3. **Expand arrows** at tree edges load more generations
4. **Focus/re-center** → click a person, then "Make this person the focus"
5. **Zoom** via mouse wheel, pinch, and +/- buttons
6. **Pan** via click-drag on empty space

### Node/Card Design
- Photo (circular or rectangular) prominently displayed
- Name clearly readable (14-16px)
- Birth–death years secondary
- Gender sometimes indicated by card color (blue/pink) or icon
- Cards are typically 120-180px wide, 60-100px tall

### Multiple Spouses
- Show each marriage as a separate couple unit
- Person appears once, with horizontal lines going to each spouse
- Children drop from the appropriate couple connector

---

## Libraries Evaluated

| Library | License | Approach | Pros | Cons |
|---------|---------|----------|------|------|
| BALKAN FamilyTreeJS | Commercial (free tier) | Built-in family semantics | Multiple partners, photos, search, mini-map | Commercial license, heavy (150KB+) |
| donatso/family-chart | MIT | D3-based, TypeScript | MIT, modern, expand/collapse | Less mature, fewer features |
| BenPortner/js_family_tree | MIT | d3-dag for layout | "Union" node for couples, handles multiple spouses | More complex data model |
| d3-pedigree-tree | MIT | D3 hierarchy | Lightweight, iterative positioning | Academic-oriented, less polished |
| Custom D3 (current) | N/A | Manual BFS + layout | Full control, no dependencies | Must implement all patterns manually |

### Recommendation
Use **custom D3** (already in place) but implement the **standard "T-shape" couple layout** pattern. The current code positions nodes individually without couple units. The fix is to:
1. Group couples as a unit with horizontal connector
2. Drop vertical lines from couple midpoint to children
3. Use rectangular cards (not just circles) for better name readability
4. Add proper expand arrows at tree edges

---

## What Rhodesli Must Implement (Minimum Viable Parity)

1. **Couple units**: Partners side-by-side with horizontal connector line
2. **T-shape connections**: Vertical line from couple midpoint → horizontal spread → children
3. **Rectangular person cards**: Photo (circle inside card), name, dates — not just floating circles
4. **Expand arrows**: Clearly visible at top/bottom/sides with directional indicators
5. **Click → info popup**: NOT navigation. Popup offers "View Profile" and "Focus Tree"
6. **Re-focus**: Ability to re-center tree on any clicked person
7. **Zoom/pan**: Already implemented, keep it
8. **Search**: Already implemented, keep it

---

## Sources
- [Ancestry Support: Navigating a Family Tree](https://support.ancestry.com/s/article/Navigating-an-Ancestry-Family-Tree)
- [Ancestry: Tree Layouts](https://support.ancestry.com/s/article/Vertical-and-Horizontal-Tree-Displays)
- [MyHeritage: Pedigree View](https://blog.myheritage.com/2018/04/new-feature-pedigree-view-for-family-trees/)
- [MyHeritage: Fan View](https://blog.myheritage.com/2020/02/introducing-fan-view-for-family-trees/)
- [FamilySearch: Different Views](https://www.familysearch.org/en/blog/family-tree-views)
- [FamilySearch: Portrait Pedigree](https://www.familysearch.org/en/help/helpcenter/article/what-is-the-portrait-pedigree-view-in-family-tree)
- [BALKAN FamilyTreeJS](https://balkan.app/FamilyTreeJS)
- [donatso/family-chart (MIT)](https://github.com/donatso/family-chart)
- [BenPortner/js_family_tree](https://github.com/BenPortner/js_family_tree)
- [d3-pedigree-tree](https://github.com/solgenomics/d3-pedigree-tree)
- [yWorks: Drawing Family Trees](https://www.yworks.com/pages/drawing-family-trees-with-javascript)
