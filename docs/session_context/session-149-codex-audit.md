**Auditor**: Codex CLI v0.120.0 (gpt-5.4) + Claude Code self-audit
**Agent type**: Independent (fresh context)
**Phase**: Full session 149 audit
**Date**: 2026-04-14

## Codex CLI Findings

### P1 Findings (2)

**P1-1 (Codex): RLS policy too permissive on identification_investigations.**
Any authenticated Supabase user can read investigation data, not just admin/service_role. The SELECT policy should be `auth.role() = 'service_role'` only, since investigations contain admin-only identification methodology and candidate assessments.
**Fix:** Update SQL migration — change SELECT policy to service_role only.

**P1-2: Gemini model doesn't produce new extraction fields.**
The "identification" preset adds `event_context` and `relationship_inference` sections to the prompt, but validation on 5 real photos showed the model returns the old flat format without these nested objects. The prompt sections exist and tests pass with mocked data, but real API calls don't produce the expected output. This needs prompt refinement — possibly using Gemini's `response_schema` parameter for structured output enforcement.

**Action:** BACKLOG item for next session. The infrastructure (preset, prompt sections, admin endpoint, tests) is all in place — only the prompt template needs iteration.

### P2 Findings (3)

**P2-1: SQL migration not executed.**
`scripts/migrations/create_identification_investigations.sql` is written but not run in Supabase. The table doesn't exist yet. Backfill script depends on it.

**P2-2 (Codex): Face indices not sorted by bbox x-coordinate.**
Admin endpoint builds face_index from raw photo_faces query order, but the prompt contract says indices are left-to-right. Without sorting by bbox[0], role/relationship outputs map to wrong faces. Existing batch scripts sort before prompting.
**Fix:** Add `.order("bbox->0")` to the photo_faces query, or sort in Python.

**P2-3 (Codex): `known_people` body parsing is dead code.**
Handler is synchronous, checks `loop.is_running()`, and skips `request.body()` under the normal ASGI event loop. `verified_facts` never gets built in production.
**Fix:** Use FastHTML form parameter or query parameter instead of JSON body.

**P2-4: `log_gemini_call` naming.**
Verify import matches actual function name in supabase_data.py.

### P3 Findings (2)

**P3-1: Backfill script not tested end-to-end.**
Script written but never run (depends on table creation). Should work but unverified.

**P3-2: 1/5 validation photos timed out.**
Ceremony aisle photo (4 faces) got DEADLINE_EXCEEDED. The 180s timeout in the admin endpoint should handle this, but batch execution may need retry logic.

**P3-3 (Codex): Missing `_check_origin` CSRF check.**
New admin POST route omits `_check_origin()` that other admin routes use. Tests only grep source text, don't exercise the handler.
**Fix:** Add `_check_origin(request)` at top of handler.

### Summary
| Severity | Count | Source |
|----------|-------|--------|
| P0 | 0 | — |
| P1 | 2 | Codex (RLS) + self (prompt) |
| P2 | 4 | Codex (face sort, body parsing) + self (migration, naming) |
| P3 | 3 | Codex (CSRF) + self (backfill, timeout) |

All P1/P2 items are documented in the assessment and BACKLOG for follow-up.
