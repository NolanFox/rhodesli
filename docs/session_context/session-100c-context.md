# Session 100c Context — Fox Family Speed-Run Review & Platform Reliability

**Predecessor:** Session 100b-cont3 (`docs/session_context/session-100b-context.md`)
**Date:** 2026-03-13
**Agent:** Claude Code (Opus 4.6)

## Problem Statement

Two independent problems. Workstream A is P0 (blocks data fix verification). Workstream B is the main session value delivery.

---

## Workstream A: Production Supabase Connection (P0)

### What's broken
Production app says "Supabase connection skipped" despite `DATA_SOURCE=postgres` on Railway. Data fixes applied to Supabase (Yaacov Franco face swap commit dc84696, Solomon orphan removal commit 07ac0db) are not served to users — app falls back to JSON on the Railway volume.

### Known state
- `DATA_SOURCE=postgres` is set on Railway (confirmed Session 100b-cont3)
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` are configured
- Health endpoint says "Supabase connection skipped"
- Deploy SUCCESS (f0013a7c, 2026-03-13T05:35:42Z)
- supabase>=2.0 is in requirements.txt line 18 → installed via Dockerfile line 24-25

### Investigation path
1. `app/main.py:151` — `DATA_SOURCE = os.environ.get("DATA_SOURCE", "json")`
2. `app/main.py:1065-1075` — Postgres branch calls `IdentityRegistry.load_from_postgres()`, catches Exception and falls back to JSON
3. `app/main.py:635-641` — `get_supabase_client()` check; if None, returns None (skips Supabase)
4. `app/supabase_data.py:37` — `get_supabase_client()` definition
5. `app/page_routes.py:127` — Health endpoint definition (wired at `app/main.py:10365`)
6. There is NO function called `load_registry_from_postgres` in supabase_data.py — the method is `IdentityRegistry.load_from_postgres()` (classmethod)

### Likely root causes (check in order)
1. **`get_supabase_client()` returns None** — env var names might not match what the code expects
2. **`IdentityRegistry.load_from_postgres()` throws** — exception is caught and silently falls back to JSON (Lesson 133)
3. **Health endpoint reports "skipped" for a different reason** than registry load

### Fallback
If Supabase can't be fixed in <30 min, push corrected identities.json to Railway volume via sync API and document in BACKLOG.

---

## Workstream B: Fox Family Cluster Speed-Run Review

### Current state (what already exists)
**Route:** `app/cluster_review_routes.py:777` — `/admin/upload-review`
**Three sections already render:**
1. **Grouped Identities** (line 810) — multi-face INBOX clusters, sorted by face count, max 50 shown
2. **Potential Review Groups** (line 902) — unresolved identities with similar faces, function at line 490
3. **Proposal Matches** (line 926) — faces matched to CONFIRMED identities via proposals.json

**Batch endpoints already exist:**
- `POST /api/cluster-review/confirm` (line 1103) — confirm single face
- `POST /api/cluster-review/reject` (line 1130) — reject single face
- `POST /api/cluster-review/confirm-all` (line 1179) — promote all candidates for an identity
- `POST /api/cluster-review/reject-all` (line 1224) — reject all candidates for an identity
- `POST /api/cluster-review/learn-same` (line 1303) — active learning: mark pair as same
- `POST /api/cluster-review/learn-different` (line 1348) — active learning: mark pair as different

**Community scoping works:** Lines 790-801 filter proposals by community identity set (COMMUNITY-011 fix).

**Data:** 1122 Fox-filtered proposals (Session 96e). Fox Family has 635 photos, ~1600 INBOX identities.

**Tests exist:** `tests/test_cluster_review.py` and `tests/test_cluster_review_routes.py`

### What's MISSING (the actual gaps)
1. **No auto-advance** — after confirm/reject, you see a success message but must manually find next cluster
2. **No progress counter** — no "47 of 312 reviewed" indicator
3. **No dismiss/noise action** — can't skip noise faces without confirm/reject
4. **No keyboard shortcuts** — must click each button
5. **No "speed run" flow** — current UX is dashboard-style (see all sections), not queue-style (one-at-a-time)
6. **Cluster cards link to person page** (line 877) — takes you away from the review queue entirely

### Competing software patterns (from Session 100 audit)
- **Lightroom:** cluster-first stacks, name one = tag all
- **Mylio:** batch confirm, ignore groups of unknowns
- **Apple Photos:** background indexing + people collection
- **PhotoPrism:** hide faces, report bad matches
- Common thread: **precomputation + batch confirmation + noise dismissal**

### Architecture for speed-run mode
The existing page has the right data but wrong UX paradigm. Instead of a 3-section dashboard:

**Queue mode:** Show one cluster at a time. Large face thumbnails. Confirm-all / Reject-all / Skip / Dismiss buttons. After action, HTMX swaps in the next cluster (no page reload). Progress bar at top.

**Implementation approach:**
1. New route: `GET /admin/cluster-review/next` — returns the next unreviewed cluster card (HTMX partial)
2. Add `dismissed_clusters` tracking (localStorage or proposals.json field) so dismissed clusters stay hidden
3. Keyboard event listener in page JS: Y/N/D/S mapped to buttons
4. Progress counter computed from total clusters vs reviewed count
5. Keep existing dashboard as "Overview" tab; add "Speed Run" tab

### Key files to modify
| File | Line | What |
|------|------|------|
| `app/cluster_review_routes.py` | 777 | Add speed-run mode to upload-review |
| `app/cluster_review_routes.py` | 1179 | confirm-all already exists — wire to auto-advance |
| `app/cluster_review_routes.py` | 1224 | reject-all already exists — wire to auto-advance |
| `app/cluster_review_routes.py` | NEW | `GET /admin/cluster-review/next` endpoint |
| `app/cluster_review_routes.py` | NEW | `POST /admin/cluster-review/dismiss` endpoint |
| `app/cluster_review_routes.py` | NEW | `GET /admin/cluster-review/progress` endpoint |
| `tests/test_cluster_review.py` | append | Speed-run mode tests |

---

## Relevant PRDs & Decisions
- PRD-037: Post-Upload Intelligence (`docs/prds/037_post_upload_intelligence.md`)
- AD-179: Two-tier auto-clustering (Tier 1 <0.85 auto-add, Tier 2 0.85-1.10 suggestions)
- AD-215: Error correction must be effortless
- AD-216: Photo-derived community identity sets
- Session 100 Fox Family screenshot audit (`docs/assessments/session-100-fox-family-screenshot-audit.md`)
- Session 100 face tagging audit (`docs/assessments/session-100-face-tagging-and-fox-family-audit.md`)

## Existing BACKLOG Items (related)
- COMMUNITY-015: Internal links missing community prefix
- COMMUNITY-016: `/api/proposed-matches` only reads registry, not proposals.json
- UX-202: One-Click Bulk Tag Confirmation — **this session closes this item**
- DATA-011: Visual confirmation gate for admin confirm workflow
- DATA-012: Data integrity CI for CONFIRMED identities

## Parallelization Analysis

**Workstream A (Supabase fix) and Workstream B (cluster UX) are fully independent.**
- Different files touched
- No shared state
- Can run as parallel worktree tracks if desired

**Within Workstream B:**
- PRD writing and implementation are sequential (PRD first)
- Backend endpoints and frontend JS can be partially parallelized
- Tests can be written alongside implementation

## Deferred from 100b series
- Browser verification of face cycling arrows (verify in Act 5)
- Browser verification of Yaacov Franco face (verify in Act 5)
- ML test suite verification (verify in Act 6)

## Post-Session Planning
- If cluster review ships: next session collects Fox Family labels for ML-117
- If Supabase fixed: verify all data fixes render correctly
- COMMUNITY-017 (default community routing) blocks wider sharing — consider for 101
