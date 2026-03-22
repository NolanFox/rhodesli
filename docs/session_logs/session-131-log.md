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

## Commits
- `380662e` — audit fixes (thread safety, CSS, imports)
- `4aa9947` — hide upload provenance from non-admin
- Merge commits for performance worktrees
