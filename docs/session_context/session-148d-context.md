# Session 148d Context — Fix Codex Findings + Gemini Prompt Refinement

## Predecessor
- Session 149: Built infrastructure (table, helpers, preset, endpoint, 79 tests)
- Session 148c: Identification methodology learnings

## What's Broken / Incomplete

### Codex Findings (from session-149-codex-audit.md)
1. **P1: RLS too permissive** — `identification_investigations` SELECT policy allows any authenticated user. Should be service_role only (admin data).
   - File: `scripts/migrations/create_identification_investigations.sql:29`
2. **P2: Face indices unsorted** — admin endpoint queries photo_faces without sorting by bbox x-coordinate. Role indicators map to wrong faces.
   - File: `app/admin_routes.py:5113`
3. **P2: known_people body parsing dead** — sync handler can't await request.body() under ASGI. verified_facts never built.
   - File: `app/admin_routes.py:5128-5156`
4. **P3: Missing _check_origin CSRF** — new POST route lacks origin check.
   - File: `app/admin_routes.py:5071`

### Gemini Prompt Gap
5. **P1: Model doesn't produce event_context/relationship_inference** — validation on 5 photos showed model returns old flat format. The prompt sections exist but Gemini ignores them. Need to use `response_schema` parameter for structured output enforcement OR restructure the prompt.
   - Evidence: `docs/session_context/session-149-gemini-validation.json`

### Infrastructure Not Executed
6. SQL migration not run in Supabase
7. Backfill script not run

## Key Files
- `scripts/migrations/create_identification_investigations.sql` — needs RLS fix then execution
- `app/admin_routes.py:5061` — endpoint needs 3 fixes (face sort, body parsing, CSRF)
- `rhodesli_ml/gemini_extraction.py` — prompt sections need restructuring for Gemini compliance
- `rhodesli_ml/scripts/generate_date_labels.py:196` — `call_gemini()` function
- `scripts/backfill_investigation_148c.py` — ready to run after table creation

## Gemini Structured Output Research
Gemini supports `response_schema` in `GenerateContentConfig` to enforce JSON structure. The existing `call_gemini()` uses `response_mime_type="application/json"` but no schema enforcement. Adding `response_schema` with the event_context and relationship_inference types should force the model to produce those fields.

See: https://ai.google.dev/gemini-api/docs/structured-output
