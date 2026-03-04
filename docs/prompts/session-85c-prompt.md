# Session 85c — Universal Comparison Workspace

## Context

Sessions 85/85b delivered the core compare pipeline: unified uploads, vs-person comparison,
from-photo flow, shareable results, Isaac Cohen E2E validation. But the UX is fragmented
across 3 separate pages (`/compare`, `/compare/pair`, `/facecompare`), the design is sparse
and unfocused, and the tool doesn't support the full vision: **compare ANY entity against
ANY other entity(ies)**.

### Current State (v0.87.1)
- `/compare` — upload photo → match against archive or specific person
- `/compare/pair` — upload two photos → cross-match faces (separate page, janky)
- `/facecompare` — standalone museum-quality tool (separate audience, keep as-is)
- ~33 compare tests, ~3985 total tests

### What Works
- Upload → faces detected → compare vs specific person → share result
- Archive photo → compare vs specific person (from-photo flow)
- Uploads persist to archive (unified pipeline)
- Calibrated confidence scores with tier labels
- Shareable result URLs with OG cards
- Admin merge/not-same actions on results

### 16 Gaps to Close

| # | Gap | Severity |
|---|-----|----------|
| 1 | No Individual vs Individual direct compare | P1 |
| 2 | No Individual vs Existing Photo compare | P1 |
| 3 | No Existing Photo vs Existing Photo compare | P1 |
| 4 | No Existing Photo vs Uploaded Photo compare | P1 |
| 5 | Uploaded vs Uploaded is separate janky page | P2 |
| 6 | No face/photo toggle (only see crops, never full photo context) | P1 |
| 7 | No multi-select targets (single person only) | P1 |
| 8 | No hide/collapse individual matches | P2 |
| 9 | Search excludes INBOX/unidentified people | P2 |
| 10 | No photo search at all | P2 |
| 11 | No context per match card (how does score rank vs that person's best?) | P2 |
| 12 | Design is sparse and unfocused (user: "currently it is NOT well designed") | P1 |
| 13 | No animations (no smooth transitions, no visual feedback) | P2 |
| 14 | Fragmented UX (3 separate pages for different compare modes) | P1 |
| 15 | Upload progress has no visual polish | P3 |
| 16 | No URL state (can't bookmark a comparison setup) | P3 |

### Competitive Context
FamilySearch Compare-a-Face is entertainment ("which ancestor do I look like?"), not a tool.
Rhodesli beats them on purpose (identification > entertainment), transparency (calibrated
scores with evidence), speed (no account required), shareability (public links), and community
loop (share → identify → confirm). This session makes the UX match the superiority of the
underlying engine.

---

## Design Philosophy

1. **Compare is a workspace, not a form.** You build a comparison by selecting entities on
   two sides. Source on the left, targets on the right, results below.

2. **Universal entities.** Three entity types flow through one system:
   - **Person** — any identity (CONFIRMED, PROPOSED, or INBOX/unidentified)
   - **Photo** — any archive photo (selectable by search/browse)
   - **Upload** — a newly uploaded photo (processed in real-time for admin)

3. **Matrix results.** Source faces × target entities = comparison grid. Each cell shows
   calibrated confidence with context.

4. **Everything is fluid.** No page reloads. Smooth CSS animations. Instant feedback.
   Beat FamilySearch on speed and polish.

5. **Progressive disclosure.** Start simple (upload a photo), reveal complexity as needed
   (add targets, toggle views, hide faces). Don't overwhelm new users.

---

## Phase 0: Orient (5 min)

- Read CLAUDE.md, ROADMAP.md, tasks/lessons.md
- Set `.claude/current_session.txt` to "85c"
- Read this prompt in full, save to disk
- Verify: `make test-fast` passes
- Read current compare code in app/main.py (grep for compare routes)

---

## Phase 1: PRD-026 — Universal Comparison Workspace (15 min)

Write `docs/prds/026_universal_comparison_workspace.md` with:
- Problem statement (fragmented UX, sparse design, missing entity combinations)
- Entity type definitions (Person, Photo, Upload)
- The 3×3 matrix of all entity combinations and which are supported
- Workspace model wireframe (Source + Targets → Results)
- Acceptance criteria for each gap
- Out of scope: /facecompare changes, GPU inference on Railway, ML model changes

Commit: `docs(prd): PRD-026 universal comparison workspace`

---

## Phase 2: Backend — Unified Comparison Engine (60 min)

### 2A: New unified execute endpoint

Create `POST /api/compare/execute` that accepts any combination:

```python
# Request body (form-encoded for HTMX compatibility):
source_type: "person" | "photo" | "upload"
source_id: str  # identity_id, photo_id, or job_id
target_type: "person" | "photo" | "upload" | "archive"  # "archive" = all
target_ids: str  # comma-separated IDs (up to 5)
```

Processing logic:
1. **Resolve source faces**: Extract face_ids + embeddings from source entity
   - Person → anchor_ids + candidate_ids → embeddings
   - Photo → face_ids from photo_index → embeddings
   - Upload → face_ids from job status → embeddings
2. **Resolve target faces**: Same resolution per target
   - "archive" → use find_nearest_neighbors() for top N
3. **Compute matrix**: For each source face × each target:
   - L2 distance to best-matching target face
   - Calibrated confidence via SimilarityCalibrator
   - Tier classification
   - Context: target's own top match confidence (how does this score rank?)
4. **Save result** to comparison_results.json
5. **Return HTMX fragment** with full results UI

Response includes for each comparison cell:
- source_face_id, source_crop_url
- target_id, target_type, target_name, target_crop_url
- distance, confidence_pct, tier
- context_best_pct (target's best existing match %)
- context_rank (where this source face ranks among target's matches)

### 2B: Enhanced unified search

Create `GET /api/compare/search-unified`:
- Query parameter: `q` (min 2 chars), `types` (comma-separated: "person,photo")
- Search people: ALL states (CONFIRMED, PROPOSED, INBOX) via registry.search_identities()
  - Include INBOX with "Unidentified" badge
  - Show state badge (Confirmed / Proposed / Unidentified)
- Search photos: by collection name, filename, tagged person names
  - Show photo thumbnail + face count + collection
- Return max 10 results, sorted: exact name matches first, then fuzzy
- Each result includes: type badge, preview image, title, subtitle

### 2C: Photo browse API

Create `GET /api/compare/browse-photos`:
- Parameters: `collection` (optional filter), `page` (pagination), `q` (optional text search)
- Returns paginated photo cards with face count, collection, and thumbnail
- Used by Photo tab in source/target slots

### 2D: Visual similarity search API

Create `GET /api/compare/find-similar`:
- Parameters: `face_id` or `identity_id`
- Uses existing `find_nearest_neighbors()` to find top 10 visually similar faces
- Returns list of identities with distance, confidence, crop URL
- Powers the "Find visually similar people" button in target slot
- Essentially `find_nearest_neighbors()` but formatted for the target slot pill UI

### Tests for Phase 2
- Test all 9 entity type combinations (3 source × 3 target types)
- Test multi-target (3 people selected)
- Test "archive" target type
- Test unified search returns people + photos
- Test search includes INBOX identities
- Test photo browse with collection filter

Commit: `feat(compare): unified comparison engine — all entity types, multi-target, enhanced search`

---

## Phase 3: UX — Comparison Workspace (2-3 hours)

This is the main phase. Replace the current `/compare` page with a comparison workspace.

### 3A: Layout Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Compare Faces                                                │
│  Find connections across the Rhodes Jewish heritage archive   │
│                                                               │
│  ┌──────────── Source ──────────────┐ ┌── Compare With ─────┐│
│  │                                  │ │                      ││
│  │  [⬆ Upload] [👤 Person] [📷 Photo] │ │  Search people,      ││
│  │                                  │ │  photos, or upload...││
│  │  ┌────────────────────────────┐ │ │                      ││
│  │  │                            │ │ │  ┌──────┐ ┌──────┐  ││
│  │  │   Drag a photo here        │ │ │  │Isaac │ │Barouh│  ││
│  │  │   or click to browse       │ │ │  │Cohen │ │C.    │  ││
│  │  │                            │ │ │  │  [×] │ │  [×] │  ││
│  │  └────────────────────────────┘ │ │  └──────┘ └──────┘  ││
│  │                                  │ │                      ││
│  │  Detected faces:                 │ │  [+ Add another]     ││
│  │  [F1] [F2] [F3] [F4] [F5]      │ │  ─── or ───          ││
│  │                                  │ │  [🔍 All Archive]    ││
│  └──────────────────────────────────┘ └──────────────────────┘│
│                                                               │
│  ┌───────────── Compare ─────────────────────────────────────┐│
│  │                                                            ││
│  │  Comparing 5 faces against 2 people                       ││
│  │                                                            ││
│  │  View: [👤 Faces] [📷 Photos]   Hide: [F3][F4][F5]       ││
│  │                                                            ││
│  │  ┌─ Face 1 ──────────────────────────────────────────────┐││
│  │  │ ┌──────┐  vs Isaac Cohen    85% ██████████████░ ✓     │││
│  │  │ │ crop │  Strong match · Isaac's best is 92% · #3     │││
│  │  │ │      │  vs Barouh C.      42% ████████░░░░░░        │││
│  │  │ └──────┘  Unlikely · Barouh's best is 88% · #47      │││
│  │  │                                    [Merge] [Not Same] │││
│  │  └────────────────────────────────────────────────────────┘││
│  │  ┌─ Face 2 ──────────────────────────────────────────────┐││
│  │  │ ┌──────┐  vs Isaac Cohen    22% ████░░░░░░░░░░        │││
│  │  │ │ crop │  Unlikely · #128                              │││
│  │  │ │      │  vs Barouh C.      68% ██████████████░        │││
│  │  │ └──────┘  Possible match · Barouh's best is 88% · #8  │││
│  │  │                                    [Merge] [Not Same] │││
│  │  └────────────────────────────────────────────────────────┘││
│  │                                                            ││
│  │  [Share comparison] [Try another comparison]              ││
│  └────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 3B: Source Slot

Three modes (tabs across top of source panel):

**Upload tab** (default):
- Drag-drop zone with dashed border
- On drop/select: instant preview with subtle scale-up animation
- Upload triggers processing → progress bar (animated, not spinner)
- On completion: photo displayed with numbered face thumbnails below
- Each face thumbnail clickable (for future per-face focus mode)

**Person tab**:
- Search input with live autocomplete
- Results show face crop + name + state badge + face count
- On select: person's representative face shown in slot
- All faces from that person shown as thumbnails below

**Photo tab**:
- Search input + collection filter dropdown
- Photo gallery grid (small thumbnails, 4 across)
- On select: photo shown in slot with face thumbnails below

### 3C: Target Slot

**Search input** at top (unified search: people + photos):
- As user types: dropdown shows people + photos matching query
- Type badges: 👤 for person, 📷 for photo
- On select: entity added as a pill/chip below the search
- Each pill shows: face crop thumbnail + name + [×] remove button
- Maximum 5 targets (show "5/5 selected" counter)

**Upload option**: small "or upload a photo" link below search
- Opens upload zone in target slot (same as source upload)

**"All Archive" option**: button below pills
- Compares source against entire archive (top 10 matches per face)
- Mutually exclusive with specific targets (selecting clears pills)

**"Find Similar" option**: When a person or face is selected as source,
show "Find visually similar people" button in target slot. Uses existing
`find_nearest_neighbors()` to populate targets with the top N most similar
people from the archive. This is visual similarity search — you select a face
and the system finds archive faces that look similar, ranked by embedding distance.
The results populate the target pills automatically, then comparison runs.

**Multi-select behavior**:
- Adding a target immediately triggers comparison (no explicit "Go" button)
- Removing a target re-triggers with remaining targets
- Adding while results visible: results smoothly update

### 3D: Results Area

**Header**: "Comparing N faces against M targets" with view controls

**View toggle**: [Faces] [Photos]
- **Face View** (default): compact face crops with comparison bars
- **Photo View**: full photos with bounding box overlay highlighting the relevant face
  - Source photo on left, target photo(s) on right
  - Semi-transparent overlay on non-relevant faces
  - Smooth cross-fade transition between views (300ms)

**Hide controls**: Chip row showing "Hide: [F3] [F4] [F5]"
- Each face has a toggle (eye icon) in its section header
- Hidden faces: section collapses with smooth animation, chip appears in header
- Click chip to restore (expand animation)

**Per-face sections** (one per source face):
- **Left**: Face crop (80px) or full photo (in Photo View)
- **Right**: Comparison bars, one per target:
  - Target name (linked to /person or /photo page)
  - Confidence bar: colored by tier, animated width fill
  - Percentage + tier label ("Strong match", "Possible", "Unlikely")
  - Context line: "{Target}'s best existing match is {X}%. This ranks #{N}."
  - Admin actions: [Merge] [Not Same] buttons (only for person targets)
- **Collapse**: Click section header to collapse/expand
- **Staggered reveal**: Each face section slides in 100ms after the previous

**Best match highlight**: The face × target combination with highest confidence
gets a subtle highlight (gold border or star icon).

**Empty state**: Before any comparison, show:
"Select a source and one or more targets to begin comparing."
with visual cues pointing to both slots.

### 3E: Responsive Layout

**Desktop (>1024px)**: Side-by-side source + target slots, results full width below
**Tablet (768-1024px)**: Slots stack vertically, results full width
**Mobile (<768px)**: Single column, slots accordion-style, results simplified (no photo view)

### 3F: Backward Compatibility

- Keep `/compare/result/{id}` working (shareable links must not break)
- Keep `/compare?photo_id=X&person_id=Y` working (auto-populate source + target from URL)
- Keep `/compare?face_id=X` working (select person as source)
- Deprecate `/compare/pair` (redirect to `/compare` with "upload" mode on both sides)
- Keep `/facecompare` unchanged (different audience)

### Tests for Phase 3
- Test workspace renders with empty state
- Test source slot: upload, person search, photo selection
- Test target slot: multi-select, remove, "all archive"
- Test results render for all entity combinations
- Test face/photo toggle
- Test hide/collapse functionality
- Test backward compat URLs
- Test mobile responsive (375px viewport)

Commit: `feat(compare): universal comparison workspace — two-slot design, multi-target, matrix results`

---

## Phase 4: Animations & Visual Polish (45 min)

### CSS Animations (use CSS transitions + keyframes, no JS animation libraries)

1. **Upload progress**: Gradient shimmer effect on progress bar (not flat fill)
2. **Photo appear**: On upload complete, photo fades in + subtle scale from 0.95→1.0
3. **Face thumbnails**: Stagger in one-by-one (50ms delay each) with fade+slide-up
4. **Target pill add**: Scale from 0→1 + fade (200ms ease-out)
5. **Target pill remove**: Scale 1→0 + fade (150ms ease-in)
6. **Result sections**: Slide down + fade in, staggered (100ms per section)
7. **Confidence bars**: Width animates from 0% to final value (600ms ease-out-cubic)
8. **Tier color**: Bars start gray, transition to tier color as they fill
9. **Face/Photo toggle**: Cross-fade (300ms), photos scale slightly
10. **Hide/show face**: Height collapses smoothly (300ms), chip slides in
11. **Compare button pulse**: Subtle pulse animation when both slots filled but no results yet
12. **Loading state**: Skeleton UI with shimmer effect while comparing

### Visual Design

- **Color palette**: Match existing dark theme but with more contrast in results area
- **Typography**: Larger face section headers, smaller context text
- **Spacing**: More generous padding, clear visual hierarchy
- **Cards**: Subtle borders with hover states (lift shadow on hover)
- **Confidence bars**: Rounded ends, inner glow on tier color
- **Icons**: Consistent icon set for Upload/Person/Photo tabs

### Tests
- Visual regression: screenshot comparison workspace in all states
- Animation timing: verify no janky transitions on slow 3G simulation

Commit: `style(compare): animations and visual polish — fluid transitions, skeleton loading, tier colors`

---

## Phase 5: Context & Intelligence (30 min)

### Per-match context generation

For each comparison cell, compute and display:
1. **Target's best match**: "Isaac Cohen's best existing match is 92% (Haim Capelouto)"
2. **Rank among target's matches**: "This face ranks #3 among Isaac's matches"
3. **Relative strength**: If source face > target's best: "Better than any existing match!" (highlight)
4. **Cross-target insight**: If Face 1 matches Target A at 85% AND Target B at 82%:
   "Note: Face 1 strongly matches both Isaac and Barouh (they may be related)"

### Smart defaults
- If source has 1 face: skip face section headers, show bars directly
- If only 1 target: skip target labels on bars, show name in header
- If "All Archive" selected: group results by tier (Strong > Possible > Unlikely)
- If all scores are "Unlikely": show empathetic message + suggest uploading a clearer photo

### Tests
- Test context generation for various score ranges
- Test smart defaults for single-face, single-target, all-archive modes

Commit: `feat(compare): contextual intelligence — relative rankings, cross-target insights, smart defaults`

---

## Phase 6: Tests & Regression (45 min)

### New tests (target: 30+ new compare tests)

**Backend**:
- `test_compare_execute_person_vs_person` — two people compared
- `test_compare_execute_photo_vs_person` — archive photo vs person
- `test_compare_execute_upload_vs_person` — uploaded photo vs person
- `test_compare_execute_person_vs_photo` — person vs archive photo
- `test_compare_execute_photo_vs_photo` — two archive photos
- `test_compare_execute_upload_vs_upload` — two uploaded photos
- `test_compare_execute_multi_target` — 3 targets at once
- `test_compare_execute_all_archive` — source vs entire archive
- `test_compare_search_includes_inbox` — unidentified people in results
- `test_compare_search_includes_photos` — photos in search results
- `test_compare_context_generation` — relative ranking context

**UI**:
- `test_compare_workspace_renders` — empty state
- `test_compare_workspace_source_upload` — upload tab
- `test_compare_workspace_source_person` — person tab
- `test_compare_workspace_source_photo` — photo tab
- `test_compare_workspace_multi_target` — add/remove targets
- `test_compare_workspace_face_photo_toggle` — view toggle
- `test_compare_workspace_hide_face` — hide/show functionality
- `test_compare_workspace_responsive` — mobile viewport

**Backward compat**:
- `test_compare_result_page_still_works` — shareable links
- `test_compare_url_params_populate_slots` — ?photo_id=X&person_id=Y
- `test_compare_pair_redirects` — /compare/pair → /compare

**Regression**: Run `make test-fast` — all existing tests still pass.

Commit: `test(compare): 30+ new tests — all entity combinations, multi-target, workspace UI`

---

## Phase 7: Production Verification + Assessment (45 min)

### Deploy
- `git push origin main` (Railway auto-deploys)
- Wait for deploy completion (check Railway dashboard)

### Browser verification (Chrome plugin — admin is logged in)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 1 | Workspace loads | Navigate to /compare | Two-slot workspace visible |
| 2 | Upload source | Upload photo in source slot | Photo + face thumbnails appear |
| 3 | Person source | Search "Isaac Cohen" in person tab | Isaac selected, faces shown |
| 4 | Photo source | Browse photos, select one | Photo + faces shown |
| 5 | Add target person | Search "Haim" in target slot | Pill appears with face crop |
| 6 | Multi-target | Add 2nd person to targets | Both pills visible |
| 7 | Results render | After source + targets set | Matrix results with bars |
| 8 | Face/Photo toggle | Click "Photos" view | Full photos with overlays |
| 9 | Hide face | Click hide on Face 3 | Section collapses, chip appears |
| 10 | Animations | Observe transitions | Smooth, no jank |
| 11 | Shareable link | Click Share → open in incognito | Full results visible |
| 12 | URL params | /compare?photo_id=X&person_id=Y | Auto-populated |
| 13 | Mobile | Resize to 375px | Stacked layout works |
| 14 | Search unidentified | Search "unidentified" | INBOX identities appear |

Screenshots saved to `docs/screenshots/session-85c/`

### Assessment
Write `docs/assessments/session-85c-assessment.md`:
- What shipped (with evidence per phase)
- What was deferred (with reason + BACKLOG entry)
- Red flags (with severity)
- Next session should verify

### Updates
- ROADMAP.md — update Compare status, add to Recently Completed
- CHANGELOG.md — v0.88.0 entry
- BACKLOG.md — close resolved items, add any new items
- ALGORITHMIC_DECISIONS.md — AD entries for new architecture decisions
- SESSION_LOG.md + session log archive

Commit: `docs(session): session 85c assessment, roadmap, changelog updates`

---

## Architectural Constraints

1. **No ML model changes** — use existing InsightFace + SimilarityCalibrator
2. **No GPU on Railway** — face detection runs in background thread (existing pattern)
3. **Keep /facecompare unchanged** — different audience (standalone, no auth)
4. **Keep /compare/result/{id} working** — shareable links must not break
5. **HTMX-first** — no React, no heavy JS frameworks. CSS transitions for animations.
6. **Existing dark theme** — enhance, don't replace the color palette
7. **AD-110** — web requests never run heavy ML synchronously
8. **Lesson 88** — app/main.py is a monolith; all compare UI changes are in one file

## Success Metrics

1. All 9 entity type combinations work (3 source × 3 target types)
2. Multi-select targets (up to 5) with instant comparison
3. Face/photo toggle with smooth cross-fade
4. Hide/collapse individual face sections
5. Search includes unidentified people and photos
6. Confidence bars animate smoothly
7. Context per match: relative ranking + target's best existing match
8. Upload → results faster than FamilySearch (target: <5s for processing)
9. Mobile responsive at 375px
10. All existing shareable links still work
11. 30+ new tests, all passing
12. Production browser verification: 14/14 PASS
