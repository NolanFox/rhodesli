# Session 82e Context: UX Feature Implementation

**Predecessor:** Session 82d (v0.84.0, inline Find Similar + performance)
**Planning source:** Session 82 planning transcript (this file distills that research)
**Date:** 2026-03-01

---

## Research Origin

Session 82a (Antigravity) produced a 30-idea ideation list, 5 Nano Banana mockup PNGs, competitor analysis, and an implementation plan. The 82a eval (`docs/assessments/session-82a-eval.md`, score 16/40) found the work structurally complete but shallow — mockup aesthetic was the standout. A planning session then ranked all 30 ideas into GREEN/YELLOW/RED tiers, cross-referenced against existing features, and produced PRD sketches for the top candidates.

---

## Ranked Feature Table

### GREEN (Implement in 82e)

| # | Feature | Effort | Why GREEN |
|---|---------|--------|-----------|
| 5 | Mobile Hamburger Menu Fix | Low | **BUG FIX** — broken mobile nav on Timeline/Compare blocks real users |
| 2 | Masonry Adaptive Grid | Low | CSS-focused; photo dimensions already cached in `photo_index.json`; stops cropping heads off archival photos |
| 28 | Share for Help Button | Medium | Powers growth loop: "Help identify this person from Rhodes, 1935" is highest-engagement action; OG card optimization |
| 25 | "Help Needed" Page | Medium | Direct mission service; have data (face quality, ID status); clear "how you can help" entry point |
| 22 | Click-to-Target AI Bounding Boxes | Medium | ML bounding box data already in `embeddings.npy`; eliminates face tagging friction; mockup exists |
| 17 | "Identify Mode" Focus State | Low | CSS + small JS; dim background, pulse unidentified faces; supports Help Identify flow |
| 21 | "Missing Info" Table View | Medium | Admin/contributor power tool; systematic archive cleanup |
| 30 | One-Click Bulk Tag Confirmation | Medium | 398+ review queue items; current one-at-a-time is slow; admin productivity |
| 19 | Relational Context Labels | Medium | Have GEDCOM relationship data; "Alberto, standing next to his brother Isaac" adds narrative |

### YELLOW (Consider for future)

