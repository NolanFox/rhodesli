# Session 96e — Fix Fox Family Performance + Clustering Pipeline

**Context:** `docs/session_context/session-96e-context.md` (READ THIS FIRST — contains all research, findings, user feedback)
**Priority:** P0 — Fox Family unusable, user blocked
**Previous commit:** `7b45d2c` — face grouping ran, discoveries cap, nav fix deployed

---

## What's Already Done
- Face grouping: 811 merges, 150 clusters, synced to Supabase (2533 identities)
- Proposals: 2008 at threshold 1.3 in `data/proposals.json`
- Code fixes deployed: discoveries 200-cap, neighbor_card community prefix
- BUT: Discoveries page still empty (API timeout), Proposals sidebar = 0, pages very slow

## Act 1: Fix Postgres Registry Caching (ROOT CAUSE of ALL slowness)

The server reloads ALL 2533 identities from Supabase on EVERY page request (3 HTTP calls).
This is why everything is slow and the discoveries API times out.

1. In `app/main.py`, find `load_registry()` function
2. Add a `_registry_cache` + `_registry_cache_ts` with 30s TTL (same pattern as `_community_ids_cache`)
3. In `save_registry()`, invalidate the cache (`_registry_cache = None`)
4. In `_invalidate_all_caches()`, also invalidate `_registry_cache`
5. Test: page load should be fast, discoveries API should return

Commit. /clear.

## Act 2: Make Discoveries Proposal-Only (Remove Batch Computation)

The `_compute_discoveries()` function tries to run `batch_best_neighbor_distances()` for identities without proposals. This is O(n*m) and too slow for the server.

1. Remove the `MAX_BATCH_DISCOVERY` cap AND the batch computation block entirely
2. Instead, make discoveries ONLY proposal-based: iterate proposals.json, check targets against confirmed_ids
3. Any identity without a proposal simply doesn't appear in discoveries (they appear in "Unmatched" on the To Review page instead)
4. This makes discoveries O(p) where p=number of proposals — fast and predictable
5. Verify: sidebar count should match API card count

Commit. /clear.

## Act 3: Wire Grouping Into Upload Pipeline

**User feedback F1:** Clustering is brittle — `auto_cluster.py` doesn't group unknown faces.

1. In `app/upload_routes.py`, find `_background_ingest()` function
2. After the auto_cluster step, add a call to `group_inbox_identities(dry_run=False)`
3. Pass appropriate registry, face_data, and photo_registry
4. Save the registry after grouping
5. Log the grouping result (groups formed, merges, etc.)
6. Test: mock test that verifies grouping is called after auto_cluster

Commit. /clear.

## Act 4: Fix Proposals Count + Upload Review Discoverability

1. **Proposals = 0**: Check if proposals.json is read correctly on production (Postgres mode)
   - May need to write proposals to Supabase instead of JSON, or ensure JSON is on volume
   - Check `_load_proposals()` function — does it read from DATA_DIR?
2. **Upload Review link**: Add a prominent link/banner on the Fox Family main page when proposals > 0
   - E.g., "150 clusters found — Review matches" banner above the identity grid
3. Wire notification: After clustering completes in `_background_ingest`, call notification system

Commit. /clear.

## Act 5: Fix Cross-Community Navigation

**User feedback F3:** Clicking cross-community identity goes to blank page.

1. In `neighbor_card()`, when `_cross_community_badge` exists for a neighbor, the link should go to the identity's HOME community, not the current community
2. Look up which community the neighbor belongs to (check `_get_community_identity_ids` or `identity_communities` table)
3. If neighbor is from Rhodes, link to `/person/{neighbor_id}` (Rhodes default)
4. If neighbor is from fox-family, link to `/c/fox-family/?section=...`

Commit. /clear.

## Act 6: Browser Verify ALL Fixes

Navigate in Chrome browser and verify:
1. Fox Family page loads in <5 seconds (registry caching)
2. Discoveries page shows actual cards (not empty)
3. Proposals count > 0 in sidebar
4. Clicking neighbor identity navigates correctly
5. Upload Review page accessible and shows clusters
6. Rhodes pages still work (no regression)

## Act 7: Session Wrap
1. Update BACKLOG with new items from user feedback (F1-F5)
2. Update ROADMAP
3. Write assessment
4. Update lessons.md with Lesson 111: "Postgres registry needs TTL cache — every request reloading 2533 identities caused complete feature failure"

## User Feedback to Track (from session-96e-context.md)
- F1: Clustering pipeline must run grouping + auto-cluster on upload
- F2: Discovery cap loses matches — make proposal-only instead
- F3: Cross-community navigation links to wrong community
- F4: Notification after clustering completion
- F5: Page load extremely slow (Postgres no-cache root cause)
