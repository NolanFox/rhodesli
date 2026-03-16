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

## Session 111 Continuation (after crash recovery)

### FB-041: Compare page links drop community context (P0)
- **Severity:** P0 (community middleware — RECURRING)
- **Context:** From Fox Family compare screen, clicking a face overlay to navigate to a person page (e.g., Person 3948) redirects to `/?section=to_review&view=browse#identity-{id}` — missing `/c/fox-family/` prefix. Lands in Rhodes community. Same bug class as FB-032.
- **Root cause:** compare_routes.py had ZERO community awareness — no `nav_prefix`, no `community_slug` anywhere in the file. All `/person/{id}` links and `/?section=` navigation hardcoded without community prefix.
- **Fix:** FIXED — added community prefix to all 13 route handlers + 2 helpers in compare_routes.py. Also fixed same issue in engagement_routes.py, upload_routes.py, admin_routes.py, page_routes.py.

### FB-042: Help Identify section purpose unclear (P1)
- **Severity:** P1 (UX — information architecture)
- **Context:** Help Identify shows only 1 item. Unclear how it differs from New Matches (902 items) or Discoveries (157). Both photos in the Help Identify pair are from the same initial upload batch (Charles Fox collection). Why is this one flagged? The section subtitle says "faces we need your help with" but that describes ALL unidentified faces. The distinction between Help Identify vs New Matches vs Discoveries is not clear to the admin.
- **Root cause:** Help Identify was designed for community-contributed identifications, but with only admin usage and no external contributors, it surfaces SKIPPED faces that have ML matches — which overlaps with Discoveries.
- **Fix:** BACKLOG — needs information architecture review. Consider merging Help Identify into Discoveries or making the distinction explicit.
- **BACKLOG:** UX-102

### FB-043: Help Identify face crops too small to compare (P1)
- **Severity:** P1 (UX — visual)
- **Context:** In Help Identify Focus mode, the "WHO IS THIS?" and "BEST MATCH" face crops are extremely zoomed/cropped. Can't meaningfully compare the faces because there's no surrounding context. The Photo Context section below helps but requires scrolling.
- **Fix:** BACKLOG — show full photo crops or at least larger face regions with context
- **BACKLOG:** UX-103

### FB-044: Person 3606 appears in both BEST MATCH and Similar Identities (P1)
- **Severity:** P1 (UX — redundancy/confusion)
- **Context:** In Help Identify, Person 3606 appears as the "BEST MATCH" on the right, AND also appears as the first entry in "Similar Identities" below with "50% match". This is confusing — is the user supposed to review the top match separately from the similar identities list? The best match should be excluded from the similar list, or the UX should make the relationship clear.
- **Fix:** BACKLOG — exclude best match from Similar Identities list, or consolidate
- **BACKLOG:** UX-104

### FB-045: Help Identify Focus mode UX differs from other Focus modes (P2)
- **Severity:** P2 (UX — inconsistency)
- **Context:** Focus mode in Help Identify has completely different UX from Focus mode in New Matches or Speed Run. Different layout, different actions, different flow. No reason for this inconsistency — creates cognitive overhead switching between sections.
- **Fix:** BACKLOG — unify Focus mode UX across sections
- **BACKLOG:** UX-105

### FB-046: "More Matches" meaning unclear (P2)
- **Severity:** P2 (UX — labeling)
- **Context:** Below the BEST MATCH, there's a "MORE MATCHES" section with 4 thumbnails. Not clear if these are more matches for the left photo (Person 2479) or alternative matches. The relationship to "Similar Identities" below is also unclear.
- **Fix:** BACKLOG — clarify labeling and relationship between sections
- **BACKLOG:** UX-106

### FB-047: "View in Admin Queue" link drops community (P0)
- **Severity:** P0 (community middleware — RECURRING)
- **Context:** From `/identify/{id}` page, clicking "View in Admin Queue" navigates to `/?section=to_review&view=browse#identity-{id}` — missing `/c/fox-family/` prefix. Lands in Rhodes community. User had to manually copy-paste the UUID and construct the URL.
- **Root cause:** Same as FB-041 — hardcoded links without community prefix in identify/person routes.
- **Fix:** FIXED — covered by the community prefix fix across all route files.

### FB-048: No direct path from face card to person page in tagging view (P1)
- **Severity:** P1 (UX — dead end)
- **Context:** In Speed Loop tagging view (`/photo/{id}?seq=1&face={face_id}`), clicking on a face card with the tag popup shows the identity name but there's no link to navigate to that person's page. User can see "Unidentified Person 2479" but can't click through to see their other photos or similar matches.
- **Fix:** BACKLOG — add "View Person" link in face tag popup
- **BACKLOG:** UX-107

