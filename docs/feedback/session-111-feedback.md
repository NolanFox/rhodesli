# Session 111 Feedback — Interactive Fox Family Upload Review

## P0 — Data Integrity

### FB-029: Rhodes photos appearing in Fox Family upload review (DATA BREACH)
- **Severity:** P0 (data integrity — SHOWSTOPPER)
- **Context:** Multiple Rhodes community photos showing up in Fox Family speed-run upload review. Examples:
  - Person 5b3ba844: 4 faces from howie_frano_collection (Rhodes) incorrectly clustered together and showing in Fox Family review
  - Person 746: 3 faces from uriel_galante_collection (Rhodes batch community-batch-20260214) in Fox Family review
  - Person 3542: 12 faces from Rhodes community in Fox Family review
- **Root cause (investigated):** Two issues:
  1. `group_inbox_identities()` in core/grouping.py operates globally with NO community filter — merges faces across communities
  2. Speed-run community filter (`_get_speed_run_clusters`) relies on `_get_community_identity_ids()` which may be failing to exclude Rhodes identities, possibly because photo_communities table entries are missing or wrong
- **Impact:** Admin wastes time reviewing wrong community's data. Worse: could accidentally confirm/merge Rhodes faces into Fox Family identities. This has been "fixed" multiple times in previous sessions (DATA-019, Session 102) but keeps recurring.
- **Fix:** IMMEDIATE — community filter on grouping pipeline + audit speed-run filter
- **BACKLOG:** DATA-022

### FB-030: Cluster count not incrementing / resetting
- **Severity:** P1 (UX — gamification broken)
- **Context:** Speed-run shows "35 clusters reviewed" but the count was higher earlier during the Esther Burd Fox review. Count appears to reset or not persist across page loads/actions. The counter is supposed to gamify the review process and show progress toward completion.
- **Root cause:** TBD — likely counter stored client-side and lost on page reload, or server-side counter not persisting
- **Fix:** TBD
- **BACKLOG:** UX-094

## P1 — UX

### FB-025: Speed-run latency too slow for efficient triage
- **Severity:** P1 (performance)
- **Context:** Loading each cluster in upload review is too slow to "breeze through" the review. Latency blocks the fast-triage workflow the speed-run is designed for.
- **Root cause:** Likely neighbor computation, registry lookups, or Supabase queries on each cluster load
- **Fix:** BACKLOG — profile and optimize the speed-run cluster loading path
- **BACKLOG:** PERF-008

### FB-026: Suggested matches sorted by face count, not ML similarity
- **Severity:** P1 (UX — wrong sort order)
- **Context:** After confirming a cluster that is clearly Esther Burd Fox, the "Suggested Matches" list shows Charles Fox (106 faces) first, then Roland Fox (64), Albert Fox (57), and Esther Burd Fox (31) fourth. Should be sorted by embedding distance so the best ML match appears first.
- **Root cause:** `_get_confirmed_identity_suggestions()` in cluster_review_routes.py sorts by `-s["face_count"]` instead of embedding distance
- **Fix:** IN PROGRESS — modified to use `_compute_top_neighbors()` for ML-based ranking
- **BACKLOG:** UX-095

### FB-027: After merge in speed-run, should auto-advance to next cluster
- **Severity:** P1 (UX — workflow friction)
- **Context:** After clicking Merge on a suggestion (e.g., merging into Esther Burd Fox), the user must manually scroll down and click "Go to next cluster." The system already knows who the person is and where they are in the tree. Should auto-advance unless GEDCOM link is needed.
- **Flow should be:** Merge → if tree-linked, auto-advance with persistent notification → if not tree-linked, show Link to Tree panel → then auto-advance
- **Fix:** BACKLOG — requires HTMX response chain modification
- **BACKLOG:** UX-096

### FB-028: Merge notification should persist to next screen
- **Severity:** P2 (UX — feedback)
- **Context:** When a merge happens and the system auto-advances, the notification/toast confirming the merge should persist into the next cluster view so the user knows what happened (in case they missed it).
- **Fix:** BACKLOG — toast persistence across HTMX swaps
- **BACKLOG:** UX-097

## P1 — Pre-existing (from before this session)

### FB-031: Face grid on identity card gear/settings click is broken
- **Severity:** P1 (UX — visual)
- **Context:** Clicking the gear icon on a confirmed identity card in the People section expands a face grid that is completely distorted — faces overlap, labels pile on each other, layout broken. Should display faces in a clean grid like the compare tool does, taking full width and pushing other content up/down.
- **Root cause:** face_card() had `min-w-[150px]` causing overflow in narrow grid containers. Grid was `grid-cols-3 sm:grid-cols-4` which doesn't work in the narrow identity card context.
- **Fix:** IN PROGRESS — removed min-width, changed to responsive `grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3`
- **BACKLOG:** UX-098

