# Session 133 — Data Resolution + Feature Foundation + Community Audit

## Predecessor
Session 132 (v0.99.42). See `docs/assessments/session-132-assessment.md` and `docs/session_logs/session-132-log.md`.

## What Happened in Session 132
- **Merge chain flattening**: 556 multi-hop chains flattened to direct targets (0 remaining).
- **Optimistic concurrency**: shadow_write_identities_batch() now skips stale writes via version_id check. 4 tests.
- **Merge safety**: Cache invalidation on save_registry(), startup merge orphan check with auto-repair, merged identity redirect (UX-038). 10 tests.
- **Deep audits**: Merge chain (0 circular, 691 dangling, 1858 retaining faces). Face coverage (2 ghost, 212 orphaned, 3 multi-claimed, 24 empty CONFIRMED).
- **UX-089**: Hide "Unknown" fields from public person pages.
- **Deploy SUCCESS**: v0.99.42, 3619 app + 590 ML tests pass.

## Session 132 Gaps (MUST fix in Phase 1)
1. **BACKLOG entries missing** — Assessment references deferred items with no entries: DATA-021 (691 dangling), DATA-022 (1858 retained faces), DATA-023 (212 orphaned), DATA-024 (3 multi-claimed), DATA-025 (2 ghost faces), HARNESS-001 (hook scoping).
2. **test_merge_orphan_startup.py** — 5 tests from worktree agent lost on cleanup.
3. **No AD entry** for optimistic concurrency (AD-230).

## Session 133 Objectives
1. **RESOLVE ALL DATA CONCERNS** — zero question marks, zero deferrals
2. **TOOLS-004 NL Query MVP** — wire existing parser to /tools/search route
3. **TOOLS-005 Estimate v2 PRD** — design doc only
4. **WORKSPACE-001 Signup Integration** — wire create_personal_archive() into signup
5. **Community Middleware Audit** — file-by-file route-by-route

## Phase 0: Session Init (~5 min)
```bash
echo "133" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```
Create `docs/session_logs/session-133-log.md`. Clean stale worktrees.

## Phase 1: Session 132 Closeout (~15 min)

### 1A: BACKLOG Entries
Add DATA-021 through DATA-025 + HARNESS-001 to `docs/BACKLOG.md` with breadcrumbs.

### 1B: Recreate Lost Tests
Recreate `tests/test_merge_orphan_startup.py` — 5 tests for startup merge orphan detection/repair.

### 1C: AD-230 — Optimistic Concurrency
Add to `docs/ml/ALGORITHMIC_DECISIONS.md`.

### 1D: Fix Hook Scoping
Update `.claude/hooks/pre-work-clear-gate.sh` and `post-commit-clear-gate.sh` to derive counter file from `git rev-parse --show-toplevel`.

Commit, /clear.

## Phase 2: Resolve ALL Data Concerns (~45 min, CRITICAL)

### 2A: 691 Dangling Merge References
- Cross-reference 106 missing targets against `data_backup_session25/identities.json`
- Write `scripts/resolve_dangling_merges.py` (dry-run + execute)
- Target found in backup: re-point to final active target in Supabase
- Target not found: clear `merged_into` (un-merge)
- Report: `docs/session_context/session-133-dangling-merge-resolution.md`

### 2B: 1,858 Merged Identities Retaining Faces
- Depends on 2A (all targets must exist first)
- Write `scripts/bulk_face_transfer.py` (dry-run + execute)
- Re-run `scripts/face_coverage_audit.py` — expect 0 retained

### 2C: 212 Orphaned Faces
- Check if startup auto-repair ran. Re-run audit.
- If still orphaned: trigger repair via script.
- Acceptance: 0 orphaned faces

### 2D: 3 Multi-Claimed Faces
- `inbox_fb4b65ccecfe`: Remove from Person 4063 (Albert Fox CONFIRMED wins)
- `inbox_eaf34885039f`: Investigate 2820 vs 1e91425f, merge if same
- `Image 026_compress:face2`: Remove from Contested (Selma CONFIRMED wins)
- Write `scripts/fix_multi_claimed.py` (dry-run)

### 2E: 2 Ghost Faces (Netanel Menashe)
- Check embeddings.npy for `inbox_22a58175dbc2` and `inbox_b13a0d1781cc`
- If absent: remove from anchor_ids

### 2F: 24 CONFIRMED with 0 Anchors
- Verify GEDCOM-linked. Document as accepted.
- Add "No photos matched yet" indicator on person pages.

