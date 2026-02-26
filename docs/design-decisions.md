# Design Decisions

This document tracks product and UX decisions. Each entry is authoritative and should not be revisited without explicit discussion.

---

## D1: Photo Browser Scope

**Date:** 2026-01-29
**Status:** Decided

**Context:** Users need to browse photos globally, not just through identity-grouped faces.

**Decision:** Separate route `/photos` with dedicated light-table surface.

**Rationale:**
- Main dashboard remains identity-focused
- Enables future filtering/sorting without cluttering identity review
- Clear mental model: "review identities" vs "browse photos"

**Tradeoffs:**
- Additional route to maintain
- Navigation between views requires clear affordances

---

## D2: Skip vs Reject Semantics

**Date:** 2026-01-29
**Status:** Decided

**Context:** Need to distinguish between "I don't know" and "These are NOT the same person."

**Decision:** Split semantics with distinct actions.

| Action | Meaning | Recoverable | Generates Signal |
|--------|---------|-------------|------------------|
| Skip | Temporary deferral | Yes | No |
| Reject ("Not Same Person") | Strong negative | No (intentional) | Yes (`negative_ids`) |

**Rationale:**
- Epistemic humility: uncertainty is not rejection
- Negative signals must be explicit and intentional
- Skip supports iterative review over time

**Tradeoffs:**
- Two actions instead of one increases UI complexity
- Must clearly communicate difference to users

---

## D3: Pagination Strategy

**Date:** 2026-01-29
**Status:** Decided

**Context:** Find Similar returns limited results; users need to see more.

**Decision:** Explicit "Load More" button.

**Rationale:**
- HTMX-compatible with modal-first navigation
- User controls when to load more (no surprise fetches)
- Simpler than infinite scroll state management

**Tradeoffs:**
- Requires explicit user action
- Must track offset state

---

## D4: Navigation Model

**Date:** 2026-01-29
**Status:** Decided

**Context:** Clicking faces/photos created confusing navigation state.

**Decision:** Modal-first navigation for photo context.

**Rationale:**
- Preserves identity-review flow
- Back button behaves predictably (closes modal, not page exit)
- Reduces context switching

**Tradeoffs:**
- Modals have accessibility considerations
- Deep linking to specific photos requires separate handling

---

## DD-001: Archival Aesthetic Direction

**Date:** 2026-02-25
**Status:** Decided
**Session:** 69 (Subagent A)

**Context:** The Rhodesli heritage archive serves a community preserving the memory of the Jewish Community of Rhodes. The existing dark theme (cold slate grays) felt more like a developer tool than a museum exhibition. Community members sharing photos on Facebook expect warmth and respect for historical content. Lesson 84 explicitly calls for "Museum-quality design for ML demos -- editorial feel beats developer utility."

**Decision:** Adopt an "editorial archival" aesthetic direction across the application:
- **Typography**: Playfair Display (serif) via Google Fonts CDN for all display headings, identity names, and branding. Configured as both `font-display` and `font-serif` in Tailwind.
- **Color palette**: Warm tones (amber-900, #2a241e, #3d3428) replacing cold slate for card backgrounds and borders, evoking aged paper and physical photographs.
- **CSS classes**: Three new archival classes (`.face-card-archival`, `.identity-card-archival`, `.photo-card-frame`) with warm gradients and shadows that suggest mounted prints.

**Alternatives Considered:**
1. **System serif only (Georgia)**: Would work without a CDN dependency, but Georgia lacks the distinctive character needed for an editorial feel.
2. **Cormorant Garamond**: Beautiful serif, but thinner strokes make it less legible at small sizes on face cards.
3. **Full warm background (cream/parchment)**: Tested but clashed with the existing dark mode. Warm accents within dark chrome was a better compromise.

**Rationale:**
- Playfair Display is a transitional serif that evokes late 19th / early 20th century typography, matching the period of many Rhodes archive photographs.
- Warm card backgrounds create a psychological bridge between "viewing a database" and "handling family photographs."
- Subtle sepia filter on face crop images reinforces the archival context without obscuring detail.
- Google Fonts CDN has global edge presence and is free -- no performance or cost concern.

**Tradeoffs:**
- +3 HTTP requests at page load (preconnect + font CSS + font files). Mitigated by `display=swap` to avoid FOIT.
- Font-display class name could collide with future Tailwind releases, but we define it in custom CSS which takes precedence.

**Revisit If:** Community feedback indicates the warm styling feels inappropriate, or if Tailwind CSS v4 ships a native `font-display` utility.

---

## DD-002: Face Card Layout Improvements

**Date:** 2026-02-25
**Status:** Decided
**Session:** 69 (Subagent A)

**Context:** Single-photo face cards in the identity browse view were visually heavy: 2-column layout at mobile, 4 at desktop, with cold slate backgrounds, heavy shadows, and excessive padding. For identities with many faces, the cards wasted enormous vertical space.

**Decision:** Redesign face cards and identity cards for compactness and warmth:
1. **Face card**: Reduced padding (p-2 to p-1.5), warm gradient background via `.face-card-archival`, amber-tinted border, lighter sepia filter (0.3 to 0.15 for more detail).
2. **Face grid density**: Changed from `grid-cols-2/3/4` to `grid-cols-3/4/5/6` -- 50% more faces visible per row on desktop.
3. **Identity card**: Replaced `bg-slate-800 border-slate-700` with `.identity-card-archival` warm gradient.
4. **Focus card**: Same archival treatment as identity cards.
5. **Photo detail person cards**: Added `.photo-card-frame` for the mounted-print aesthetic, warm hover state.

**What Changed (per component):**
| Component | Before | After |
|-----------|--------|-------|
| Face card bg | `bg-slate-700 border-slate-600 p-2` | `.face-card-archival p-1.5` (warm gradient) |
| Face card image border | `border-slate-600 bg-slate-700` | `border-amber-900/30 rounded-sm` |
| Face card sepia | `sepia-[.3]` | `sepia-[.15]` (lighter for more detail) |
| Face grid cols (desktop) | `md:grid-cols-4` | `md:grid-cols-5 lg:grid-cols-6` |
| Identity card | `bg-slate-800` | `.identity-card-archival` (warm gradient) |
| Focus card | `bg-slate-800` | `.identity-card-archival` |
| Photo person card | `bg-slate-800/50` | `.photo-card-frame` |
| Identity name H3 | `font-serif` | `font-display` (Playfair Display) |

**Rationale:**
- 6-column layout at lg means an identity with 8 faces fits in ~1.3 rows instead of 2 rows, dramatically reducing scroll.
- Lighter sepia (0.15 vs 0.3) preserves face detail while still cueing "archival."
- Warm gradient backgrounds on cards create visual separation without the harsh border effect of cold slate.
- All changes are CSS-only -- no data model, route, or logic changes.

**Tradeoffs:**
- Smaller face cards may be harder to distinguish at a glance on very small screens. Mitigated by keeping 3 columns (not 4+) at mobile.
- Warm backgrounds may reduce contrast for light-skinned historical photographs. The sepia filter reduction helps compensate.

**Revisit If:** Admin feedback finds faces too small at the 6-column density.

---

## Template for New Decisions

```markdown
## D[N]: [Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Decided | Superseded

**Context:** [What problem or question prompted this?]

**Decision:** [What was decided?]

**Rationale:** [Why this option?]

**Tradeoffs:** [Known downsides or risks]

**Revisit If:** [Conditions that would warrant reconsideration]
```
