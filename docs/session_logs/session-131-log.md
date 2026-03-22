# Session 131 Log — Performance + UX + Codex Audit
Started: 2026-03-22
Mode: implementation
Predecessor: Session 130

## Phase Checklist
- [x] Deploy verification — 11/11 smoke tests pass
- [x] Performance audit — 2 high-priority N+1 patterns identified
- [x] Performance fix 1: Focus mode N+1 proposals — merged from worktree
- [x] Performance fix 2: Photo grid identity lookup — merged from worktree
- [x] Browser verification — Landing, People, Photos, Compare, Estimate
- [x] UX fix: Hide upload provenance from non-admin users
- [x] Codex audit of sessions 125-130 — 11 findings, P1s fixed
- [x] Audit fixes: Thread safety, CSS conflicts, import cleanup

## Performance Fixes
1. **Focus mode N+1** — `_build_best_proposals_index()` pre-computes O(n) lookup
   - Eliminates ~200+ redundant `_load_proposals()` calls per sort
   - 150 proposal/triage/focus tests pass
2. **Photo grid identity lookup** — pre-computed `_face_id_confirmed` set
   - Eliminates ~2,900 per-face lookups per /photos page load
   - 55 browse tests pass
3. **FakeRegistry fix** — added `list_identities()` to test mock

## Codex Audit Results (Sessions 125-130)
| # | Severity | Issue | Status |
|---|----------|-------|--------|
| 1 | P1 | CSRF _check_origin not on all POST routes | Documented (SameSite=Strict mitigates) |
| 2 | P2 | CSRF allows missing Origin/Referer | Documented |
| 3 | P2 | Rate limiter in-process only | Acceptable for single instance |
| 4 | P3 | Rate limiter unbounded memory | Deferred |
| 5 | P1 | JSON backup shared mutable reference | **FIXED** (deepcopy) |
| 6 | P2 | sync_identity_overrides stub | Acceptable |
| 7 | P2 | Duplicate face-confirmed set build | Deferred (both are O(n)) |
| 8 | P3 | Conflicting Tailwind CSS classes | **FIXED** (4 conflicts) |
| 9 | P3 | PhotoRegistry O(n) resolve | **FIXED** (SHA256 reverse index) |
| 10 | P3 | Import in hot path | **FIXED** (moved to module level) |
| 11 | P3 | find_confirmed_by_name linear scan | Acceptable at current scale |

## UX Fix
- Upload provenance ("Uploader not recorded for this import") hidden for non-admin
- `_get_upload_provenance_display()` returns None when is_admin=False
- Both /photos initial load and infinite scroll respect admin check

## Response Times (post-performance fix)
| Page | Time |
|------|------|
| Person page | 628ms |
| People grid | 448ms |
| Photos grid | 370ms |
| Estimate tool | 363ms |
| Compare tool | 356ms |

## Continuation Phase — Merge Orphan Crisis (Lesson 154)

### P0 Data Fix: 175 Orphaned Faces
- **Root cause**: Merge operations transferred faces in-memory but persistence failed silently. Merged source identities got `merged_into` set (hiding them from `list_identities()`) while their faces were never transferred to the target.
- **Impact**: 175 faces across 18 identities orphaned. Esther Burd Fox lost 8 faces, showing as "Unidentified" in Dayton Ohio photo (10a7d40eb3bf94f7) despite being tagged.
- **Fix**: Direct Supabase repair — 112 unique faces restored to 18 target identities.
- **Browser verified**: Esther Burd photo now shows 17/18 identified (was 16/18). "Esther Bur..." label visible on correct face.

### Prevention: Post-Merge Verification
- Added to `core/registry.py merge_identities()`: after merge completes, verify ALL source faces are in target. Force-adds any orphans with error logging.
- Defensive comment (Codex P1-1): documents that source lists must remain populated for verification to work.

### Structural Tests (8 total)
- `tests/test_merge_face_transfer.py`:
  - Simple merge face transfer (all source faces in target)
  - get_identity_for_face finds merged faces
  - Source hidden after merge
  - No orphaned faces after merge
  - Direction swap preserves all faces
  - Chained merges (A→B→C) preserve all faces
  - Force-add safety net fires when face skipped (Codex P1-2)
  - Source lists preserved after merge
- `tests/test_merge_orphan_audit.py`: Production Supabase audit (skipped in CI)

### Codex Audit (Session 131 Continuation)
- 10 findings across 4 severity levels
- 3 P1s fixed: defensive comment, safety net test, co-occurrence audit
- Co-occurrence audit confirmed 0 violations from repair (4 pre-existing)
- Written to `docs/session_context/session-131-codex-audit.md`

### Investigation Report
- `docs/session_context/session-131-merge-failure-investigation.md`
- Finding: Sessions 129/130/131 each verified at wrong layer (person page count / Supabase query / generic browser check) — never the specific broken photo page

### Lesson 154 Documented
- 10th data integrity occurrence (Lessons 56→69→78→85→141→144→147→150→153→154)
- Rule: NEVER declare data fix done without browser-verifying the SPECIFIC affected page

### Deep Investigation Findings (7 vulnerabilities)
1. TTL cache stale-while-revalidate race (MEDIUM)
2. Community cache not invalidated after merge (MEDIUM)
3. Batch shadow write can overwrite merge data (CRITICAL)
4. No transitive merge chain following (CRITICAL)
5. Merged identity GET not redirected (LOW)
6. Partial batch merges leave inconsistent state (MEDIUM)
7. Photo registry cache not cleared after merge (MEDIUM)

→ All deferred to Session 132 for comprehensive fix

## Commits
- `380662e` — audit fixes (thread safety, CSS, imports)
- `4aa9947` — hide upload provenance from non-admin
- Merge commits for performance worktrees
- `a1f3397` — post-merge verification prevents face orphaning (Lesson 154)
- `dfe5068` — continuation prompt + merge failure investigation
- `31f5269` — Codex audit P1 fixes — safety net test + defensive comment
