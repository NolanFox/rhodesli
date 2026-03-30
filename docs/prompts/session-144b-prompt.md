# Session 144b: Bug Fixes + Batch Completion + Temporal Co-Occurrence

## Context
Session 144 delivered GEDCOM import, context enrichment, 218/279 batch photos, and identity investigation.
See `docs/session_context/session-144b-context.md` for full predecessor context.

## Approach
This session runs autonomously. Follow all harness rules in `.claude/rules/`. Codex audit after every phase. /clear between phases. Assessment + ROADMAP + BACKLOG + CHANGELOG at end.

## Phase 0: Bug Fixes (SEQUENTIAL — Tracks 0a and 0b both touch page_routes.py)

### 0a: FB-007 Person Page Sort by Estimated Date (P1)
- **Bug**: "Sort: Earliest First" on person page doesn't sort by Gemini estimate
- **File**: `app/page_routes.py` — search for sort logic near photo gallery
- **Likely cause**: date_labels not loaded or `best_year_estimate` not used as sort key
- **Steps**:
  1. Trace the sort dropdown handler — what field does "Earliest First" sort by?
  2. Verify date_labels are loaded from Supabase for the person's photos
  3. If sorting by upload_date instead of best_year_estimate, fix the sort key
  4. Test: Albert Fox (199 photos spanning 1910s-1980s) should show 1910s photos first
  5. Add test for sort ordering
- **Browser verify**: Albert's person page with "Earliest First" selected

### 0b: 0% Display Bug for Family Resemblance (P1) — AFTER 0a commits
- **Bug**: Matches in the 20-35% confidence range display as "0% match"
- **Codex finding**: Unified scorer gives 27%, calibrator gives 32%, but UI shows 0%. Likely stale/alternate display path or floor/truncation.
- **Steps**:
  1. Search for confidence display formatting in identity_routes.py, page_routes.py, main.py
  2. Find where "0% match" badge is generated — check if it truncates/floors values
  3. Check if "Manual Search" uses a different scorer than "Find Similar"
  4. Fix: ensure calibrated confidence is displayed consistently
  5. Test: verify 27% displays as "27% match" not "0% match"
- **NOTE**: Do NOT touch page_routes.py until 0a is committed and merged

### 0c: Person 3481 Multi-Claimed Faces (Data Repair — PARALLEL with 0a)
- **Bug**: 3 faces from penny arcade strip claimed by Persons 3481, 3485, 3486
- **All 3 faces should belong ONLY to Person 3481** (identity_id: `273ac560-bf13-43f5-8f87-e0f7ec967b2c`)
- **Person 3485**: identity_id from `data/identities.json` (search for "Unidentified Person 3485")
- **Person 3486**: identity_id from `data/identities.json` (search for "Unidentified Person 3486")
- **Face IDs**: `inbox_0f38fc4ed157`, `inbox_a9836b90601f`, `inbox_ecd034168ebc`
- **Steps**:
  1. Snapshot anchor_ids for all 3 identities BEFORE changes
  2. Remove face IDs from 3485 and 3486's anchor_ids in Supabase
  3. Verify 3481 has all 3 faces, 3485/3486 have none
  4. If 3485/3486 are now empty, consider merging them into 3481

## Phase 1: Batch Completion (SEQUENTIAL — after Phase 0)

### 1a: Determine Actual Remaining Photos (query-derived, not hardcoded)
- Do NOT trust hardcoded counts. Run this query to find the real worklist:
  ```python
  # Get all Albert+Esther photo IDs
  # Compare against date_labels with gedcom_context_sent=true
  # The difference is the worklist
  ```
- The approximate count is ~61, but verify by query

### 1b: Canary Run (3 photos — verify before bulk)
- Re-run 3 already-labeled photos and compare output quality
- **Must verify**: spouse timeline in GEDCOM context, structured geo with candidates, face analysis
- Compare side-by-side: old estimate vs new estimate
- Only proceed to bulk if canary quality is good

### 1c: Run Remaining Photos
- Budget: ~$4.00 (enough for ~72 photos)
- Command:
  ```bash
  python scripts/batch_gemini_for_person.py \
    --identity "85546ebf-75b9-4971-a9d4-b2ce2271bc19" \
    --identity "65207728-9ee6-48c1-be68-a2da23354caf" \
    --skip-existing --max-cost 4.00
  ```
- **Verify first result**: `gedcom_context_sent: True`
- All results write to Supabase (Lesson 162)
- Note: 2-3 photos may be R2-only (no local file). These can be skipped — they need R2 download first, and there is no `download_from_r2.py` script. Log as BACKLOG.

### 1d: Verify Complete Coverage (SCOPED to Albert+Esther)
- Query Albert+Esther's photo IDs from identities table
- For each, check date_labels has an entry with `gedcom_context_sent: true`
- Report: "X/Y Albert photos covered, X/Y Esther photos covered"
- Any gaps → investigate and re-run

## Phase 2: PRD-059 Temporal Co-Occurrence — Extend Existing Event Grouping

