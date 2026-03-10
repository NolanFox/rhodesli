# Session 96e-cont7 Assessment

## Shipped
- [x] **Post-deploy Supabase resync**: 938 photos, 3023 identities synced — Evidence: browser JS fetch returned `{"status":"ok","photos_synced":938,"identities_synced":3023}`
- [x] **Browser verification — Raymond Halfon photo**: Face detected, dimensions (3572x2553), source "FamilySearch" (not duplicated), collection "Immigration Records" — Evidence: screenshot ss_6615m6rhp, ss_901917htt
- [x] **Browser verification — Claude Benatar photo**: Face overlay visible (blue bounding box), 1 face detected, dimensions (1241x1891), source "Facebook" (not duplicated), collection "Jews of Rhodes: Family Memories & Heritage" — Evidence: screenshot ss_9272i9ui7
- [x] **Browser verification — Discoveries page**: "All discoveries reviewed!" with 0 high-confidence matches. BUG-7 fix confirmed (proposals not auto-applied). Help Identify shows 561 unidentified faces. — Evidence: screenshot ss_901917htt
- [x] **PRD-038 comprehensive rewrite**: Hub PRD (235 lines) + 4 sub-files (725 lines total = 960 lines). Follows PRD template. Includes: User flows, acceptance criteria, data model changes, implementation sequence, evaluation framework, retroactive improvement safety, community resilience, LoRA data growth strategy, recalibration architecture analysis.
- [x] **BACKLOG breadcrumbs**: ML-110 through ML-116 now all reference PRD-038 with workstream mapping
- [x] **Recalibration architecture analysis**: Found that existing hooks silently fail on production (sklearn not on Railway, embeddings path wrong). Documented 4 architecture options, recommended Option A (local-only).
- [x] **Research references**: Academic papers, Google Photos architecture, LoRA best practices, heritage-specific challenges documented.

## Shipped (continued)
- [x] **Upload sort fix**: Found root cause — BUG-1 wiped `upload_date` from volume JSON for photos uploaded before cont6 fix. Added backfill to `/api/sync/resync-supabase` endpoint: detects photos missing upload_date, sets current timestamp, persists to volume JSON, invalidates cache. Committed as 1e82d5e.
- [x] **Deploy triggered**: Railway CLI deploy, commit 1e82d5e.

## Deferred
- **Upload new test photo**: Deferred — existing 6 photos verified via browser.
- **External research agent**: Launched but results not fully incorporated — PRD already comprehensive from manual investigation.
- **Post-deploy browser verification of sort fix**: Deploy in progress at session end. Next session should trigger `/api/sync/resync-supabase` and verify "Upload Date (Newest)" shows recent photos first.

## Red Flags
- [MEDIUM] Deploy used RAILPACK builder instead of DOCKERFILE — may need `railway deploy` with Dockerfile flag or check railway.toml config. See Lesson 117.
- [LOW] Recalibration hooks silently failing in production — documented in PRD-038 WS-0, needs fixing in next ML session
- [LOW] `engagement_routes.py:740` uses `logging.debug` — should be `logging.warning` for visibility
- [LOW] Known flaky test `test_my_contributions_page_accessible` (ordering issue)

## Next Session Should Verify
1. Deploy completed successfully with DOCKERFILE builder (not RAILPACK)
2. Trigger `/api/sync/resync-supabase` → verify `upload_date_backfilled` count > 0
3. Verify "Upload Date (Newest)" sort shows recent photos at top
4. PRD-038 human review (Nolan) — especially recalibration architecture and LoRA data strategy
5. WS-0 (fix recalibration pipeline) should be first ML session
6. Verify `calibration_pairs` table has data from recent admin actions
