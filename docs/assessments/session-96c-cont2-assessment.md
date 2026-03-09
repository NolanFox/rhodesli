# Session 96c-cont2 Assessment

## Shipped
- [x] P0: Fox Family admin view — admins now get admin section, not landing page
  - Evidence: `page_routes.py:1820` — admin check added before community landing redirect
- [x] P1: David Capeloto photo restored — re-ingested from ~/Downloads, uploaded to R2, synced to Supabase
  - Evidence: `data/photo_index.json` has 932 photos (was 931), face inbox_aca56b9475f5 in face_to_photo
  - Root cause: partial sync from production (identities.json synced, photo_index did not)
- [x] P1: Data integrity validator — `scripts/validate_data_integrity.py` + tests
  - Evidence: `tests/test_data_integrity.py` TestOrphanedIdentities class (3 tests)
  - Catches: orphaned anchor faces, broken face_to_photo links, null names
- [x] P2: Dismissed section card sizing — now uses grid layout matching People section
  - Evidence: `app/main.py:6704` — grid-cols-2/3/4/5 layout
- [x] P1: Test notification deleted from Supabase
- [x] P3: Debug endpoint /api/debug/community-ids removed
- [x] Data cleanup: Netanel Menashe orphaned faces removed, CONTESTED null name fixed

## Deferred
- Browser verification blocked by Railway GitHub connectivity issues (all deploys QUEUED)
- P1: Fox Family People page showing 0 — need browser verify (may work after deploy)
- P1: Cross-community matches visibility in Upload Review — proposals exist (35), need UI verification
- P2: "Photo not found" in Dismissed section — data issue (orphaned production-only faces), not code bug
- P3: Community boundary UX (labels on notifications, search results) — needs design work

## Prevention: David Capeloto Incident
**Root cause:** Production-local data divergence (Lesson 78, 5th occurrence).
Identity was created on production via web upload. identities.json was synced to git,
but photo_index.json, embeddings.npy, and the photo file were NOT synced.

**Prevention implemented:**
1. `scripts/validate_data_integrity.py` — run before deploy to catch orphaned data
2. `TestOrphanedIdentities` in test suite — blocks commit if CONFIRMED identity has orphaned faces
3. Ingest pipeline already writes to Supabase (added in 96c-cont)

**Remaining prevention gap:** No automated check that production volume data stays in sync with git.
Need: a post-deploy validation endpoint that checks data integrity on the running server.

## Red Flags
- [MEDIUM] Railway deploy using RAILPACK instead of DOCKERFILE for git-push deploys — railway.toml not being read. Previous deploys used Dockerfile correctly. May be a Railway platform regression.
- [LOW] 3 pre-existing test failures (test_gallery_has_face_cards, test_community_landing_page_with_content, test_my_contributions_page_accessible) — test ordering issues, not related to our changes.
- [INFO] 125 "CRITICAL" entries in integrity validator — faces in identities.json not in embeddings.npy. These are production-only faces (community uploads, newspaper.com batch) that were never synced locally. Expected for now but should be resolved when ML service extraction moves face detection to cloud.

## Next Session Should Verify
1. Railway deploy completes and all fixes are live
2. Fox Family admin view shows sidebar + to_review
3. Fox Family Photos page shows 636 photos
4. David Capeloto appears in Rhodes People section (86/86 confirmed)
5. Cross-community proposals visible in Discoveries or Upload Review
6. Dismissed section cards are grid-sized
