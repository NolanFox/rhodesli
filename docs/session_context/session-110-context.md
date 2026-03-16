# Session 110 Context: James Fields UX Bug Sprint

**Predecessor:** Session 109b (cross-batch clustering deployed)
**Trigger:** End-to-end James Fields test by Nolan exposed 9 UX bugs
**Test case:** Rename → Confirm → Find Similar → Merge → Override → GEDCOM link

## User Test Results (Session 109b)

Nolan walked through the James Fields identification workflow end-to-end. The cross-batch matching worked (all expected faces appeared in Similar Identities). But the UX had 9 issues ranging from P0 (broken) to P2 (friction).

### P0 — Broken functionality

**FB-019: Individual Merge buttons silently fail**
- Clicking the blue "Merge → James Henry Jimmy Fields" button on a single face card does nothing
- No error, no loading state, no response
- Only "Merge Selected" (checkbox + bulk button) works
- This is the primary merge action for most users — must work

**FB-021: Override button does nothing**
- Clicking "Override ⚠" shows a tooltip with the photo filename but takes no action
- No confirmation dialog, no merge, nothing happens
- Tooltip text: "Override: Appear together in james_henry_fields_528..."
- Override is needed for collage faces (same photo, different sub-images)
- This blocks merging 3+ James Fields faces that are co-occurrence blocked

### P1 — Works but broken UX

**FB-016: Rename is very slow**
- Takes several seconds to complete
- No loading indicator — appears to silently fail
- Eventually shows a toast notification that disappears after ~2 seconds
- User thought it was broken and almost gave up

**FB-017: Confirm creates duplicate giant face card + stale buttons**
- After clicking Confirm, a large face card appears below the original thumbnail
- The card shows CONFIRMED state but Confirm/Skip/Reject buttons are still visible above
- The INBOX badge was still showing in the admin panel before refresh
- After page refresh, displays correctly (CONFIRMED badge, no action buttons)

**FB-018: Find Similar requires page refresh after Confirm**
- After confirming identity, clicking "Find Similar" does not work
- Page must be manually refreshed first, then Find Similar works
- Likely stale HTMX state after the confirm swap

**FB-020: Every merge closes Find Similar panel**
- After any merge action, the Similar Identities panel closes
- Must click "Find Similar" again to continue merging more faces
- Find Similar is slow to load (~3-5 seconds)
- This makes the merge workflow extremely tedious for 5+ faces

**FB-023: GEDCOM linking very slow**
- After confirming, the GEDCOM link panel takes a long time to load
- "Needs Tree Link" badge appears but clicking it is slow
- User might think it's broken if not patient enough

**FB-024: General slowness throughout**
- Rename: ~3-5 seconds
- Confirm: ~3-5 seconds
- Find Similar: ~3-5 seconds
- Each merge: ~2-3 seconds + panel close + reopen
- GEDCOM: ~3-5 seconds
- Total for 5 merges: potentially 60+ seconds of waiting

### P2 — Missing functionality

**FB-022: No "Merge All Including Overrides" batch action**
- "Select All" + "Merge Selected" only works for non-blocked faces
- Co-occurrence blocked faces (Override) cannot be batch merged
- Must go one by one, and Override doesn't work anyway (FB-021)
- Ideal: "Select All" includes Override faces with a confirmation step

## Root Cause Analysis

### Slowness
- Every action triggers a full Supabase sync (shadow_write) which is synchronous
- `save_registry()` invalidates all caches + writes JSON + syncs Supabase
- Find Similar panel does a real-time embedding distance computation
- GEDCOM search does a full-text search against the GEDCOM index

### Merge button failure (FB-019)
- Need to investigate: the individual merge button uses `hx_post` targeting a merge endpoint
- The bulk "Merge Selected" uses a different code path (JS + form submission)
- The individual button may have a stale identity_id or wrong hx_target

### Override failure (FB-021)
- Override was added in Session 108b (PRD-048)
- The tooltip showing suggests the button event handler fires but doesn't proceed to merge
- May need a confirmation dialog that then calls the merge endpoint with override=true

### Confirm UI regression (FB-017)
- The confirm endpoint returns an updated card via HTMX swap
- But the swap target may be wrong, causing it to append rather than replace
- After page refresh it's correct, so the data is right — just the DOM update is wrong

## Files to Investigate

| File | What to look for |
|------|-----------------|
| `app/main.py` | `neighbor_card()` — the Similar Identities card rendering, merge button hx_post |
| `app/main.py` | `_similar_identities_panel()` — the panel that closes after merge |
| `app/identity_routes.py` | Confirm handler return value (what gets swapped) |
| `app/identity_routes.py` | Merge handler — individual vs bulk code paths |
| `app/main.py` | Override button handler |
| `core/registry.py` | `merge_identities()` with override param |

## Performance Investigation

- Profile `save_registry()` — how long does Supabase sync take?
- Check if Find Similar can be cached or pre-computed
- Check if GEDCOM search uses the trigram index properly
- Consider making Supabase sync async for merge operations (already is for some paths)

## Session 110 Plan

**Phase 1: Fix P0 bugs (merge button + override)**
- Debug individual merge button — trace hx_post endpoint
- Fix Override to actually merge with confirmation dialog

**Phase 2: Fix P1 UX bugs**
- Fix confirm UI swap (no duplicate card, no stale buttons)
- Fix Find Similar after confirm (refresh panel state)
- Keep Similar panel open after merge (re-render instead of close)
- Add loading states for rename, confirm, GEDCOM

**Phase 3: Performance**
- Make Supabase sync async where safe
- Add loading spinners for slow operations
- Consider pre-loading Similar Identities on page load

**Phase 4: P2 — Batch override merge**
- Add "Select All Including Overrides" with confirmation step
