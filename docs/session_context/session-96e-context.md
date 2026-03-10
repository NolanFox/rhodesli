# Session 96e Context — Fix Fox Family Clustering + Usability

**Predecessor:** [Session 96d context](session-96d-context.md)
**Date:** 2026-03-10
**Status:** IN PROGRESS — needs continuation

## What Was Done

### 1. Face Grouping Pipeline — COMPLETED
- Ran `group_inbox_identities()` from `core/grouping.py`
- 811 merges, 150 clusters formed
- INBOX went from 2084 → 1273
- Top clusters: 252 faces, 157 faces, 121 faces, 37 faces, 23 faces
- Saved to local `data/identities.json` and synced to Supabase via `shadow_write_identities_batch()`
- Production now shows: 821 New Matches, 718 Discoveries, 1 Person confirmed

### 2. Discoveries Performance Fix — DEPLOYED
- `_compute_discoveries()` in `app/main.py` line ~6390: added MAX_BATCH_DISCOVERY=200 cap
- Without proposals, batch_best_neighbor_distances for 1600+ identities causes server timeout
- Cap prevents timeout but MISSES discoveries for faces without proposals (user concern!)

### 3. Navigation Link Fix — DEPLOYED
- `neighbor_card()` in `app/main.py` line ~8123: added community URL prefix
- Links were hardcoded `/?section=...` — now use `{_nav_prefix}/?section=...`
- Fixes COMMUNITY-015: clicking neighbor from Fox Family no longer goes to Rhodes

### 4. Proposals Regenerated — DEPLOYED
- `cluster_new_faces.py --dry-run --threshold 1.3`: 2008 proposals written to proposals.json
- proposals.json is in git and OPTIONAL_SYNC_FILES for Railway volume

## What Is NOT Working Yet

### A. Discoveries Page Still Empty
- Sidebar shows "718 Discoveries" but the `/c/fox-family/api/discoveries` HTMX endpoint never returns
- Root cause: Every request triggers full Postgres reload (3 requests × 1000 identities each)
- The page render blocks computing sidebar counts (slow), then HTMX fires another request that also reloads
- Server logs show repeated `IdentityRegistry loaded from Postgres (2533 identities)` — no caching
- FIX NEEDED: The `load_registry()` function in Postgres mode has no in-memory cache with TTL

### B. Proposals Count = 0 in Sidebar
- `_compute_sidebar_counts()` reads proposals.json from disk
- On Railway volume, proposals.json may not have been synced from bundle (init_railway_volume checks content hash)
- Needs investigation: is proposals.json on the volume? Does the Railway server read it?
- The Postgres load path may not use proposals.json at all

### C. Upload Review Page Not Discoverable
- URL: `/c/fox-family/admin/upload-review`
- Sidebar has "Upload Review" link but user couldn't find it
- User feedback: should be in a notification after upload/clustering completes

### D. Help Identify = 0
- Sidebar shows 0 for Fox Family
- Needs investigation: SKIPPED identities may not exist for Fox Family

## User Feedback (MUST BE ADDRESSED)

### F1: Clustering Pipeline is Brittle
> "Our approach to clustering is very brittle. We still haven't properly solved what happens when you add incremental faces and how you refresh clusters for new batches. We need to make sure this isn't prone to catastrophic failure."

**Root cause:** `auto_cluster.py` (called in `_background_ingest`) only matches faces against EXISTING confirmed identities. It does NOT run `grouping.py` to group similar unknown faces together. This means new uploads of unknown faces just sit as individual INBOX entries.

**Fix needed:** The upload pipeline must run BOTH:
1. `auto_cluster.py` — match against confirmed identities (Tier 1/2)
2. `group_inbox_identities()` — group similar unknown faces into clusters

Wire `group_inbox_identities()` into `_background_ingest()` in `app/upload_routes.py` AFTER auto_cluster runs.

### F2: Discovery Cap Missing Matches
> "I'm concerned we are missing matches because of the 200 cap. We need to refactor to cover that many faces — maybe batches."

**Fix needed:** Instead of capping at 200, use proposals as the PRIMARY source:
- Every face should get proposals via `cluster_new_faces.py`
- `_compute_discoveries` should ONLY use proposal-based lookup (cheap, O(1) per identity)
- Remove batch_best_neighbor_distances from the hot path entirely
- Move it to a background/offline computation that feeds proposals.json

### F3: Navigation Broken for Cross-Community
> "When I click on Unidentified Person 083 it brings me to a blank page"

Partially fixed (community prefix added). But cross-community identities still navigate to wrong section. A Rhodes identity viewed from Fox Family goes to `/c/fox-family/?section=skipped` where it doesn't exist.

**Fix needed:** Cross-community identity links should go to the identity's HOME community, not the current community.

### F4: Upload Review Should Send Notification
> "Why wouldn't that be in a notification?"

The notification system exists but isn't wired to clustering completion. After upload + clustering, admin should get a notification: "635 photos processed. 150 clusters formed. 2008 matches found. Review: /c/fox-family/admin/upload-review"

### F5: Page Load Extremely Slow
> "This page is loading slower than ever"

Root cause: Every page request triggers full Postgres reload of 2533 identities (3 HTTP requests to Supabase). No in-memory TTL cache for the Postgres-loaded registry.

**Fix needed:** Add TTL cache to `load_registry()` when DATA_SOURCE=postgres. Cache for 30-60s in memory, invalidate on save_registry().

## Architecture Issue: Postgres Registry Caching

The server logs show `IdentityRegistry loaded from Postgres (2533 identities)` on EVERY request. With 2533 identities fetched in 3 pages of 1000, each page load makes 3+ HTTP calls to Supabase. This is why:
1. Pages load slowly
2. The discoveries API times out (it triggers ANOTHER full reload)

`load_registry()` in `app/main.py` needs a `_registry_cache` with 30-60s TTL, similar to the existing `_community_ids_cache_ts` pattern. Invalidate on `save_registry()`.

## Commits Made
- `7b45d2c` — fix(community): run face grouping + fix discoveries timeout + navigation links

## Files Changed
- `app/main.py` — discoveries cap, neighbor_card community prefix
- `data/identities.json` — 811 merges applied
- `data/proposals.json` — 2008 proposals at threshold 1.3

## Next Steps (Priority Order)
1. Add TTL cache to `load_registry()` for Postgres mode — fixes page speed AND discoveries timeout
2. Wire `group_inbox_identities()` into upload pipeline (`_background_ingest`)
3. Make `_compute_discoveries` proposal-only (remove batch computation from hot path)
4. Fix cross-community navigation links (link to home community)
5. Wire notification after clustering completion
6. Verify discoveries page works after registry caching fix
7. Verify proposals count in sidebar