| # | Feature | Notes |
|---|---------|-------|
| 24 | "Low Confidence" Suggestion Mode | Lowers participation barrier; needs moderation design |
| — | Design Direction (DD-006) | Warm dark, gold/amber (#D4A574), serif headings — codify to prevent drift |
| 26 | Categorized AI Rejection Reasons | Small UI; feeds ML quality loop |
| 13 | Historical Context Sidebar | Emotionally powerful; requires curated data |
| 1 | Global Command Palette (Cmd+K) | Power user feature; nice-to-have |
| 20 | "On This Day" | Seasonal engagement; have date estimates |
| 3 | "Surprise Me" Module | Simple random query; encourages exploration |

### RED (Skip — exists, too expensive, or low ROI)

| # | Feature | Reason |
|---|---------|--------|
| 6 | Radial Family Tree | **Already built** (Sessions 75-81, D3 tree with cards/expand/search) |
| 11 | Before/After Enhancement Slider | Requires AI colorization pipeline (major scope) |
| 12 | Audio Narrative Snippets | Requires audio infrastructure |
| 16 | Ken Burns Slideshows | Passive consumption, doesn't drive identification |
| 9 | Infinite Scroll | Performance risk with HTMX; 274 photos is fine with pagination |
| 4 | Power-User Keyboard Shortcuts | Niche; heritage visitors don't use KB shortcuts |

---

## Technical Architecture Notes

### Masonry Grid (#2)
- Photo dimensions already cached in `photo_index.json` (width/height per photo)
- CSS approach: `CSS columns` native or CSS Grid with `masonry` auto-flow
- Calculate aspect ratio per photo server-side, pass as inline style
- Mobile: single column below 600px
- Current grid uses `aspect-square` Tailwind classes — replace those

### Click-to-Target Bounding Boxes (#22)
- Bounding boxes in `embeddings.npy`: `[x1, y1, x2, y2]` pixel coordinates
- Photo dimensions in `photo_index.json` for scaling
- Render as SVG overlay on photo; scale bboxes relative to rendered image
- `det_score` in embeddings — color-code by confidence (blue=high, yellow=low)
- Admin click → auto-fill face index in sidebar

### Share for Help + Help Needed (#28, #25)
- Unidentified faces: `state == INBOX` in identities
- Quality scores: `quality` field in embeddings (0-1 range)
- OG meta tags on person pages: `og:title`, `og:image` (face crop URL)
- New `/help` page: top 50 unidentified high-quality faces
- Share button generates OG card optimized for Facebook/Twitter preview

### Identify Mode (#17)
- CSS-only dim + pulse/glow on unidentified faces
- Toggle button on photo page
- Uses existing face overlay positions (already rendered for admin)

### Missing Info Table (#21)
- New route: `/photos?view=table` or dedicated `/admin/missing`
- Join identities + photo_index to flag missing: date, location, names
- HTMX `hx-get` buttons for inline edit modals

### Bulk Tag Confirmation (#30)
- Group pending suggestions by identity
- Batch approve/reject via POST with array of IDs
- Admin-only; builds on existing Gatekeeper pattern

### Relational Context Labels (#19)
- GEDCOM relationships in Supabase (1,240 rels synced Session 81C)
- For each face in a photo, look up relationships to other faces in same photo
- Generate label: "X, [relationship] of Y"
- Display below face overlay or in face card

---

## Parallel Track Strategy

### Recommended Layout (3 tracks)

**Track A: Visual + CSS (worktree)**
- Masonry grid (#2)
- Mobile hamburger fix (#5)
- Identify Mode CSS (#17)
- *Touches:* `app/main.py` grid rendering, CSS
- *Conflict risk:* LOW if changes are in separate DOM sections

**Track B: New Pages + Routes (worktree)**
- Help Needed page (#25)
- Share for Help OG cards (#28)
- Missing Info table (#21)
- *Touches:* `app/main.py` route registration, new endpoints
- *Conflict risk:* LOW — new routes don't conflict with existing code

**Track C: Admin Tools (worktree)**
- Bulk tag confirmation (#30)
- Click-to-target boxes (#22)
- Relational context labels (#19)
- *Touches:* `app/main.py` admin sections, face rendering
- *Conflict risk:* MEDIUM — shares face rendering code with Track A

### Merge Order
1. Track B first (new pages, minimal conflict)
2. Track A second (CSS changes)
3. Track C last (admin tools, most likely to need manual merge)

### Key Conflict Zone
All tracks touch `app/main.py` (~6000+ lines). Session 82d's lesson: "Monolithic app files prevent parallel worktree execution — tracks touching app/main.py must be sequential" (Lesson 88). Mitigation: keep each track's changes to distinct line ranges.

---

## Mockup References

5 Nano Banana PNGs from Session 82a at `docs/assessments/mockups/`:
- `mockup_ai_bounding_box.png` — Dark theme, yellow box, "Identify" CTA (510KB)
- `mockup_masonry_grid.png` — Varied aspect ratios, sepia tones (649KB)
- `mockup_missing_info_table.png` — Dark table with "Add Info" CTAs (423KB)
- `mockup_radial_tree.png` — Circular layout (656KB) — **skip, already built**
- `mockup_vertical_timeline.png` — Elegant interspersed photos (519KB) — **skip, already built**

Note: Mockups use generic branding (not Rhodesli). Use as directional inspiration only.

### Design Direction (from 82a eval)
- Color: Warm dark (#1a1a1a background), gold/amber accents (#D4A574, #C9915D)
- Typography: Serif headings for archival feel, sans-serif body
- Layout: Breathable whitespace, museum-catalog aesthetic
- Interactions: Museum-quiet, gentle hovers, focus states for a11y

---

## Existing Feature Awareness (DO NOT Rebuild)

| Feature | Status | Sessions |
|---------|--------|----------|
| D3 Family Tree | Live | 75-81 (card layout, expand, search, generation bands) |
| Timeline page | Live | 75-81 (person-centered events) |
| Map page | Live | 81 (Leaflet, confidence badges) |
| Similarity calibration | Live | 63-66 (isotonic, AUC=0.9577) |
| Auto-clustering | Live | 76a (Tier 1 <0.85, Tier 2 0.85-1.30) |
| Inline Find Similar | Live | 82d (HTMX expansion panel, AD-194) |
| Person gallery toggle | Live | 82d (HTMX partial swap, AD-195) |
| Face overlay toggle | Live | 65a (admin ON, non-admin OFF) |

---

## Cross-References

- 82a eval: `docs/assessments/session-82a-eval.md`
- 82a ideation (30 ideas): `docs/assessments/session-82a-ideation.md`
- 82a top proposals: `docs/assessments/session-82a-top-proposals.md`
- 82a implementation plan: `docs/assessments/session-82a-implementation-plan.md`
- 82d assessment: `docs/assessments/session-82d-assessment.md`
- 82d archaeology: `docs/session_context/session-82d-archaeology.md`
- Session 82 context (bugs): `docs/session_context/session-82-context.md`
- Backlog: `docs/BACKLOG.md`
- UX tracker: `docs/ux_audit/UX_ISSUE_TRACKER.md`

---

## Deferred to Future Sessions

- Historical Context Sidebar (#13) — needs curated Rhodes historical data
- Discussion Threads (#29) — needs moderation infrastructure
- Contributor Gamification (#23) — premature for current user base
- Design Direction codification (DD-006) — could be done alongside any UI session
- BACKLOG entries from 82a (25 items on 82c branch) — need cherry-pick to main