### FB-049: Sentry PYTHON-ASGI-13 — _load_annotations AttributeError (P1)
- **Severity:** P1 (infrastructure — recurring)
- **Context:** Sentry alert: `AttributeError: partially initialized module 'app.engagement_routes' has no attribute '_load_annotations'`. Circular import timing issue between app.main and app.engagement_routes. Pre-existing, not caused by today's changes.
- **Root cause:** app.main line 10580 does `_load_annotations = engagement_routes._load_annotations` during module init. If engagement_routes hasn't finished loading when this runs, the attribute doesn't exist yet.
- **Fix:** BACKLOG — refactor circular import or use lazy import pattern
- **BACKLOG:** INFRA-005

### FB-050: GitHub CI test failure on commit 2e1fb2d (P1)
- **Severity:** P1 (infrastructure)
- **Context:** GitHub Actions test run failing. Likely same pre-existing test failures (test_partial_has_public_page_link, test_upload_date_propagated_for_inbox_photos).
- **Fix:** BACKLOG — fix pre-existing test failures
- **BACKLOG:** CI-002

### FB-051: Photo filename search still not working (P1 — RECURRING)
- **Severity:** P1 (UX — regression from FB-007/FB-015)
- **Context:** User reports "still no way to search by the photo name" despite FB-015 being marked DONE in Session 108b. Code exists in `/api/search` but may have issues: (1) search results link to `/photo/{id}` without community prefix, (2) the `_photo_cache` may not be populated in production, (3) sidebar search input may not be triggering the right endpoint.
- **Root cause:** TBD — need to verify search works end-to-end in production
- **Fix:** IN PROGRESS — adding community prefix to search results + investigating

### FB-052: "Confirm" button doesn't merge with suggested match — misleading UX (P0)
- **Severity:** P0 (UX — critical workflow confusion)
- **Context:** Card shows "STRONG MATCH — Likely Charles Fox (69%) (+7 additional)" with face thumbnails. User expects "Confirm" to mean "Yes, this IS Charles Fox" and merge the faces into Charles Fox's identity. Instead, Confirm just promotes Person 791fb268 to CONFIRMED as a NEW separate person. To actually merge with Charles Fox, user must: click Similar → find Charles Fox → click Merge. That's 3-4 clicks for what should be 1 click.
- **Impact:** Misleading to anyone who doesn't understand the internal data model. The UI asserts "this is Charles Fox" then doesn't act on it when you confirm. Creates duplicate confirmed identities instead of merging.
- **Proposed fix:** When a STRONG MATCH exists, change Confirm to "Confirm as Charles Fox" which does confirm + merge in one action. Keep a separate "Confirm as New Person" for cases where the match is wrong. This is how Google Photos works — "Is this [Name]?" with Yes/No.
- **BACKLOG:** UX-108

### FB-053: Identity IDs inconsistent — mix of numbers and hex hashes (P2)
- **Severity:** P2 (UX — visual consistency)
- **Context:** Some identities display as "Person 3606" (sequential number), others as "Person 791fb268" (hex hash prefix). The mix looks unprofessional and confusing. User wants consistency — either all numbers or all hex, but numbers look nicer.
- **Root cause:** Legacy identities from initial clustering got sequential "Unidentified Person NNN" names. Newer identities from inbox pipeline get UUID-based IDs displayed as first 8 hex chars. The display name is set at creation time and never unified.
- **Proposed fix:** Assign sequential display numbers to all identities. Keep UUIDs as internal IDs but show "Person 1", "Person 2", etc. as display names. Would need a one-time renumbering migration.
- **BACKLOG:** UX-109

### FB-054: Thumbnail mismatch in Similar Identities — Person 3124 crop doesn't match actual person (P0)
- **Severity:** P0 (data integrity — CRITICAL)
- **Context:** In Similar Identities for Person 791fb268, Person 3124 shows a thumbnail that doesn't match what appears when clicking Compare. The Compare view shows a completely different face photo for Person 3124. This means crop files are mismatched with identity records. Same class of bug as previous data integrity issues with Rhodes photos.
- **Root cause:** TBD — investigating. Likely crop file mapped to wrong identity, or face_id/crop filename mismatch after merge/regroup operations.
- **Fix:** INVESTIGATING — need to trace crop resolution path for Person 3124
- **BACKLOG:** DATA-023

### FB-055: Select All checkbox doesn't check individual checkboxes (P1 — RECURRING)
- **Severity:** P1 (UX — broken feature)
- **Context:** In Similar Identities panel, clicking "Select All" toggles the master checkbox (turns blue) but doesn't actually select the individual identity checkboxes below. Was reported in previous session, acknowledged, but never fixed.
- **Root cause:** TBD — likely JS event delegation issue or checkbox name mismatch
- **Fix:** BACKLOG
- **BACKLOG:** UX-110

