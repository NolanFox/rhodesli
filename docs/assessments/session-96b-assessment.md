# Session 96b Assessment — Charlie Fox Collection Ingest + Post-Upload Intelligence

## Status: COMPLETE (with continuation session 96c planned for deeper fixes)

## Shipped
- [x] Act 1: Orient — 636 photos validated, starting state logged
- [x] Act 2: Ingest — 636 photos, 1652 faces detected, 0 failures
- [x] Act 3: Community tagging — 636 photos tagged to fox-family in Supabase
- [x] Act 4: Auto-cluster — 35 matches (27 Roland Fox, 4 Betty Capeluto Fox, 1 Ray Franco, 3 others)
- [x] Act 5: R2 upload — 636 photos + 1653 crops, 0 failures. Pushed to production.
- [x] Act 6: Auto-cluster wired into upload pipeline (PRD-037 Phase 1)
- [x] Act 7: Cluster review dashboard + GEDCOM triage page (/admin/upload-review, 18 tests)
- [x] Bug fix: Community photo browse SHA256/inbox ID mismatch (browse_routes.py)
- [x] Act 8 (continuation): Sidebar Review section enabled for all communities
- [x] Act 8 (continuation): CI workflow fixed — venv creation so Makefile finds pytest
- [x] Act 8 (continuation): Test updated for new sidebar behavior (review visible for Fox Family)
- [x] Act 8 (continuation): Test updated for browse_routes alias-based community filter

## Deferred to Session 96c
- Fox Family still shows "0 identities" — root cause: `identity_communities` table empty, needs photo-derived identity sets (AD-216)
- Admin section still gated by `is_rhodes` — needs removal
- ML feature counts (proposals, discoveries) hardcoded to 0 for non-Rhodes — needs removal
- Upload review page not linked from sidebar — needs admin section enabled first
- Cross-community search verification for Type 2 error correction
- Browser verification deferred (deploy not yet verified in browser)

## Red Flags
- [HIGH] `identity_communities` never populated for non-Rhodes — root cause of all "0" counts. Session 96c addresses with photo-derived identity sets.
- [HIGH] Admin section (`is_rhodes` gate) blocks Fox Family admin tools. Session 96c removes gate.
- [FIXED] Sidebar Review section `if is_rhodes` gate removed (commit 7596a59)
- [FIXED] CI workflow — every push since Session 92 failed with "venv/bin/pytest: No such file" (commit d2ac392)
- [MEDIUM] Sidebar counts still 0 for Fox Family even with Review section visible — needs `_compute_sidebar_counts()` fix

## Nolan Feedback (AD-215, continued)
1. Cluster matches must be highlighted, not hidden
2. One-click reject/confirm, not navigate-find-detach
3. Intuitive cross-community splits
4. Sidebar sections needed for ALL communities — **FIXED** (Review section)
5. GEDCOM triage on same page as cluster review
6. Ray Franco is a woman — correct gender references
7. Type 2 errors (missed matches) need manual merge path with cross-community search
8. Multi-community users should see person's review items in ALL their communities

## Session 96c Planned
Full prompt at `docs/prompts/session-96c-prompt.md`. Covers:
- Photo-derived community identity sets (AD-216) — the foundation fix
- Sidebar counts + Admin section for all communities
- Community-aware discoveries
- Cross-community search + manual merge path
- Fox Family landing page identity count fix
- Browser verification

## Next Session Should Verify FIRST
1. Fox Family landing page shows N identities (not 0)
2. Fox Family sidebar shows Review section with non-zero counts
3. Fox Family admin section visible (Uploads, GEDCOM, etc.)
4. Upload review page accessible from sidebar
5. CI passes (green check on GitHub)
