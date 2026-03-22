# Session 134 Context — Clean Sweep + Performance + Codex Collaboration

**Predecessor:** [Session 133 Assessment](../assessments/session-133-assessment.md)
**Session 133 Log:** [session-133-log.md](../session_logs/session-133-log.md)

## Current State (Post-Session 133)

| Metric | Value |
|--------|-------|
| Version | v0.99.43 |
| App tests | 3674 pass |
| ML tests | 590 pass |
| Photos | 972 |
| Identities | 3757 total (1863 non-merged) |
| Confirmed | ~154 |
| Data integrity | ALL ZEROS (verified by audit scripts) |
| Unpushed commits | 0 |

## Session 133 Gaps Identified

### 1. BACKLOG Not Updated
DATA-021 through DATA-025 were fully resolved (691 dangling, 1858 face transfers, 212 orphans, 695 multi-claimed, 2 ghost) but BACKLOG.md entries still show OPEN. HARNESS-001 shows strikethrough but no DONE status. BACKLOG header says v0.99.6 / 4357 tests — stale.

### 2. NL Query Not Production-Tested
`/tools/search` was browser-verified to RENDER on production (form loads, nav bar shows "Archive Search") but never tested with actual queries returning results from Supabase.

### 3. WORKSPACE-001 Signup Only Mock-Tested
`create_personal_archive()` wired into `POST /signup` — 5 unit tests pass with mocks. Real Supabase interaction untested. Session 122's SQL migration may not have been applied.

### 4. Session 129 UX Bugs Unresolved (15 items)
Root cause chain: FB-016 (photo_faces inbox ID vs SHA256) → FB-002, FB-003, FB-006, FB-010.
Independent: FB-004, FB-005/007, FB-008, FB-009, FB-013-015, FB-017-020.

### 5. Fox Triage Feedback Unresolved (14 items)
FB-100 through FB-114 from 2026-03-14 triage session. Key: speed-run flow order (FB-104), GEDCOM linking (FB-110), cross-community badge (FB-100), "Under Review" contradiction (FB-113).

### 6. Codex Audit Skipped
Session 133 continuation prompt called for Codex audits on TOOLS-004 (SQL injection focus) and WORKSPACE-001 (auth flow). Not run.

### 7. Performance
- PERF-002: Tree cold load ~6.4s (target <3s)
- FB-105: Merge/confirm multi-second latency (target <1s)
- Sessions 111f-125 fixed many perf items but these remain

## FB-016 Root Cause Analysis

**Problem**: `photo_faces` table stores photo IDs in inbox format (`inbox_fox-charlie-001_173_603575867.895093`). Photo page URLs use SHA256 format (`10a7d40eb3bf94f7`). Face-to-identity lookup queries `photo_faces` by SHA256 ID → zero results → faces appear unidentified.

**Impact**: All batch-uploaded Fox Family photos (636 photos) have this mismatch. Rhodes photos (legacy) use SHA256 natively and are unaffected.

**Fix approach**: Extend face resolution to try both ID formats. `PhotoRegistry._sha256_reverse_index` (Session 131) maps SHA256 → original filename. Use this to find the inbox photo ID, then query photo_faces.

**Cascading fixes**: FB-002 (Esther untagged), FB-003 (overlay click fails), FB-006 (no number), FB-010 (no checkmark).

## Codex Audit Strategy

Per HD-028 and `.claude/rules/ai-tool-audit.md`:

**Security audit** (fresh, no prior context):
- Target: `app/nl_query_executor.py`, `app/auth_routes.py`, `app/tools_routes.py`
- Focus: SQL injection (Supabase .ilike()), auth bypass on search, input validation, rate limiting

**Performance audit** (collaborative — go back and forth):
- Target: `app/main.py`, `app/page_routes.py`, `app/perf_cache.py`
- Focus: N+1 queries, missing caches, heavy computation in request path
- Process: review findings → push back on already-done items → agree on top 3-5 → implement

## Parallelization Plan

| Phase | Track | Files | Dependencies |
|-------|-------|-------|-------------|
| 1 | Main | BACKLOG.md | None |
| 1 | BG | Codex security | None |
| 1 | BG | Codex performance | None |
| 2 | Main | page_routes.py, main.py, photo_registry.py | Phase 1 |
| 3A | Worktree | cluster_review_routes.py | Phase 2 |
| 3B | Worktree | page_routes.py (people grid section only) | Phase 2 |
| 3C | Worktree | identity_routes.py | Phase 2 |
| 4 | Main | cluster_review_routes.py | Phase 3A merge |
| 5 | Main | Various (Codex findings) | Codex security complete |
| 6 | Main | Various (perf) | Codex perf complete |
| 7 | Main | Browser only | All code phases |
| 8 | Main | BACKLOG, feedback files | Phase 7 |
| 9 | Main | Docs, deploy | Phase 8 |

## Items Deferred to Future Sessions

| Item | Reason | Dependency |
|------|--------|-----------|
| WORKSPACE-002/003 | Sharing + upload flows | WORKSPACE-001 verified |
| TOOLS-005 Estimate v2 | PRD exists, next feature session | None |
| PRD-038 Phase 5 | Needs more Fox labels | User triage session |
| Multi-GEDCOM support | Architecture decision needed | PRD required |
| pgvector migration | Only at 5K+ embeddings | Scale threshold |
| TOOLS-006 Self-service archive | WORKSPACE-001 complete first | WORKSPACE-001 |
| FB-017 Mobile community switcher | UX design needed | PRD |

## Cross-References

- Session 129 feedback: `docs/feedback/session-129-feedback.md`
- Fox triage feedback: `docs/feedback/2026-03-14-fox-triage-feedback.md`
- Merge chain audit: `scripts/audit_merge_chains.py` → `docs/session_context/session-132-merge-chain-audit.md`
- Face coverage audit: `scripts/face_coverage_audit.py` → `docs/session_context/session-132-face-coverage-audit.md`
- Data resolution report: `docs/session_context/session-133-dangling-merge-resolution.md`
- AI tool audit rule: `.claude/rules/ai-tool-audit.md`
- Codex strategy: HD-028 in `docs/HARNESS_DECISIONS.md`
- Performance cache: `app/perf_cache.py`
- Photo ID mapping: `core/photo_registry.py` (_sha256_reverse_index)