### CRITICAL: Existing Code Exists — Do NOT Start From Scratch
- `scripts/event_grouping.py` — existing event clustering algorithm (Session 142)
- `app/temporal_routes.py` — existing admin event-groups page
- `rhodesli_ml/data/event_groups.json` — existing output (STALE — references Person 3772)
- `scripts/sql/create_life_events.sql` — existing event schema

**Read ALL of these files first before writing any code.**

### 2a: Regenerate Event Groups with Updated Data
- The existing `event_grouping.py` uses **5-year windows** (not ±2 years — Codex found ±2 causes snowball chains)
- Re-run event grouping with the 218 new date estimates
- Output must reference current identities (Person 3772 is now Albert Fox)
- Write updated `event_groups.json` + sync to Supabase

### 2b: Enhance Person Timeline UI
- The existing `temporal_routes.py` serves an admin page
- Enhance: add a "Timeline" tab on the person page (`app/page_routes.py`)
- Show events as chronological groups with photo thumbnails
- "Frequent Companions" sidebar: who appears most often with this person
- This ties into the sort fix from Phase 0a

### 2c: Co-Occurrence Matrix (PRD-059 Phase 3)
- For each confirmed identity, compute: which other confirmed identities appear in the most shared photos
- Store as a co-occurrence matrix or adjacency list
- Display on person page: "Often appears with: Esther Burd Fox (52 photos), Rose Weiss Baygel Fox (12 photos)"

### Tests
- Event grouping: verify 5-year window clustering with shared faces
- Timeline rendering: verify HTML with event cards
- Co-occurrence: verify matrix computation and display
- Sort integration: verify "Earliest First" uses date estimates after event grouping

## Phase 3: Geo Dual-Write + Anchor Verify (PARALLEL with Phase 2)

### 3a: Geocode + Dual-Write
- For each photo with `location_primary` in date_labels:
  1. Geocode using existing `scripts/geocode_photos.py`
  2. Write to `photo_locations` table (the map reads from this table)
- Verify: map pins appear for batch-processed photos

### 3b: Anchor Compare Browser Verify
- Navigate to a photo page with the anchor compare panel
- Test the flow: enter anchor photo ID, click Compare, view results
- Screenshot evidence required (Lesson 97)

## Phase 4: Session Close (MANDATORY)

### 4a: Harness Compliance
- Assessment: `docs/assessments/session-144b-assessment.md`
- CHANGELOG: increment version
- ROADMAP: update PRD-059 status (Phase 2 complete? Phase 3 started?)
- BACKLOG: close done items, add new items (including SORT-001 if not already there)
- SESSION_HISTORY: add session entry
- Deploy: `git push origin main`, verify health 200
- Browser verify: landing, person page (Albert), timeline, map
- `git log origin/main..HEAD` must be empty

### 4b: Verification Gate
- Re-read this prompt file
- For each phase, verify artifacts exist and tests pass
- Fix any FAIL before declaring complete

## Codex Audit Strategy

| After Phase | Scope | Block on P0/P1? |
|-------------|-------|-----------------|
| Phase 0 | Bug fixes — sort, display, data repair | Yes |
| Phase 1 | Batch output quality spot-check | Yes for first |
| Phase 2 | Event grouping rerun, timeline UI, co-occurrence | Yes |
| Phase 3 | Geo/anchor — security, data integrity | Yes |

## Parallelization Plan

| Track | Phase | Dependencies | Files |
|-------|-------|-------------|-------|
| Sequential | 0a: Sort fix | None | page_routes.py |
| Sequential | 0b: 0% display fix | After 0a commits | identity_routes.py, main.py |
| Track C (worktree) | 0c: 3481 data repair | None | Supabase only |
| Sequential | Phase 1: Batch completion | After Phase 0 | scripts/batch_gemini_for_person.py |
| Sequential | Phase 2: Event grouping + timeline | After Phase 1 | scripts/event_grouping.py, app/temporal_routes.py, app/page_routes.py |
| Track D (worktree) | Phase 3a: Geo dual-write | After Phase 1 | scripts/geocode_photos.py |
| Track E (worktree) | Phase 3b: Anchor verify | None | Browser only |

## Key Constraints
- **Budget**: ~$4.00 for remaining photos
- **Gemini quota**: 250 RPD on Tier 1
- **Browser verification MANDATORY** for: sort fix, timeline UI, anchor compare, map pins
- **Codex audit MANDATORY** after every phase
- Follow `batch-data-pipeline.md` for all outputs
- All data writes to Supabase (Lesson 162)
- No doc >300 lines (Lesson 106)
- **Face analysis name mapping only works for single-face photos** (Session 144 limitation)
- **event_groups.json is STALE** — references Person 3772 (merged into Albert). Must regenerate before any UI work.

## Key Risks
- Date labels may not be in Supabase for all 218 batch photos (verify before Phase 2)
- Event grouping uses 5-year windows to avoid snowball chains — do NOT use ±2-year naive clustering
- Parallel tracks must not touch the same files (page_routes.py is sequential)
- R2-only photos (2-3) need manual download — no automated script exists