**Acceptance (ALL must pass):**
- [ ] 0 dangling merge references
- [ ] 0 merged identities retaining faces
- [ ] 0 orphaned faces
- [ ] 0 multi-claimed faces
- [ ] 0 ghost faces
- [ ] 24 CONFIRMED/0-anchors documented as GEDCOM-only

Commit, /clear.

## Phase 3: TOOLS-005 Estimate v2 PRD (~15 min)
- Write `docs/prds/055_estimate_v2.md` — GEDCOM context paste, text hints, geography retry
- PRD only. Update ROADMAP.
- Commit, /clear.

## Phase 4: TOOLS-004 NL Query MVP (~40 min)
- **4A**: Acceptance tests (SDD) — 6 tests for `/tools/search`
- **4B**: Route in `app/tools_routes.py` — GET form, POST parse+query
- **4C**: `app/nl_query_executor.py` — Supabase query per intent type
- **4D**: Add "Search" to tools_nav_bar
- Reuse: `rhodesli_ml/nl_query.py` (259 lines, complete)
- Commit, /clear.

## Phase 5: WORKSPACE-001 Signup Integration (~20 min)
- Wire `create_personal_archive()` into POST /signup at `app/auth_routes.py:253`
- Post-signup redirect to personal archive
- 5 tests in `tests/test_workspace_signup.py`
- Commit, /clear.

## Phase 6: Community Middleware Audit (~30 min, PARALLEL WORKTREE)
- Branch: `session-133/community-audit`
- Launch after Phase 1 (hook fix enables worktrees)
- Audit all 19 route files: community_slug flow, url_prefix usage, Supabase filtering
- Extend `tests/test_community_routing_safety.py`
- Report: `docs/session_context/session-133-community-audit.md`

## Phase 7: Codex Audit (~10 min, BACKGROUND)
- Audit all changes: data scripts, NL query (SQL injection), signup, community
- Write `docs/session_context/session-133-codex-audit.md`
- Fix P0/P1 immediately.

## Phase 8: Deploy + Verify + Close (~15 min)
1. Merge: `./scripts/merge.sh session-133/community-audit`
2. Full test suite (3619+ app + 590 ML)
3. `git push origin main`
4. Browser verify: health, landing, /tools/search, Albert Fox, Selma Capeluto, Netanel Menashe
5. Post-deploy: `face_coverage_audit.py` + `audit_merge_chains.py` — all zeros
6. Assessment, CHANGELOG v0.99.43, ROADMAP, SESSION_HISTORY, BACKLOG
7. `git log origin/main..HEAD` must be empty
8. Run /session-review and /ux-review skills

## Parallelization

| Track | Branch | Files | Start After |
|-------|--------|-------|-------------|
| Data (2A-2F) | main | scripts/, supabase_data.py | Phase 1 |
| Community (Phase 6) | session-133/community-audit | Route files (NOT main.py) | Phase 1 |
| Codex (Phase 7) | Background | docs/ only | Phase 4 |
| Features (4-5) | main | tools_routes.py, auth_routes.py | Phase 2 |

Merge order: main 1-5 → merge community audit → test → deploy

## Critical Constraints
- **ZERO data concerns remaining after Phase 2** — no deferrals
- DRY-RUN all data repair scripts before executing
- NEVER delete identities — un-merge or reassign only
- /clear between phases, commit after every sub-task
- Browser automation READ-ONLY on production
- Codex audit after each major phase
- PRD/SDD for features >30 min

## Key Files
- `data_backup_session25/identities.json` — cross-reference for dangling merges
- `scripts/audit_merge_chains.py`, `scripts/face_coverage_audit.py` — audit scripts
- `app/supabase_data.py:767` — shadow_write_identities_batch
- `app/supabase_data.py:1656` — create_personal_archive()
- `app/auth_routes.py:253` — POST /signup handler
- `app/tools_routes.py:25` — tools_nav_bar
- `rhodesli_ml/nl_query.py` — NL query parser (complete)
- `app/main.py:667` — CommunityMiddleware
- `.claude/hooks/pre-work-clear-gate.sh` — counter file path fix

## Reference Documents
- Session 132 assessment: `docs/assessments/session-132-assessment.md`
- Merge chain audit: `docs/session_context/session-132-merge-chain-audit.md`
- Face coverage audit: `docs/session_context/session-132-face-coverage-audit.md`
- PRD-032 NL Query: `docs/prds/032_nl_archive_query.md`
- PRD-036 Workspace: `docs/prds/036_workspace_onboarding.md`
- Lessons 154, 153, 150, 146: data integrity lessons