### FB-056: Multi-merge always reports failures — co-occurrence blocking (P1 — RECURRING)
- **Severity:** P1 (UX — misleading + broken)
- **Context:** Every multi-merge operation shows yellow warning "Merged 2 identities (23 faces). 3 failed." The failures are co-occurrence blocks (faces in same photo can't be in same identity). But: (1) the message doesn't explain WHY, (2) it happens EVERY TIME making the feature feel broken, (3) it's unclear which identities failed and which succeeded.
- **Root cause:** Co-occurrence blocker silently rejects merges. Same as FB-039.
- **Fix:** BACKLOG — same as FB-039/UX-100. Need per-identity success/failure with reason.
- **BACKLOG:** UX-100 (existing)

### FB-057: Focus mode doesn't auto-advance after action — requires manual refresh (P1)
- **Severity:** P1 (UX — workflow broken)
- **Context:** In New Matches Focus mode, after confirming/skipping/rejecting an identity, the page doesn't advance to the next person. User must manually refresh the page each time. Defeats the purpose of Focus mode which is supposed to be a fast triage flow.
- **Root cause:** TBD — HTMX response from confirm/skip/reject doesn't swap in the next identity card
- **Fix:** BACKLOG
- **BACKLOG:** UX-111

### FB-058: Thumbnail in Similar Identities doesn't match default displayed photo (P1 — clarification of FB-054)
- **Severity:** P1 (UX — visual confusion)
- **Context:** Clarification from user: the thumbnail mismatch for Person 3124 is NOT a data integrity issue. The identity has multiple face crops, and the thumbnail shown in the Similar Identities list is a different crop than the "default first picture" shown when you click into the person's Compare view. You have to click through faces to find the one matching the thumbnail. This is confusing because it makes you think there's a data error when it's actually just showing a different face from the same person.
- **Root cause:** Thumbnail selection in Similar Identities uses a different face crop (likely first anchor_id) than the Compare view's default display (likely highest quality or first in list).
- **Fix:** BACKLOG — unify thumbnail selection so the same face is shown everywhere for a given identity
- **BACKLOG:** UX-112

### FB-059: Discovery tab extremely slow to load — appears broken (P1)
- **Severity:** P1 (performance — CRITICAL UX)
- **Context:** Discovery tab takes so long to load that the user thinks it's not working at all. No loading indicator, just a blank/stale page for many seconds.
- **Root cause:** TBD — likely heavy neighbor computation or Supabase queries without caching
- **Fix:** BACKLOG — profile Discovery load path, add loading indicator
- **BACKLOG:** PERF-009

### FB-060: No easy way to compare photos from Discovery tab (P1)
- **Severity:** P1 (UX — missing workflow)
- **Context:** From the Discovery tab, there's no direct "Compare" button to quickly compare a discovered match with the suggested identity. User had to manually construct the compare URL: `/tools/compare?face_id=inbox_e514be13974b&person_id=429cf1b6-04be-475d-9a9d-a3f37dd2f1db`. Should be one click.
- **Fix:** BACKLOG — add Compare button to Discovery cards
- **BACKLOG:** UX-113

### FB-062: "Merged 1 identities (3 faces). 4 failed." — Person 84de0218 (P0 — RECURRING)
- **Severity:** P0 (UX — recurring, blocks triage workflow)
- **Context:** Screenshot shows Person 84de0218 (3 faces, STRONG MATCH Esther Burd Fox 68%). Yellow warning: "Merged 1 identities (3 faces). 4 failed." This is the SAME pattern as FB-039/FB-056 — co-occurrence blocker silently fails without explaining WHY or WHICH identities failed. User has no way to know what to do next.
- **Fix:** Same root cause as FB-039/FB-056. Need: (1) per-identity success/failure with reason, (2) Confirm button that merges with the suggested match (FB-052)
- **BACKLOG:** UX-100 (existing)

### FB-063: Person page /person/{id} lacks community prefix — Similar Identities broken (P0 — RECURRING)
- **Severity:** P0 (community middleware — CRITICAL RECURRING)
- **Context:** Debbie Fox Schapiro person page at `rhodesli.nolanandrewfox.com/person/67e830ac...` — NO `/c/fox-family/` prefix. Similar Identities shows Person 3037 and Person 3462 (both Fox Family photos) but all links (Compare, Merge, Not Same) lack community context. User navigated here from Rhodes collection, wants to merge Fox photos into Debbie. The community middleware is not being applied to the /person/ route or to the links generated within Similar Identities.
- **Root cause:** The `/person/{id}` route generates neighbor cards without community prefix. The neighbors endpoint `/api/identity/{id}/neighbors` also lacks community awareness.
- **Fix:** IMMEDIATE — audit /person/ route and neighbors endpoint for community prefix
- **BACKLOG:** COMMUNITY-016

### FB-061: Merge failures recurring — 5 faces attempted, many failed (P1)
- **Severity:** P1 (UX — recurring, same class as FB-056)
- **Context:** User tried to merge 5 faces and "seems like many of them didn't work." Same co-occurrence blocking issue as FB-039/FB-056. Every multi-merge shows partial failures without explanation.
- **Fix:** Same as FB-039/FB-056/UX-100
