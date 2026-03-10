# Session 96e Continuation 2 — Fix Fox Family UX (P0)

**Context:** `docs/session_context/session-96e-feedback.md`
**Previous:** Session 96e shipped grouping (813 merges), proposals (2115), STORAGE_DIR fix, TTL cache
**Priority:** P0 — "When I wake up I want a working platform"
**PRD:** `docs/prds/037_post_upload_intelligence.md`

---

## Current State (What Works)
- Grouping pipeline ran: 2009 → 1196 INBOX identities (813 merges)
- Proposals generated: 2115 proposals at threshold 1.3
- Sidebar counts show: New Matches 1497, Proposals 1122, Discoveries 568
- Clusters ARE visible in New Matches when sorted by "Faces" (252, 157, 121, 37, 23 faces per group)
- Registry TTL cache working (30s)
- Discoveries page loads without timeout

## What's Broken (User P0 Feedback — `docs/session_context/session-96e-feedback.md`)

### FIX 1: Default sort for New Matches must be "Faces" not "Newest"
- **File:** `app/page_routes.py` line 1714
- **Current:** `sort_by: str = "newest"` — shows 1497 individual 1-face cards
- **Fix:** Change default to `"faces"` for `section == "to_review"` only
- **Also fix:** `_sort_control()` in `app/main.py` line 5547 — sort links use `/?section=...` without community prefix. Must use community-aware URLs.

### FIX 2: Upload Review must be community-scoped
- **File:** `app/cluster_review_routes.py`
- **Problem:** `/admin/upload-review` shows GLOBAL data (2115 faces to 70 identities)
- **Fix:** Route must be `/c/{slug}/admin/upload-review` and filter proposals + identities by community
- The community prefix routing already exists via CommunityMiddleware — verify it works for this route
- Check how other admin routes handle community scoping (e.g., admin_routes.py)

### FIX 3: Upload Review cluster section must show GROUPED identities, not just proposals
- **Problem:** Cluster Review shows 1122 proposal matches. It should show the actual CLUSTERS from grouping (the 252, 157, 121-face groups).
- **Fix:** Upload Review should have two sections:
  1. **Clusters** — Multi-face INBOX identities created by grouping. Show face count, thumbnail grid, link to person page. Sort by face count descending.
  2. **Proposal Matches** — Matches between clusters and CONFIRMED identities. Filter to high confidence only (distance < 1.05). Show match confidence, community labels for cross-community matches.
- **Reference:** PRD-037 Flow 2 — "Top identities by face count (descending)"

### FIX 4: Proposal quality — filter out Low confidence garbage
- **Problem:** 389 matches for Roland Fox at Low (1.30) confidence are useless
- **Current threshold:** 1.3 (set in cluster_new_faces.py)
- **Fix:** Either:
  a. Re-run proposals with lower threshold (0.95 or 1.05), OR
  b. Filter in Upload Review UI to only show distance < 1.05 (Medium+High confidence)
- Option (b) is faster and preserves data — recommend this approach
- Confidence tiers: <0.85 High, 0.85-1.05 Medium, >1.05 Low

### FIX 5: Upload Review face cards must match rest of app
- **Problem:** Cards show minimal info (thumbnail + confidence badge + "From: Unidentified Person XXXX")
- **Fix:** Use the same `identity_card()` component used in New Matches
- Each card should have: face thumbnail, name, face count, community badge if cross-community, link to person page
- For proposal matches: show Compare button, Merge button, match confidence

### FIX 6: Investigate "99% match, Dist: 0.00, Seen together in 1 photo"
- **Problem:** Compare/Similar Identities shows faces with 0.00 distance and "Seen together in 1 photo" — suggests duplicate face entries or same-photo faces being compared
- **Where to look:** The grouping pipeline may have created identities that share the same face_id, or the similar identities panel may be showing faces from the same photo against each other
- **File:** Check `app/identity_routes.py` or `app/main.py` neighbors_sidebar logic
- If grouping created duplicates: need dedup pass
- If it's a rendering issue: filter out same-photo comparisons from similar panel

## Implementation Order

1. **FIX 1** (5 min) — Change default sort, fix community prefix in sort links
2. **FIX 4** (5 min) — Add distance < 1.05 filter to Upload Review proposals
3. **FIX 2** (15 min) — Community-scope Upload Review route
4. **FIX 3** (20 min) — Add clusters section showing grouped identities by face count
5. **FIX 5** (15 min) — Upgrade face cards to use identity_card()
6. **FIX 6** (10 min) — Investigate and fix duplicate/same-photo comparisons
7. Tests for all fixes
8. Push, deploy, browser verify from `/c/fox-family/` context
9. Session wrap (assessment, CHANGELOG, ROADMAP, lessons)

## Key Files
- `app/page_routes.py` line 1714 — sort_by default
- `app/main.py` line 5531-5548 — `_sort_control()` sort links
- `app/cluster_review_routes.py` — Upload Review route + rendering
- `app/identity_routes.py` — neighbors_sidebar / similar identities
- `core/grouping.py` — group_inbox_identities
- `data/proposals.json` — 2115 proposals
- `data/identities.json` — 2455 identities (1196 INBOX after grouping)
- `docs/prds/037_post_upload_intelligence.md` — PRD acceptance criteria

## Verification Checklist
- [ ] `/c/fox-family/?section=to_review&view=browse` defaults to sort by Faces
- [ ] Sort links include community prefix (`/c/fox-family/...`)
- [ ] Upload Review is accessible at `/c/fox-family/admin/upload-review`
- [ ] Upload Review shows ONLY Fox Family data
- [ ] Upload Review shows clusters section with multi-face groups (252, 157, 121+)
- [ ] Upload Review proposals filtered to Medium+ confidence (< 1.05)
- [ ] Upload Review face cards match identity_card() design
- [ ] No "Dist: 0.00" entries in Similar Identities
- [ ] All tests pass (make test-fast + rhodesli_ml tests)
