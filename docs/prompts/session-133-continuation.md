# Session 133 Continuation — Phases 4, 5, 8

## Context
Session 133 completed Phases 1-3, 6-7. Data resolution (Phase 2) is the big win — all integrity metrics at zero. Community audit merged. TOOLS-005 PRD written. Parallel agent research done + harness updated.

**Read first:** `docs/session_logs/session-133-log.md` for full status.

## Remaining Work

### Phase 4: TOOLS-004 NL Query MVP (~40 min)
- **4A**: Acceptance tests (SDD) — 6 tests for `/tools/search`
- **4B**: Route in `app/tools_routes.py` — GET form, POST parse+query
- **4C**: `app/nl_query_executor.py` — Supabase query per intent type
- **4D**: Add "Search" to tools_nav_bar
- Reuse: `rhodesli_ml/nl_query.py` (259 lines, complete parser)
- Key files: `app/tools_routes.py:25` (tools_nav_bar), `rhodesli_ml/nl_query.py`
- **Codex audit** after implementation (SQL injection focus — must use parameterized queries)

### Phase 5: WORKSPACE-001 Signup Integration (~20 min)
- Wire `create_personal_archive()` into POST /signup at `app/auth_routes.py:253`
- Post-signup redirect to personal archive
- 5 tests in `tests/test_workspace_signup.py`
- Key files: `app/supabase_data.py:1656` (create_personal_archive), `app/auth_routes.py:253`
- **Codex audit** after implementation (auth flow, race conditions, idempotency)

### Phase 8: Deploy + Verify + Close (~15 min)
1. Full test suite (expect 3646+ app tests)
2. `git push origin main`
3. Browser verify: health, landing, /tools/search, Albert Fox, Selma Capeluto, Netanel Menashe
4. Post-deploy: `face_coverage_audit.py` + `audit_merge_chains.py` — all zeros
5. Assessment: `docs/assessments/session-133-assessment.md`
6. CHANGELOG v0.99.43
7. ROADMAP: update Recently Completed
8. SESSION_HISTORY: add Session 133
9. `git log origin/main..HEAD` must be empty

## What's Already Done (don't redo)
- Phase 1: Session 132 closeout (BACKLOG, tests, AD-230, hooks)
- Phase 2: ALL data concerns resolved (691 dangling, 1858 face transfers, 212 orphans, 3+692 multi-claimed, 2 ghost faces)
- Phase 3: TOOLS-005 PRD at `docs/prds/055_estimate_v2.md`
- Phase 6: Community audit merged (3 fixes, 8 tests, COMMUNITY-018 BACKLOG)
- Phase 7: Parallel agent research + harness R1/R3/R4 updates
- 17 commits on main, not yet pushed

## Tests: 3646 pass
## Worktrees: None (all cleaned up)
## Background agents: All completed
