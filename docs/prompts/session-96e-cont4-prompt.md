# Session 96e-cont4 — Fix Upload + Supabase Sync + Deploy Verify

**Context:** `docs/session_context/session-96e-cont3-findings.md`
**Previous commit:** `de6f3c2` (community scoping fixes)
**Priority:** P0 — Fix broken upload, sync Supabase, deploy and verify

---

## What Was Fixed in cont3 (COMMITTED, NEEDS DEPLOY + VERIFY)

1. Proposals sidebar community-scoped
2. Proposals API community-filtered
3. Discoveries Help Identify community-filtered
4. Dist 0.00 duplicate filter in Similar Identities
5. Name consistency "Person NNNN" in neighbor cards

## Act 1: Fix Upload Bug

User tried uploading 3 photos from ~/Downloads/rhodes_pics_more_testing on Rhodes.
Files appear in tooltip but upload doesn't start.

Investigation steps:
1. Check upload route in `app/main.py` — search for `def post` near `/upload`
2. Check the JS upload handler — look for `dropzone` or file input change handler
3. Test locally: try uploading via the upload page
4. Check browser console for errors (use Claude Chrome `read_console_messages`)
5. The upload page is at `/upload` — check if CommunityMiddleware affects it

The upload bug is likely pre-existing (cont3 didn't touch upload code).

## Act 2: Fix Supabase Data Divergence

Local JSON has correct data (3006 identities, max 44 faces per cluster).
Supabase has 4155 (stale from single-linkage, includes 252-face garbage clusters).

### Step 1: Verify Benatar contributions
```python
# Check if any of the 919 non-merged extras were created/modified by Claude Benatar
# Look for annotations, proposed_matches, or user_source fields referencing Benatar
```

### Step 2: Delete orphans safely
- First: Delete 230 identities with `merged_into` set that aren't in local JSON
- Then: For the 919 non-merged, check if they have any user-contributed data
- If clean (no user data): delete them
- If they have user data: preserve and note in backlog

### Step 3: Verify identity_communities table
- The identity_communities table needs to match the current identity set
- After cleanup, backfill identity_communities for new identities

## Act 3: Deploy + Browser Verify

1. `git push origin main` to deploy
2. Wait for Railway deploy SUCCESS
3. Navigate to each page and verify:
   - `/c/fox-family/?section=to_review&view=browse&sort_by=faces` — max cluster should be 44, not 252
   - `/c/fox-family/admin/proposals` — should show Fox Family context
   - `/discoveries` — Help Identify should NOT show Fox photos
   - `/upload` — should accept file uploads
   - Click "Similar" on any identity — no Dist 0.00 entries
4. Save screenshots to `docs/screenshots/session-96e-cont4/`

## Act 4: Upload UX Improvement (if time permits)

Nolan feedback: Upload needs better flow:
- Select files → see file list in scrollable preview box → click explicit "Upload" button → progress
- Current auto-upload gives no feedback
- Must handle large file counts without breaking

## Act 5: Session Wrap
1. Assessment file
2. CHANGELOG, ROADMAP updates
3. Final tests + commit

## Key Files
- `app/main.py` — upload route, `_compute_sidebar_counts()`, `neighbor_card()`, `identity_card()`
- `app/admin_routes.py` — proposals page
- `app/engagement_routes.py` — proposals API
- `app/discoveries_routes.py` — discoveries + Help Identify
- `app/identity_routes.py` — neighbors API
- `scripts/backfill_identities_to_supabase.py` — Supabase sync
- `docs/session_context/session-96e-cont3-findings.md` — full findings
