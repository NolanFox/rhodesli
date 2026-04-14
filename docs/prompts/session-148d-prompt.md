# Session 148d — Fix Codex Findings + Gemini Prompt Refinement + Deploy

**Mode:** Implementation (autonomous)
**Predecessor:** Session 149 (infrastructure built), Session 148c (methodology)
**Context:** `docs/session_context/session-148d-context.md`

## Phase 1: Fix Codex Findings (~15 min)

### 1a: Fix RLS policy (P1)
- Edit `scripts/migrations/create_identification_investigations.sql`
- Change SELECT policy from `auth.role() = 'authenticated' OR auth.role() = 'service_role'` to `auth.role() = 'service_role'` only

### 1b: Fix admin endpoint (P2+P3)
- `app/admin_routes.py` endpoint at line 5061:
  - Add `_check_origin(request)` after `_check_admin(sess)`
  - Sort face_coordinates by bbox[0] after loading from Supabase
  - Replace the complex async body parsing with FastHTML form parameter: add `known_people: str = ""` to function signature, parse as JSON if non-empty

### 1c: Tests
- Add test for CSRF check (origin validation)
- Add test for face coordinate sorting
- Verify existing 17 tests still pass

**Commit.**

## Phase 2: Gemini Prompt Refinement (~30 min)

### 2a: Restructure extraction prompt for compliance
- The current prompt adds sections but Gemini ignores nested objects it hasn't seen before
- Option A: Use Gemini `response_schema` parameter to enforce structure
- Option B: Restructure prompt to explicitly request the fields in a way the model responds to
- Try Option A first — it's the most reliable

### 2b: Update call_gemini or create identification-specific caller
- The existing `call_gemini()` in generate_date_labels.py doesn't pass `response_schema`
- Either: extend it to accept an optional schema parameter, OR create a new `call_gemini_with_schema()` wrapper
- The admin endpoint should use the schema-enforced version

### 2c: Validate on 5 Fader photos again
- Run the same 5 photos with the schema-enforced prompt
- Verify event_context and relationship_inference fields are now populated
- Compare to Session 148c manual findings
- Save results to `docs/session_context/session-148d-gemini-validation.json`

### 2d: Tests
- Test prompt with response_schema produces expected structure
- Test backward compatibility (existing presets without schema still work)

**Commit.**

## Phase 3: Execute Supabase Migration + Backfill (~10 min)

### 3a: Create table
- The SQL can't be run from CLI — write a Python script that executes it via Supabase client
- OR document the exact SQL to paste into Supabase dashboard
- Create the table

### 3b: Run backfill
- Execute `scripts/backfill_investigation_148c.py`
- Verify with SELECT query

### 3c: Verify round-trip
- Call `get_investigation()` and `get_investigations_for_family("Nellie Kubrin")`
- Confirm data matches

**Commit.**

## Phase 4: Deploy + Verify (~10 min)

- `git push origin main`
- Verify health 200
- Test admin endpoint on production: `curl -X POST .../api/admin/analyze-event-context/{photo_id}`
- Browser verify Compare Faces modal merge button still works (Session 148c fix)

## Phase 5: Session Close

Standard harness: assessment, CHANGELOG, session log, Codex audit.

## Success Criteria
- [ ] All 4 Codex findings fixed with tests
- [ ] Gemini returns event_context + relationship_inference on real photos
- [ ] identification_investigations table exists in Supabase with 148c data
- [ ] Admin endpoint works on production
- [ ] All tests pass, deployed
