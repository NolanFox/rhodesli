# Session 120 Context — ML Comparison Script + UX Fix Sprint

**Predecessor:** [Session 119 Context](session-119-context.md) (ML Service E2E Verification)
**Assessment:** [Session 119 Assessment](../assessments/session-119-assessment.md)
**Feedback:** [Session 119 Feedback](../feedback/session-119-feedback.md)

## Problem Statement

Session 119 verified the ML service works end-to-end (first real production upload, 14 faces, 3/3 matches correct). But several gaps remain:

1. **No way to compare local vs cloud embeddings** without writing to production DB — needed for AD-229 cosine similarity criterion
2. **Sentry alert**: "POST-SYNC VALIDATION FAILED: 14 new faces have no identity after Supabase sync" — needs investigation
3. **4 high-priority UX bugs** from interactive feedback block admin workflow

## Phase 1: ML Embedding Comparison Script

### Goal
Create a standalone script that sends a photo to both local InsightFace AND the ML service, compares embeddings, and reports cosine similarity per face. No database writes.

### Approach
The ML service's `/api/v1/detect-and-embed` endpoint already returns embeddings as JSON. Local InsightFace can be called directly. A comparison script:
1. Takes a local photo path
2. Runs local InsightFace detection (same buffalo_l model, same config)
3. Calls ML service endpoint via HTTP (needs ML_SERVICE_URL — use production internal URL via Railway proxy, or public endpoint if available)
4. Matches faces by bounding box overlap (IoU)
5. Reports cosine similarity per matched face pair
6. AD-229 criterion: cosine similarity ≥ 0.999

### Key files
- `core/ingest_inbox.py:extract_faces()` — local InsightFace detection
- `core/ml_client.py:MLServiceClient.detect_and_embed()` — ML service client
- `ml_service/detect.py` — ML service detection endpoint

### Challenge
The ML service is on Railway's internal network. Options:
- A: Run the script ON Railway (via one-off command) — has network access
- B: Expose a temporary public endpoint on the ML service — security risk
- C: Run the comparison inside the web app as an admin endpoint — cleanest
- **D (recommended): Create `scripts/compare_ml_embeddings.py`** that takes a photo, runs local detection, and also calls the ML service via the web app's `/api/admin/ml-compare` endpoint (new). The admin endpoint forwards to ML service internally and returns embeddings. No DB writes.

### New endpoint design
```
POST /api/admin/ml-compare
  - Accepts: multipart image upload
  - Calls ML service detect-and-embed
  - Returns: raw embedding JSON (no DB writes, no identity creation)
  - Admin-only auth
```

### Script design
```
python scripts/compare_ml_embeddings.py --photo raw_photos/IMAGE.jpg [--url https://rhodesli.nolanandrewfox.com]
  - Runs local InsightFace
  - Calls /api/admin/ml-compare
  - Matches faces by IoU
  - Reports cosine similarity per face
  - PASS if all ≥ 0.999
```

## Phase 2: Sentry Alert Investigation

### The alert
```
PYTHON-ASGI-25 - [upload] POST-SYNC VALIDATION FAILED: 14 new faces have no identity after Supabase sync
```

### Location
`app/upload_routes.py:1207-1237` — post-sync validation checks if every new face_id exists in the registry's anchor_ids/candidate_ids.

### Likely cause
The validation runs against `json_registry._identities` AFTER `shadow_write_identities_batch()`. But the face IDs may use a different format than what's stored in anchor_ids (e.g., inbox_ prefix differences, or the ingest pipeline creates identities through `group_inbox_identities()` which uses a different key scheme).

### Investigation steps
1. Check what `result["face_ids"]` contains (format)
2. Check what anchor_ids look like after ingest
3. Determine if this is a timing issue (identities created after validation) or format mismatch
4. Fix: either adjust validation logic or fix the face ID format

### Evidence it's non-critical
All 14 identities work correctly in the UI (user merged Fanny, Irving, named Sarah and Solomon). The orphan repair path at line 1225-1237 likely fixed the issue in real-time.

