# PRD-041: Magnifying Glass Inspect Mode

**Status:** DRAFT
**Author:** Research session (2026-03-13)
**Source:** Session 100 Codex research (#6), Antigravity plan review, Magic UI Lens pattern
**Dependencies:** Benefits from UX-204 (face card unification); can proceed independently
**BACKLOG:** UX-205

---

## Problem Statement

Rhodesli's archive contains group photos with 10-30+ faces. When an admin or community
member tries to identify a person, they need to inspect fine facial detail — but the
current UI forces a trade-off between seeing the whole photo (context) and seeing a
face up close (detail). The existing click-to-zoom on compare crops (`scale(2)` toggle)
loses spatial context entirely. The photo lightbox scroll-zoom moves the entire viewport.
Neither provides the "magnifying glass over a photo album" interaction that is natural
for heritage photo identification work.

The Antigravity plan review explicitly flagged this: "the ability to inspect the context
(or zoom in) is a primary workflow requirement for accurate identification, not just
visual polish."

## User Stories

1. **Admin reviewing face matches (Compare modal):** "I'm comparing two face crops
   side by side. I want to hover over one crop and see magnified detail of the eye
   area, hairline, or ear shape without losing sight of the other crop."

2. **Community member examining a group photo (Photo lightbox):** "I found my
   grandmother's wedding photo. There are 25 people. I want to move a lens across
   the photo to read faces without zooming in so far I lose track of who is where."

3. **Admin in speed-run cluster review:** "I'm reviewing 80x80px face thumbnails
   at speed. Some look similar but I need to inspect a detail before confirming.
   I want to hover briefly to see a magnified view, then move on."

4. **Community member on person page:** "I'm looking at all photos of 'Vida
   Capeluto.' Some face crops are small. I want to inspect them without
   navigating away from the identity gallery."

## Scope

### In Scope
- Magnifying lens overlay on face crops and full photos
- Desktop: hover-activated lens that follows cursor
- Mobile: long-press-activated lens that follows finger
- Keyboard toggle (`L` key) for compare and speed-run views
- Works with existing R2-served images (no new image pipeline)

### Out of Scope
- Server-side image tiling or multi-resolution pyramids (IIIF)
- New image upload sizes or quality variants
- Lens on the family tree visualization
- Lens on the Estimate tool results

## Surfaces (Priority Order)

| # | Surface | File | Current State |
|---|---------|------|---------------|
| 1 | Compare modal face crops | `app/compare_routes.py:5450-5491` | Click toggles `scale(2)` via Hyperscript |
| 2 | Photo lightbox | `app/page_routes.py:5560-5624` | Scroll-zoom + pinch-zoom (vanilla JS) |
| 3 | Speed-run cluster review | `app/cluster_review_routes.py:1397-1420` | 80x80px thumbs, no zoom |
| 4 | Identity card face gallery | `app/main.py:face_card()` line 8331 | No zoom |
| 5 | Photo modal (admin) | `app/main.py:photo_modal()` line 9669 | HTMX-loaded content, no zoom |

## Technical Approach

### Core Pattern: CSS Background-Position Lens

The lens is a circular `<div>` overlaid on the image. It uses the same image URL as
`background-image` but at 2-3x `background-size`, with `background-position` computed
from the cursor's offset relative to the image bounds.

```
Container (position: relative, overflow: hidden)
  Image (normal display)
  Lens div (position: absolute, pointer-events: none)
    - background-image: same src as <img>
    - background-size: 300%
    - background-position: computed from cursor
    - border-radius: 50%
    - width/height: 150px (configurable)
    - box-shadow for depth
    - border: 2px solid white/30%
```

### Hyperscript Implementation (Desktop)

```hyperscript
on mouseenter add .lens-active to me
on mouseleave remove .lens-active from me
on mousemove
  set rect to my getBoundingClientRect()
  set xPct to ((event.clientX - rect.left) / rect.width) * 100
  set yPct to ((event.clientY - rect.top) / rect.height) * 100
  set my style.--lens-x to `${event.clientX - rect.left - 75}px`
  set my style.--lens-y to `${event.clientY - rect.top - 75}px`
  set my style.--bg-x to `${xPct}%`
  set my style.--bg-y to `${yPct}%`
```

The lens `<div>` uses CSS custom properties:
```css
.lens-overlay {
  left: var(--lens-x); top: var(--lens-y);
  background-position: var(--bg-x) var(--bg-y);
}
```

### Mobile (Long-Press)

Hyperscript `on touchstart` with a 300ms delay activates the lens. `on touchmove`
updates position. `on touchend` removes it. The existing pinch-to-zoom in the
lightbox remains as fallback — the lens is additive, not a replacement.

### Progressive Enhancement

- **No JS:** Images render normally. No degradation.
- **CSS `@media (hover: hover)`:** Desktop lens styles only apply when a pointing
  device with hover capability is present.
- **CSS `@media (hover: none)`:** Long-press hint text shown on mobile.

### Reusable Component

A Python function `lens_image(src, alt, cls, zoom_factor=3, lens_size=150)` returns
a FastHTML `Div` containing the image and lens overlay div, with the Hyperscript
wired in. All surfaces call this instead of raw `Img()`.

## Interaction Design

| Platform | Activation | Behavior | Deactivation |
|----------|------------|----------|--------------|
| Desktop | Hover over image | Lens follows cursor | Move cursor away |
| Desktop | Click image | Toggle sticky lens mode | Click again |
| Desktop | Press `L` | Toggle lens mode for focused surface | Press `L` again |
| Mobile | Long-press (300ms) | Lens appears at touch point | Lift finger |
| Mobile | Drag while pressed | Lens follows finger | Lift finger |

### Keyboard Shortcuts (Compare + Speed-Run)
- `L` — Toggle lens mode on/off for the focused image
- `+` / `-` — Increase / decrease lens zoom factor (2x, 3x, 4x)

## Acceptance Criteria

1. **Compare modal:** Hovering over a face crop shows a circular lens with 3x
   magnification. Moving the cursor smoothly updates the magnified region. Both
   left and right crops support the lens independently.
2. **Photo lightbox:** Lens works on the full photo. Face bounding box overlays
   remain visible underneath the lens.
3. **Speed-run:** Hovering over an 80x80px thumbnail shows a 150px lens with the
   face at 3x. Does not interfere with confirm/reject button clicks.
4. **Mobile:** Long-press on any lens-enabled image activates magnification. Works
   on iOS Safari and Chrome Android.
5. **Performance:** No visible jank on a 3000x4000px R2 photo. The lens uses the
   browser-cached image (same URL as the `<img>` src).
6. **No regression:** Existing click-to-zoom on compare crops still works (lens
   replaces it). Existing scroll-zoom and pinch-zoom in lightbox still work
   alongside the lens.
7. **Progressive enhancement:** With JS disabled, all images display normally.

## Effort Estimate

| Phase | Scope | Estimate |
|-------|-------|----------|
| 1 | `lens_image()` component + compare modal | 1-2 hours |
| 2 | Photo lightbox integration | 2-3 hours |
| 3 | Speed-run thumbnail inspect | 1 hour |
| 4 | Identity card gallery | 1 hour |
| **Total** | | **~1 session** |

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Large photo jank on mobile | Medium | Use browser-cached src, not a second fetch. Test on real device. |
| Lens interferes with click actions | Low | `pointer-events: none` on lens div; clicks pass through to image/buttons. |
| HTMX swap destroys lens state | Medium | Event delegation pattern (Lesson 39). Lens Hyperscript on container, not swapped content. |
| Touch conflict with scroll on mobile | Medium | Long-press threshold (300ms) distinguishes from scroll. `touch-action: none` only while lens active. |
