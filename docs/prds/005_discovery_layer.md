# PRD: Discovery Layer — Surface Intelligence, Capture Corrections

**Author:** Nolan Fox
**Date:** 2026-02-14
**Status:** Draft
**Session:** 27

---

## Problem Statement

The archive has 250 photos with rich AI-generated metadata (scene descriptions, date estimates, OCR text, tags, clothing notes) stored in `photo_search_index.json` and `date_labels.json`. None of this intelligence is visible in the UI. Users can't search by content ("wedding", "outdoor"), filter by decade, see estimated dates, or correct AI mistakes. The ML pipeline generates data that sits unused.

**Who is affected:**
- Family members browsing the archive (can't find photos by topic or era)
- Admin reviewing AI quality (no visibility into what the model estimated)
- ML pipeline (no correction signal to improve future labeling)

**Why now:** 250 photos labeled, CORAL model trained, search index exported. The data exists — it just needs a UI.

---

## Who This Is For

| Role | Relationship to Feature |
|------|------------------------|
| Anonymous visitor | Sees date badges, searches/filters, views AI analysis (read-only) |
| Logged-in user | All above + can submit corrections |
| Guest (anonymous contributor) | Can submit corrections (go to review queue) |
| Admin | All above + review queue for prioritized corrections |

---

## Feature 1: Date Badges on Photo Cards

### User Flow
1. User visits `/photos` (public browse page)
2. Each photo card shows a date badge in the bottom-left corner: "c. 1930s"
3. Badge opacity/style reflects AI confidence:
   - High confidence: solid background (`bg-amber-700/80`)
   - Medium confidence: outlined/faded (`bg-amber-700/50 border border-amber-600/50`)
   - Low confidence: dashed outline only (`border border-dashed border-amber-600/40 text-amber-400/60`)
4. Hovering the badge shows a tooltip: "Best estimate: 1935 (range: 1930–1940)"
5. Photos without labels show no badge (not "Unknown")

### Data Source
- `data/date_labels.json` → keyed by `photo_id`
- Fields used: `estimated_decade`, `best_year_estimate`, `confidence`, `probable_range`

### Technical Notes
- Load date_labels.json into a `_date_labels_cache` dict at startup (keyed by photo_id)
- Badge renders server-side. Tooltip via `title` attribute (no JS needed)
- Badge must not obscure face count badge (top-right) — date goes bottom-left
- Applies to both `/photos` public page and admin photos section

---

## Feature 2: Photo Detail Metadata Panel

### User Flow
1. User views a photo at `/photo/{id}` (public page) or in the admin photo modal
2. Below the person cards, a new "AI Analysis" section appears
3. Section header shows a sparkle icon and "Estimated by AI — help us verify"
4. Subsections (all collapsible via `<details>`, first expanded):
   a. **Date Estimate**: "circa 1935" + confidence level + probable range bar
   b. **Scene**: scene_description text (2-3 sentences)
   c. **Visible Text**: visible_text if non-empty (OCR of inscriptions)
   d. **Tags**: controlled_tags as styled pill chips
   e. **Dating Evidence**: reasoning_summary (what visual cues were used)
   f. **Subject Ages**: estimated ages list
5. Each subsection has a small pencil icon for corrections (Feature 4)
6. AI-estimated fields have a subtle blue-gray left border
7. Human-verified fields (after correction) show a checkmark with gold/green border

### Data Source
- `rhodesli_ml/data/date_labels.json` (full Gemini output) → load into `_date_labels_cache`
- Fields: `scene_description`, `visible_text`, `keywords`, `controlled_tags`, `reasoning_summary`, `subject_ages`, `estimated_decade`, `best_year_estimate`, `confidence`, `probable_range`, `evidence`

### Visual Language
- **AI-estimated**: `border-l-2 border-indigo-500/40 bg-indigo-950/20` + sparkle text
- **Human-verified**: `border-l-2 border-emerald-500/40 bg-emerald-950/20` + checkmark

---

## Feature 3: Decade Filtering + Keyword Search + Tag Filtering

### User Flow: Decade Pills
1. User visits `/photos`
2. Above the photo grid, a row of clickable decade pills appears:
   "All" | "1900s (2)" | "1910s (13)" | "1920s (35)" | ... | "1980s (7)"
3. Clicking a pill filters the gallery to that decade
4. Multiple pills can be selected (OR logic within decades)
5. "All" clears decade filters
6. HTMX swaps the grid without full page reload

### User Flow: Keyword Search
1. A search input appears above the grid (next to filters)
2. User types "wedding" → server searches `searchable_text` field
3. Results show matching photos with a small "Matched: scene description" label
4. Empty search shows all photos
5. Search + decade filter combine with AND logic

### User Flow: Tag Filtering
1. A dropdown or pill row shows top controlled_tags with counts:
   "Studio (114)" | "Group Portrait (131)" | "Wedding (23)" | ...
2. Clicking a tag filters to photos with that tag
3. Tags combine with AND logic with decade and search

### Data Source
- `data/photo_search_index.json` → loaded into `_search_index_cache` at startup
- Fields: `searchable_text`, `controlled_tags`, `estimated_decade`, `photo_id`

### Technical Notes
- In-memory Python search: iterate documents, substring match on `searchable_text`
- At 250 docs, this is <1ms. No database needed.
- **Scaling decision**: When archive exceeds 1000 photos, migrate to SQLite FTS5. Document this threshold.
- HTMX: pills/search submit via `hx-get="/photos"` with query params, swap `#photo-grid`
- Preserve existing collection filter and sort — all filters combine with AND
- The `/photos` route gains new params: `decade`, `search_q`, `tag`

### Match Reason Display
- When search is active, each photo card shows a small label below:
  "Matched: scene" or "Matched: visible text" or "Matched: keywords"
- This builds trust in why a result appeared

---

## Feature 4: Correction Flow

### User Flow
1. User views photo detail (Feature 2 metadata panel)
2. Next to each AI field, a small pencil icon appears
3. User clicks pencil:
   - **Date**: inline input for year + decade dropdown
   - **Tags**: add/remove tag interface (checkboxes from controlled_tags enum)
   - **Scene/Visible Text**: textarea for editing
4. User submits correction
5. System:
   - Archives old AI value in `data/corrections_log.json`
   - Updates the field source to `"human"` with contributor info
   - Visual transition: blue/sparkle → green/checkmark styling
   - Toast: "Thanks! Your correction helps improve our AI."
6. Admin can review all corrections at `/admin/corrections`

### Auth Requirements
- Logged-in users: corrections apply immediately (auditable)
- Guest users: corrections go to pending review queue (like annotations)
- Anonymous: pencil icon triggers login prompt modal

### Data Model

**New file: `data/corrections_log.json`** (append-only)
```json
{
  "schema_version": 1,
  "corrections": [
    {
      "id": "corr_uuid",
      "photo_id": "a3d2695fe0804844",
      "field": "estimated_decade",
      "old_value": 1930,
      "new_value": 1940,
      "old_source": "gemini",
      "new_source": "human",
      "contributor_email": "user@example.com",
      "contributor_type": "registered",
      "status": "applied",
      "timestamp": "2026-02-14T12:00:00Z"
    }
  ]
}
```

**Modified: `rhodesli_ml/data/date_labels.json`**
- When correction applied, update the field value and set `source` to `"human"`

**Modified: `data/photo_search_index.json`**
- Regenerated after corrections to reflect updated values

### Correctable Fields
- `estimated_decade` / `best_year_estimate` → date correction
- `controlled_tags` → tag add/remove
- `scene_description` → text correction
- `visible_text` → text correction

### ML Feedback Loop
- Corrected dates become ground truth for future CORAL training
- `source="human"` labels override `source="gemini"` in training pipeline

---

## Feature 5: Active Learning Priority Queue (Admin Only)

### Priority Scoring

```python
correction_priority_score = (
    (1.0 - confidence_numeric) *      # low confidence = high priority
    range_width_normalized *           # wide date range = high priority
    (1.0 + temporal_conflict_flag)     # temporal impossibility = 2x boost
)
```

Where:
- `confidence_numeric`: high=0.9, medium=0.6, low=0.3
- `range_width_normalized`: (range_end - range_start) / 50
- `temporal_conflict_flag`: 1 if `audit_temporal_consistency.py` flagged this photo

### User Flow (Admin)
1. Admin visits `/admin/review-queue`
2. Photos sorted by `correction_priority_score` (highest first)
3. Each card shows:
   - Photo thumbnail
   - Current AI estimate with confidence
   - Why flagged: "Wide date range (1910-1950)" or "Low confidence" or "Temporal conflict"
4. Quick-action buttons:
   - "Confirm AI Estimate" → sets `source="human"` (validates AI was right)
   - "Correct" → opens correction form (Feature 4)
5. "Confirm" and "Correct" both count as human verification

### Data
- Script: `rhodesli_ml/scripts/calculate_correction_priority.py`
- Output: `data/correction_priorities.json`
- Route: `/admin/review-queue` (admin-only)

---

## Acceptance Criteria (Playwright Tests)

```
TEST 1: Photo card shows date badge
  - Visit /photos
  - Assert: at least one photo card contains text matching "c. \d{4}s"

TEST 2: Date badge reflects confidence
  - Visit /photos
  - Assert: high-confidence badges have solid background class
  - Assert: low-confidence badges have dashed border class

TEST 3: Photo detail shows metadata panel
  - Visit /photo/{known_photo_id}
  - Assert: page contains "AI Analysis" section
  - Assert: page contains "Scene" subsection with text content
  - Assert: page contains tag pills

TEST 4: Decade filter pills displayed with counts
  - Visit /photos
  - Assert: page contains decade pills ("1920s", "1930s", etc.)
  - Assert: pills show photo counts in parentheses

TEST 5: Decade filter filters gallery
  - Visit /photos
  - Click "1920s" pill
  - Assert: all visible photo cards have 1920s date badges
  - Assert: URL contains decade=1920

TEST 6: Keyword search returns results
  - Visit /photos
  - Enter "wedding" in search box
  - Assert: results appear
  - Assert: results show match reason text

TEST 7: Search + decade filter combine
  - Visit /photos with decade=1930 and search_q=outdoor
  - Assert: results are intersection (1930s AND outdoor)

TEST 8: Correction flow updates source
  - Log in as admin
  - Visit /photo/{id}
  - Click pencil on date field
  - Enter new year
  - Submit
  - Assert: field now shows "Verified" styling (not "AI Estimated")

TEST 9: Correction logged
  - After TEST 8
  - Assert: corrections_log.json contains the correction entry

TEST 10: Provenance visual distinction
  - Visit /photo/{id} with a corrected field
  - Assert: corrected field has emerald/green border class
  - Assert: uncorrected field has indigo/blue border class

TEST 11: Admin review queue sorted by priority
  - Log in as admin
  - Visit /admin/review-queue
  - Assert: photos are listed
  - Assert: first photo has higher priority score than last

TEST 12: Tag filter works
  - Visit /photos
  - Click "Studio" tag filter
  - Assert: visible photos are filtered
```

---

## Data Model Changes

### New Files
| File | Purpose | Tracked in git? | In sync lists? |
|------|---------|-----------------|----------------|
| `data/corrections_log.json` | Append-only correction log | Yes (.gitignore whitelist) | No (production-origin, like annotations) |
| `data/correction_priorities.json` | Scored priority list | Yes | OPTIONAL_SYNC_FILES |

### Modified Files
| File | Change |
|------|--------|
| `rhodesli_ml/data/date_labels.json` | `source` field updated on correction |
| `data/photo_search_index.json` | Regenerated after corrections |

### New Caches (in-memory, app startup)
| Cache | Source | Invalidation |
|-------|--------|-------------|
| `_date_labels_cache` | `rhodesli_ml/data/date_labels.json` | On correction submit |
| `_search_index_cache` | `data/photo_search_index.json` | On correction submit |
| `_correction_priorities_cache` | `data/correction_priorities.json` | On correction/confirm |

---

## Technical Constraints

1. **FastHTML + HTMX**: All rendering is server-side. No React/SPA.
2. **In-memory search**: Python substring matching at 250 docs. No external search engine.
3. **Scaling threshold**: 1000 photos → migrate to SQLite FTS5.
4. **Vanilla JS only**: Tooltips, pill toggles — no JS frameworks.
5. **corrections_log.json is production-origin**: Like annotations.json, it must NOT be in deploy sync lists. It flows production→local via a pull endpoint.
6. **date_labels.json lives in rhodesli_ml/data/**: Not in app data/ dir. Load from ML path.

---

## Out of Scope

1. **Timeline visualization** — Needs 500+ photos and user demand signal. Prerequisite: decade filtering exists first (Feature 3).
2. **Map view** — Gemini `location_estimate` is unstructured text, not lat/long. Needs geocoding pipeline.
3. **Probability distribution rendering** — Premature at 250 photos. Unclear user value vs decade-level granularity.
4. **Confidence heatmap mode** — Nice visualization but low user impact. Build after correction flow proves engagement.
5. **Generational spread view** — Requires many identified people with multiple photos across decades.
6. **Decade auto-narrative** — Delight feature. Build after core discovery works.
7. **Photo comparison tool** — Engagement feature, not core discovery.
8. **Smart geocoding** — Action NOW: add `location_structured` field to Gemini prompt for future runs. Document as AD-057.

---

## Priority Order

If session runs out of context:

1. **Feature 1: Date Badges** — Highest visual impact, zero new routes, data already exists
2. **Feature 3: Decade Filtering** — Makes the archive navigable by era
3. **Feature 2: Metadata Panel** — Surfaces AI intelligence on detail pages
4. **Feature 4: Correction Flow** — Enables human feedback loop
5. **Feature 5: Review Queue** — Admin-only optimization tool

---

## Algorithmic Decisions

- **AD-056**: Discovery Layer architecture — in-memory search, correction flow, provenance visual system
- **AD-057**: Deferred features with rationale (map, timeline, probability rendering, geocoding prep)
- **AD-058**: Active learning priority scoring formula