## Phase 3: UX Fix Sprint (4 items from Session 119 feedback)

### FB-009 (P0): Confirm button silently fails for unidentified persons
- **File:** `app/page_routes.py:4005-4026`
- **Root cause:** Button always rendered for INBOX/PROPOSED/SKIPPED states. `identity_routes.py:1452-1458` returns 409 but toast not visible in Speed Loop context.
- **Fix:** Check `IdentityRegistry._is_real_name()` when rendering the button. If False, either hide the button or render it as disabled with a tooltip "Name this person first."
- **Risk:** Low — only affects rendering, not data.
- **Test:** Verify confirm button hidden for "Unidentified Person XXX", visible for named persons.

### FB-008 (P1): Cross-batch match notifications
- **Current state:** Upload pipeline runs `find_cross_batch_matches()` and logs results but generates no notification.
- **Location:** `app/upload_routes.py` — after cross-batch matching, around line 1150-1190
- **Notification system:** Check `app/engagement_routes.py` for existing notification infrastructure. There's a notifications count endpoint and sidebar badge.
- **Fix:** After cross-batch matching, create notification entries for high-confidence matches. Format: "Upload complete: N faces found, M potential matches to existing people."
- **Risk:** Medium — need to understand notification table schema and rendering.
- **Test:** Upload a photo, verify notification appears with correct count.

### FB-001 (P1): Merge search in Focus/New Matches view
- **Current state:** Person pages have "Search to merge..." input. Focus/New Matches view may be missing it.
- **Location:** The Focus view card rendering in `app/identity_routes.py` or `app/page_routes.py`
- **Fix:** Add the same "Search to merge..." input to the Focus view card for each identity. The search endpoint already exists.
- **Risk:** Low — additive UI change.
- **Test:** Navigate to Focus view, verify search box appears on identity cards.

### FB-011 (P1): Community filter on Similar Identities
- **Current state:** Similar Identities panel shows ALL identities globally ranked by embedding distance. Cross-community matches (often noise) are mixed with same-community matches.
- **Location:** The function that computes Similar Identities — likely `_get_confirmed_identity_suggestions()` or `find_nearest_neighbors` in `core/neighbors.py`
- **Fix:** Add a "Community" filter dropdown to the Similar Identities panel. Options: "Same community" (default), "All communities", specific community names. Filter the results before rendering.
- **Risk:** Medium — need to ensure community_id is available for each identity in the similarity computation.
- **Test:** View person in Fox Family, verify default shows Fox Family matches first, toggle shows all.

## Parallelization Plan

### File dependency analysis
| Track | Files touched | Overlap? |
|-------|--------------|----------|
| Phase 1 (ML compare) | `scripts/compare_ml_embeddings.py` (new), `app/admin_routes.py`, `tests/test_admin_routes.py` | admin_routes.py |
| Phase 2 (Sentry) | `app/upload_routes.py` (investigation + fix) | None |
| FB-009 | `app/page_routes.py` | None |
| FB-008 | `app/upload_routes.py`, notification system | Overlaps Phase 2 on upload_routes |
| FB-001 | `app/identity_routes.py` or card rendering | Possible overlap with FB-011 |
| FB-011 | `app/identity_routes.py` (Similar Identities panel) | Possible overlap with FB-001 |

### Recommended execution
- **Worktree A:** FB-009 (page_routes.py — isolated, quick fix)
- **Worktree B:** Phase 1 (ML compare script + admin endpoint — admin_routes.py, new script)
- **Sequential on main:** Phase 2 + FB-008 (both touch upload_routes.py)
- **Sequential on main:** FB-001 + FB-011 (both touch identity card rendering)

OR if FB-001 and FB-011 touch different functions:
- **Worktree C:** FB-001 (Focus view card)
- **Worktree D:** FB-011 (Similar Identities panel)

### Test plan
- `make test-fast` after each worktree merge
- Browser verify: FB-009 (Speed Loop), FB-001 (Focus view), FB-011 (person page)
- Script verify: Phase 1 comparison script output

