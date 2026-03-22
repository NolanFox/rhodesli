# Session 133 Context — Data Resolution + Feature Foundation

**Predecessor:** Session 132 (v0.99.42) — `docs/assessments/session-132-assessment.md`

## Research Findings (Pre-Session Planning)

### Data Integrity Issues (from Session 132 audits)

| Issue | Count | Root Cause | Resolution Strategy |
|-------|-------|-----------|-------------------|
| Dangling merge refs | 691 (106 unique targets) | Pre-Supabase era identities never migrated | Cross-ref `data_backup_session25/identities.json`, re-point or un-merge |
| Merged retaining faces | 1,858 | merge_identities() didn't transfer faces historically | bulk_face_transfer.py after dangling refs resolved |
| Orphaned faces | 212 across 36 photos | Faces in photo_faces not claimed by any identity | Startup auto-repair creates INBOX, verify it ran |
| Multi-claimed faces | 3 | Same face in 2 identities | CONFIRMED identity wins, remove from other |
| Ghost faces (CONFIRMED) | 2 (Netanel Menashe) | anchor_ids ref non-existent photo_faces entries | Remove phantom references |
| CONFIRMED 0 anchors | 24 | GEDCOM-linked without matching photos | Accepted, add UX indicator |

### Feature State

| Feature | PRD | Parser/Code | Route | Tests | Status |
|---------|-----|-------------|-------|-------|--------|
| TOOLS-004 NL Query | PRD-032 exists | `rhodesli_ml/nl_query.py` (259 lines, complete) | None | `tests/test_nl_query.py` (parser only) | Needs route + Supabase wiring |
| TOOLS-005 Estimate v2 | None | `app/estimate_routes.py` (current v1) | `/tools/estimate` | Existing | Needs PRD first |
| WORKSPACE-001 | PRD-036 exists | `create_personal_archive()` in supabase_data.py | None | 16 tests (Session 122) | Needs signup wiring |

### Community Middleware Architecture
- `CommunityMiddleware` at `app/main.py:667-713`
- Skip prefixes: `/static/`, `/api/`, `/_`
- Default community: "rhodes"
- Previous audit: Session 115 (PRD-052) covered 120+ routes, 27 safety tests
- Known gap: `/api/` routes skip middleware (Lesson 109) but some should be community-scoped

### Parallelization Constraints
- `app/main.py` (11714 lines) is shared bottleneck — only one track can touch it
- Community audit touches route files (NOT main.py) — safe to parallelize
- Hook scoping issue: `pre-work-clear-gate.sh` uses shared counter, blocks worktree agents
- Fix: derive counter path from `git rev-parse --show-toplevel`

### Session 132 Closeout Gaps
1. BACKLOG entries never created for deferred items
2. `test_merge_orphan_startup.py` lost when worktree cleaned
3. No AD-230 for optimistic concurrency
4. Hook scoping prevents worktree parallelization

## Cross-References
- Merge chain audit: `docs/session_context/session-132-merge-chain-audit.md`
- Face coverage audit: `docs/session_context/session-132-face-coverage-audit.md`
- Backup data: `data_backup_session25/identities.json`
- NL Query PRD: `docs/prds/032_nl_archive_query.md`
- Workspace PRD: `docs/prds/036_workspace_onboarding.md`
- Community routing PRD: PRD-052 (Session 115)

## Deferred to Future Sessions
- TOOLS-005 implementation (after PRD written this session)
- WORKSPACE-002 through WORKSPACE-006 (depend on WORKSPACE-001)
- TOOLS-004 Phase 3 (LLM-assisted parsing)