### FB-032: Public /c/fox-family/people not community-scoped
- **Severity:** P1 (UX — data leak to public)
- **Context:** In incognito, visiting /c/fox-family/people shows ALL 104 confirmed identities across all communities (Rhodes people like Abraham Almaleh, Abraham Capuano visible). Should only show Fox Family people. This was supposed to be fixed in COMMUNITY-001 (Session 96) but the people page was missed.
- **Root cause:** browse_routes.py `/people` route loads all confirmed identities without filtering by community. `_get_community_identity_ids()` is never called.
- **Fix:** IN PROGRESS — added community filter using `_get_community_identity_ids(community)`
- **BACKLOG:** COMMUNITY-015 (existing)

### FB-033: CI tests failing on GitHub
- **Severity:** P1 (infrastructure)
- **Context:** GitHub Actions test run failing on `test_upload_date_propagated_for_inbox_photos` — upload_date not propagated in _photo_cache when photo IDs mismatch between photo_index.json (inbox_*) and _photo_cache (SHA256).
- **Root cause:** `_build_caches()` populates `filename_to_metadata` only from photo_registry, not from raw photo_index.json data. When IDs mismatch, the fallback path misses metadata like upload_date.
- **Fix:** IN PROGRESS — added `filename_to_metadata` population from `best_raw_entries`
- **BACKLOG:** CI-001

### FB-034: More Rhodes clusters in Fox Family (recurring)
- **Severity:** P0 (data integrity)
- **Context:** uriel_galante_collection photos (community-batch-20260214) appearing as Person 746 cluster in Fox Family speed-run. Same root cause as FB-029.
- **Fix:** FIXED — same fix as FB-029 (community slug fallback)

### FB-035: Bad cluster quality — different Fox Family people grouped together
- **Severity:** P2 (ML quality)
- **Context:** Person 2820 has 5 faces from fox-charlie-001 collection that appear to be different people. All ARE Fox Family photos (not a community leak). The grouping threshold (0.95) may be too loose for low-quality/partial face crops from old photos.
- **Root cause:** group_inbox_identities() threshold too permissive for degraded face crops
- **Fix:** BACKLOG — tighten threshold or add quality-aware clustering
- **BACKLOG:** ML-102

### FB-036: Speed Loop tagging broken — tags don't persist (BUG-001 regression)
- **Severity:** P0 (data loss)
- **Context:** In Speed Loop (/photo/{id}?seq=1), user types "Charles" and selects "Charles Fox" from dropdown. The tag panel shows the selection but the assignment does NOT persist. Same as BUG-001 from previous sessions. Nolan called this "the exact same bug we fixed yesterday."
- **Root cause:** BUG-001 was never fully fixed — the tag assignment endpoint silently fails
- **Fix:** BACKLOG — BUG-001 (existing, needs root cause investigation)

### FB-037: Speed Loop tagging broken on second photo too + slowness
- **Severity:** P0 (data loss + performance)
- **Context:** Same tagging failure as FB-036 on a different photo (group photo with 10 faces). Also, everything in the Speed Loop is "very very slow."
- **Fix:** Same as FB-036 + PERF-008

### FB-038: "View More" in Similar Identities panel resets all checkboxes
- **Severity:** P2 (UX — state loss)
- **Context:** User checked several identities for batch merge, then scrolled down and clicked "View More" to load additional suggestions. The HTMX swap replaced the DOM and lost all checkbox state. User had to re-check everything.
- **Root cause:** HTMX innerHTML swap replaces the entire list, losing client-side checkbox state
- **Fix:** BACKLOG — preserve checked state in hidden field or use hx-swap="beforeend" for pagination
- **BACKLOG:** UX-099

### FB-039: Batch merge reports "14 confirmed, 11 failed" — confusing
- **Severity:** P1 (UX — misleading feedback)
- **Context:** User selected multiple identities and clicked "Merge Selected." Response said "14 confirmed, 11 failed." The failures are likely co-occurrence blocks (faces appear in the same photo). But the message doesn't explain WHY they failed or which ones.
- **Root cause:** Co-occurrence blocker silently rejects merges without per-identity feedback
- **Fix:** BACKLOG — show per-identity success/failure with reason ("blocked: faces appear in same photo")
- **BACKLOG:** UX-100

### FB-040: Merge succeeded but stale card remains in inbox
- **Severity:** P1 (UX — stale DOM)
- **Context:** After merge, the identity card was still visible in the inbox list. User had to inspect the photo to confirm the merge actually worked. The "14 confirmed, 11 failed" message made them think it failed for Charles Fox specifically, but it hadn't.
- **Root cause:** HTMX merge response doesn't remove the source card from the inbox. Card needs to be swapped out with OOB swap or removed after merge.
- **Fix:** BACKLOG — after merge, remove the merged-from card via OOB swap
- **BACKLOG:** UX-101