## Research Findings (from Session 119 agents)

### ML Comparison: No Admin Endpoint Needed
The ML service `/api/v1/detect-and-embed` already returns embeddings as JSON with zero DB writes. A standalone script can call local InsightFace directly via `core/ingest_inbox.extract_faces()` and the ML service via `MLServiceClient.detect_and_embed()`. No new admin endpoint required — simpler than the context file originally proposed.

**Key detail:** `extract_faces()` returns PFE dicts with `mu` key (normed embedding). ML service returns `embedding` key (also normed). Both are 512-dim L2-normalized. Cosine similarity = dot product.

### Sentry Alert: Registry Source Conflict (NOT a false positive)
The post-sync validation fires because the **grouping step overwrites identities.json** with Supabase-origin data that lacks the just-ingested faces:
1. `process_directory()` writes 14 new identities to `identities.json`
2. Grouping loads from Supabase (misses new faces) → if any merges → `save_registry()` **overwrites JSON** with Supabase data, erasing the 14 new faces
3. Validation finds them missing → orphan repair recreates them

**Fix:** Load from JSON (not Supabase) in the grouping step at `upload_routes.py:998`. Also use `_collect_registry_face_ids()` for type-safe face ID normalization in the validation check.

### FB-009: Three Surfaces Need Fix
Confirm button appears in THREE places:
1. **Photo modal quick-action** (`page_routes.py:4008-4026`) — primary. `raw_name` is in scope at line 3800.
2. **Person detail page** (`person_routes.py:1330-1341`) — `display_name` in scope.
3. **main.py:6761** — lower priority modal.

Fix: Check `_is_real_name(name)` before rendering. Render as disabled (gray, cursor-not-allowed, tooltip) not hidden.

### FB-008: Notification Infrastructure Already Exists
- Supabase `notifications` table is live with full CRUD
- `_create_notification()` helper in `notification_routes.py` handles DB write + optional email
- `create_discovery_notification()` exists but is NEVER CALLED — close analog
- Bell badge polls every 30s via `/api/notifications/count`
- **Risk:** Need admin `user_id` UUID for notification. Existing pattern uses `"00000000..."` placeholder.

### FB-001: Search Box Exists but Hidden Behind "Find Similar"
- `manual_search_section` (main.py:9255) renders the search box
- It only appears AFTER clicking "Find Similar" to load `neighbors_sidebar`
- In Focus view, if no proposals exist, the search is invisible
- **Fix:** Add `manual_search_section` directly to `identity_card_expanded` (main.py:~5812) so it's always visible

### FB-011: Community Sort Already Has a Pattern
- `find_nearest_neighbors_fast` returns all communities (neighbors.py FROZEN)
- `current_community` IS available in the route handler at `request.state.community`
- `_get_community_identity_ids(community)` already exists and is used in cluster-review search (identity_routes.py:1142-1154)
- **Fix:** Post-process neighbors results to sort same-community first. Apply in identity_routes.py:~540-575.

### Updated Parallelization (based on research)

| Track | Files | Can Parallelize? |
|-------|-------|-----------------|
| FB-009 | page_routes.py, person_routes.py | YES — worktree A |
| ML compare script | scripts/compare_ml_embeddings.py (new) | YES — worktree B |
| Sentry fix | upload_routes.py | Sequential with FB-008 |
| FB-008 | upload_routes.py, notification_routes.py | Sequential after Sentry |
| FB-001 | main.py | YES — worktree C |
| FB-011 | identity_routes.py | YES — worktree D |

**4 parallel worktrees possible!** FB-001 and FB-011 touch different files (main.py vs identity_routes.py). Only Sentry + FB-008 must be sequential (both touch upload_routes.py).

## Breadcrumbs
- AD-229: ML service stability criteria (docs/ml/ALGORITHMIC_DECISIONS.md)
- Session 119 feedback: docs/feedback/session-119-feedback.md
- UX-131 through UX-140: BACKLOG items from Session 119
- Lesson 149: Browser READ-ONLY on production
- Lesson 152: Supabase queries must match actual schema
