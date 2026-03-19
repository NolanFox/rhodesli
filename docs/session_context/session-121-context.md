# Session 121 Context — Upload Verification + UX Fix Sprint + Planning

**Predecessor:** [Session 120 Context](session-120-context.md) (ML Comparison Script + UX Fix Sprint)
**Assessment:** [Session 120 Assessment](../assessments/session-120-assessment.md)
**Feedback:** [Session 119 Feedback](../feedback/session-119-feedback.md)

## Problem Statement

Session 120 shipped the ML comparison script, Sentry root cause fix, and 4 UX fixes (FB-009, FB-008, FB-001, FB-011). But AD-229 still needs 2 more criteria verified, 3 quick UX fixes remain from Session 119 feedback, and 2 larger features (TOOLS-003, WORKSPACE-001) need planning artifacts.

## Items

### 1. AD-229 Cosine Comparison Verification
- Script: `scripts/compare_ml_embeddings.py` (Session 120)
- Criteria: cosine similarity >= 0.999 between local and ML service embeddings
- Status: Script exists, needs to be run with real ML service
- Requires: ML_SERVICE_URL env var (Railway internal URL or admin endpoint)
- **Challenge**: ML service is on Railway internal network. Script can't reach it from local.
- **Options**: (a) Run via Railway CLI one-off, (b) Add admin proxy endpoint `/api/admin/ml-compare`, (c) Document as manual verification step
- **Decision**: Add lightweight admin endpoint that proxies to ML service, returns embeddings. Script calls that.
- Files: `app/admin_routes.py` (new endpoint), `scripts/compare_ml_embeddings.py` (add --url flag)
- AD-229 full criteria: 1) 24h uptime, 2) 3 uploads, 3) cosine >= 0.999, 4) billing <= $5/mo

### 2. UX-211: Face Overlay Buttons Too Small on Group Photos (P1)
- Face overlays in `app/page_routes.py:3780-3860`
- CSS in `app/main.py:1005-1034`
- Percentage-based sizing from bbox — no minimum size
- Fix: Add minimum click target size (44px per mobile guidelines)
- Add "click face to select, then act from panel" interaction for dense photos
- **This is a CSS + interaction fix, NOT a PRD** — the core behavior stays the same
- Files: `app/page_routes.py`, `app/main.py` (CSS)

### 3. UX-207: Approvals Not Community-Scoped (P1)
- Pending uploads loaded from `data/pending_uploads.json` via `_load_pending_uploads()`
- Each entry HAS a `community` field (set in upload_routes.py)
- Admin list shows ALL pending uploads regardless of community
- Fix: Filter by `request.state.community` in admin approval list
- Files: `app/admin_routes.py`, `app/main.py`

### 4. TOOLS-003: Face Compare Real-Time (Planning Only)
- PRD-034 documents the feature
- ML service is deployed (TOOLS-002 complete)
- Two paths: ONNX export vs ML service extension
- **This session**: Write PRD for TOOLS-003 implementation path
- Investigate: Does ML service `/api/v1/detect-and-embed` return embeddings suitable for compare?
- Files: `docs/prds/` (new PRD), `app/compare_routes.py` (read only)

### 5. WORKSPACE-001: Personal Archive Auto-Creation (Planning Only)
- PRD-036 exists at `docs/prds/036_workspace_onboarding.md`
- **This session**: Validate PRD against current codebase, add schema migration plan
- Schema: communities table needs `owner_id`, `is_personal`, `privacy` columns
- Files: `docs/prds/036_workspace_onboarding.md` (review), context file (plan)

### 6. UX-212: Source URL Not Saved During Upload (P2)
- Upload form HAS source_url field, JavaScript appends to FormData
- source_url IS saved to pending_uploads.json
- **Root cause hypothesis**: Not propagated when approval copies to photo record
- Trace: approval flow in admin_routes.py → photo_index.json write
- Files: `app/admin_routes.py` or `app/upload_routes.py`

### 7. UX-208: Always Show Community Badge on Suggestion Cards (P2)
- `_cross_community_badge()` in `app/main.py:549-590`
- Returns None for same-community (line 573) — this hides the badge
- Fix: Return a "same community" badge instead of None
- Also apply in `neighbor_card()` at main.py:9139
- Files: `app/main.py`

## Parallelization Plan

### File Dependency Analysis
| Track | Files Touched | Overlap? |
|-------|--------------|----------|
| AD-229 endpoint | admin_routes.py, compare_ml_embeddings.py | admin_routes.py |
| UX-211 | page_routes.py, main.py (CSS) | main.py |
| UX-207 | admin_routes.py, main.py | admin_routes.py, main.py |
| UX-212 | upload_routes.py or admin_routes.py | admin_routes.py |
| UX-208 | main.py | main.py |
| TOOLS-003 PRD | docs/prds/ (new) | None |
| WORKSPACE-001 plan | docs/prds/ (existing), context | None |

### Execution Strategy
**Phase 0**: Orient (sequential on main)
**Worktree A**: UX-211 (page_routes.py + main.py CSS only)
**Worktree B**: TOOLS-003 PRD + WORKSPACE-001 plan (docs only, no code)
**Sequential on main**: AD-229 endpoint → UX-207 → UX-212 → UX-208 (all touch admin_routes.py or main.py)
**Phase 8**: Harness outputs + browser verification + gap check

Note: UX-207, UX-212, and AD-229 all touch admin_routes.py — must be sequential.
UX-208 touches main.py which UX-211 also touches — but UX-211 only touches CSS section while UX-208 touches badge logic (~line 549). Can parallelize if careful, but safer sequential.

## Breadcrumbs
- AD-229: `docs/ml/ALGORITHMIC_DECISIONS.md` (lines 2672-2684)
- UX-206-215: `docs/BACKLOG.md` (Session 119 feedback items)
- TOOLS-003: `docs/prds/034_standalone_tool_suite.md`
- WORKSPACE-001: `docs/prds/036_workspace_onboarding.md`
- Session 120 assessment: `docs/assessments/session-120-assessment.md`
- Lesson 149: Browser READ-ONLY on production
