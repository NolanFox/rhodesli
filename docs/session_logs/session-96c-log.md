# Session 96c Log — Community-Scoped Review + Cross-Community Identity Pipeline

**Started:** 2026-03-09
**Prompt:** docs/prompts/session-96c-prompt.md

## Phase Checklist
- [x] Act 1: Orient + Fix Ray Franco Gender
- [x] Act 2: Build Photo-Derived Community Identity Set
- [x] Act 3: Fix Sidebar Counts + Enable Admin Section
- [x] Act 4: Make Discoveries Community-Aware
- [x] Act 5: Verify Cross-Community Search + Manual Merge Path
- [-] Act 6: Fix Fox Family Landing Page + Browser Verify — BLOCKED by identity sync issue
- [ ] Act 7: Assessment + Session Wrap

## Act 1 Notes
- Starting state: 1840ece (session 96b assessment complete)
- Ray Franco gender: Already uses "her" in AD-216. No male pronoun references found.
- Fox Family: 636 photos, 1652 faces, 0 identities displayed (the bug to fix)

## Acts 2-4 Notes (combined commit)
- Photo-derived identity set: rewrote `_get_community_identity_ids()` to compute from photos instead of querying empty `identity_communities` table
- Admin section enabled for ALL communities (removed is_rhodes gate)
- Upload Review link added to admin sidebar
- ML feature zeroing removed — proposals/discoveries/annotations now computed for all communities
- `_compute_discoveries` accepts community_identity_ids filter
- Discoveries route passes community to sidebar counts
- Landing page uses photo-derived count
- `add_identity_to_community()` wired into upload background ingest
- 81 community-related tests pass

## Act 5 Notes
- Search API confirmed global (no community filter) — cross-community merges work
- Test added verifying search_identities has no community filtering

## Act 6 — BLOCKING BUG
**Browser verified:** Admin section VISIBLE for Fox Family (Uploads, Approvals, Proposals, Upload Review, GEDCOM) — PASS
**Browser verified:** Still shows 0 identities — FAIL

### Debug findings (from /api/debug/community-ids endpoint):
- 636 community photos, 635 resolve via aliases (inbox_* → SHA256)
- **1652 faces match resolved photo IDs** — alias resolution works!
- **identity_count: 0** — `get_identity_for_face()` returns None for all faces
- **Root cause hypothesis**: Production uses DATA_SOURCE=postgres. Fox Family INBOX identities (1600+) exist in JSON but may not be in Supabase.
- The registry on production loads from Postgres → doesn't have Fox Family inbox identities → face lookup returns None

### Next step
- Verify Supabase has Fox Family inbox identities (check identity count in Supabase vs JSON)
- If missing: run Supabase sync or add Fox Family identities to Supabase
- Then: browser verify all 8 checks from prompt

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- BLOCKED: identity sync issue must be resolved first
