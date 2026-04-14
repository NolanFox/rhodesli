# Session 149 — Gemini Event Context Analyzer + Investigation Schema

**Mode:** Implementation (autonomous)
**Predecessor:** Session 148c (Fader identification + methodology learnings)
**Context:** `docs/session_context/session-149-context.md`

## Orientation

Read at session start:
- `docs/session_context/session-149-context.md` — full context with research findings
- `docs/session_context/session-148c-learnings.md` — methodology learnings driving this work
- `docs/session_context/session-148c-api-schema-proposal.md` — full schema proposal
- `tasks/lessons.md` + `tasks/todo.md`
- `ROADMAP.md` current state

Set session: `echo "149" > .claude/current_session.txt && echo "implementation" > .claude/session_mode.txt`
Baseline: `source venv/bin/activate && make test-fast`

---

## Phase 1: Identification Investigations Table (DATA-FMT-001) (~30 min)

### 1a: Create Supabase table
- Run the CREATE TABLE from the schema proposal in Supabase SQL editor
- Fix `confirmed_identity_id` type: `text` not `uuid` (matches identities table)
- Add RLS policies matching `identity_suggestions` pattern
- Add indexes: target_name, session_id, outcome, community_id, GIN on candidates

### 1b: Supabase read/write helpers
- Add `log_identification_investigation()` to `app/supabase_data.py`
  - Follow `log_gemini_api_call()` pattern: dict construction, try/except, logger warning
- Add `get_investigations_for_family(target_name)` to retrieve past investigations
- Add `get_investigation(investigation_id)` for single lookup
- Tests: write + read round-trip, missing fields handled, community scoping

### 1c: Backfill Session 148c data
- Write a script `scripts/backfill_investigation_148c.py` that reads `session-148c-investigation.json` and inserts it into the new table
- Run it once to populate the first row
- Verify with a SELECT query

**Commit after Phase 1. /clear.**

---

## Phase 2: Extend Gemini Extraction with Event Context (~45 min)

**CRITICAL FINDING from Session 148c research:** Most of this already exists in `rhodesli_ml/gemini_extraction.py`. The existing system already extracts date estimation, face analysis (age/gender/description), clothing era, group composition, and face coordinates in a single API call per photo. We do NOT need a new function — we need to extend the existing preset system.

### 2a: Add event_context + relationship_inference to extraction schema
- Read `rhodesli_ml/gemini_extraction.py` to understand `build_extraction_prompt()` and preset system
- Add two new extraction sections to the schema:
  ```
  event_context: {
    event_type: wedding_ceremony|wedding_reception|bar_mitzvah|funeral|
                holiday|school|military|casual|portrait|formal_dinner|party,
    event_subtype: string (e.g. "head table dinner", "aisle walk"),
    role_indicators: [{face_index, roles: [bride|groom|mother_of_bride|
                      father_of_bride|mother_of_groom|father_of_groom|
                      bridesmaid|best_man|officiant|guest]}],
    formality_level: very_formal|formal|semi_formal|casual|intimate
  }
  relationship_inference: {
    couple_pairs: [{face_indices: [i,j], confidence: float, evidence: string}],
    parent_child_pairs: [{parent_index: i, child_index: j, confidence: float}],
    positioning_notes: string
  }
  ```
- Add these to a new preset "identification" or extend the "full" preset
- Face bounding box coordinates are ALREADY supported via `face_coordinates` parameter

### 2b: Update prompt template
- Add event context and relationship inference sections to `build_extraction_prompt()`
- Expand the `controlled_tags` taxonomy to include wedding-specific event types
- Use existing `face_coordinates` injection — no new plumbing needed

### 2c: Tests
- Unit test with mocked Gemini response including new fields
- Test that "identification" preset includes event_context and relationship_inference
- Test backward compatibility — existing "full" preset still works unchanged
- Test structured response parsing for new fields (valid JSON, missing fields handled)

**Commit after Phase 2. /clear.**

---

## Phase 3: Validate on Fader Wedding Photos (~30 min)

### 3a: Run analyzer on 5 key photos
- Select the 5 wedding photos from Session 148c investigation:
  1. Parents portrait (F8B131D2) — should detect: wedding, corsage, boutonniere
  2. Ceremony aisle (0FBD3088) — should detect: wedding ceremony, escort, veil
  3. Head table (A08EAB11) — should detect: wedding reception, head table, formal
  4. Father-daughter dance (2C303F28) — should detect: wedding, dance, formal
  5. Couple portrait (887E6899) — should detect: wedding, couple, formal
- Include known people (Sherry, Ira, Al Fader, Nellie Kubrin) as context
- Log all API calls to `gemini_api_calls`

### 3b: Evaluate results
- Compare Gemini's event analysis to our manual findings from Session 148c
- Does it correctly identify: event type? role indicators? age estimates?
- Log discrepancies and accuracy assessment
- Total cost for 5 calls

### 3c: Store results
- Write event context results to a new `event_context` JSONB column on `date_labels` table
  OR create a separate `photo_event_context` table (decide based on data model fit)
- Results should be queryable per-photo

**Commit after Phase 3. /clear.**

---

## Phase 4: Wire to Investigation Workflow (~20 min)

### 4a: Link event context to investigations
- When creating an investigation, auto-retrieve event context for photos containing the target person
- Add event context as a signal in the investigation candidates assessment
- Update the investigation JSON schema to include `event_context_summary` per-candidate

### 4b: Admin endpoint for on-demand analysis
- `POST /api/admin/analyze-event-context/{photo_id}` — runs Gemini event analyzer on a single photo
- Returns structured results + stores in DB
- Admin-only, logged to `gemini_api_calls`

### 4c: Display event context on photo page (optional stretch)
- Show event type badge on photo page (e.g., "Wedding Reception · ~1965")
- Show role indicators next to face overlays if available
- Only if time permits — skip if running long

**Commit after Phase 4. /clear.**

---

## Phase 5: Session Close

Standard harness:
1. Assessment: `docs/assessments/session-149-assessment.md`
2. CHANGELOG: increment to v0.99.64
3. ROADMAP + BACKLOG: update, close DATA-FMT-001 and FEATURE-F1
4. Deploy: `git push origin main`, verify health 200
5. Browser verify: estimate page, photo pages with event context
6. `git log origin/main..HEAD` must be empty
7. Memory backup: `./scripts/backup-memory.sh`
8. Run /session-review skill

## Parallelization Notes
- Phase 1 (schema) and Phase 2 (prompt engineering) are INDEPENDENT — can run in parallel worktrees
- Phase 3 depends on Phase 2 (needs the analyzer function)
- Phase 4 depends on both Phase 1 (investigation table) and Phase 3 (event context data)

## Success Criteria
- [ ] `identification_investigations` table exists in Supabase with Session 148c data backfilled
- [ ] `analyze_event_context()` function works with mocked and real Gemini calls
- [ ] 5 Fader wedding photos analyzed with event context matching manual findings
- [ ] Event context stored in queryable format
- [ ] Admin endpoint for on-demand analysis
- [ ] All tests pass, deployed, browser verified
