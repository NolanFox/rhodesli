# Session 96c Context — Community-Scoped Review + Cross-Community Identity Pipeline

**Predecessor:** [Session 96b context](session-96b-context.md) (Charlie Fox ingest + cluster review dashboard)
**Date:** 2026-03-09
**Type:** Feature build — multi-community review infrastructure
**Related ADs:** AD-213 (cross-community identity sharing), AD-215 (cluster review UX), AD-216 (community-scoped review pipeline)
**ROADMAP items:** COMMUNITY-003, COMMUNITY-004

---

## Problem Statement

After ingesting 636 Charlie Fox photos into the Fox Family community (Session 96b), the Fox Family archive is broken for users:

1. **"0 identities" on landing page** — despite 35 auto-clustered matches (27 Roland Fox, 4 Betty Capeluto, 1 Ray Franco, 3 others)
2. **No Review section in sidebar** — New Matches, Discoveries, Help Identify all show 0 counts because ML counts are hardcoded to 0 for non-Rhodes
3. **No Admin section** — Uploads, Approvals, Proposals, GEDCOM all gated behind `is_rhodes`
4. **No admin bar** — pending counts show 0 because identity filtering returns empty set

**Root cause:** The `identity_communities` table is never populated for non-Rhodes communities. When clustering adds a Fox Family face to Betty's identity, Betty doesn't get tagged into Fox Family's identity_communities. So every query that filters by community identity set returns empty.

## User Feedback (Nolan, 2026-03-09)

### On Review Section Design
- "Without notifications how would people see matches in other communities?"
- "Any person in any photo in the community can cause a photo to show up in the review section"
- "If there is a new photo of Roland Fox in the Rhodesli community, I should be able to review that photo in the Fox Family community"
- "If I detach a false positive, they would no longer show up in the Fox Family community — they would just show up in the Rhodesli community"

### On Type 1 and Type 2 Errors
- Type 1 (false positive): Ray Franco matched at distance 1.04 — marginal, needs easy reject
- Type 2 (missed match): "Imagine that Albert Fox, Roland's father, happened to be in the Rhodesli collection because he was at some family event but we didn't immediately suggest him"
- "There needs to be a way in the app for someone to make that merge occur (even if by manual search)"
- "If that merge occurs, that person should show up in To Review in the future since they would be in both communities"

### On User Roles (MVP design consideration)
- Single-community user: Sees only their community's Review section with community-relevant items
- Multi-community admin: Sees the same person's matches in BOTH community sidebars
- Contributor: Can confirm/reject matches within their community
- Guest: Browse only, no Review section

### Correction
- Ray Franco is a woman (previously written as "he" in some docs)

## Research Findings

### Current State of Community Scoping (10 components audited)

| Component | File:Line | Status | Impact |
|-----------|-----------|--------|--------|
| `_compute_sidebar_counts()` | `main.py:2805-2810` | Hardcodes ML counts to 0 | No proposals/discoveries/annotations for Fox Family |
| Admin section sidebar | `main.py:4440-4459` | Gated by `is_rhodes` | No admin tools for Fox Family |
| `_compute_discoveries()` | `main.py:6158-6240` | No community parameter | Only computed for Rhodes |
| `_get_community_identity_ids()` | `main.py:558-581` | Works but returns empty set | No identities tagged to Fox Family |
| `add_identity_to_community()` | `supabase_data.py:1390` | **Exists but never called** | Identity tagging pipeline missing |
| Command center filtering | `page_routes.py:1779-1787` | Works correctly | Shows 0 items because 0 identities tagged |
| Community landing stats | `page_routes.py:304-451` | Correctly scoped | Shows "0 identities" because nothing tagged |
| Admin bar | `main.py:4201-4228` | Filters correctly | Shows 0 pending because 0 identities |
| `identity_communities` table | Supabase | Empty for non-Rhodes | Nothing populated it |
| Review section sidebar HTML | `main.py:4344-4378` | **FIXED** (session 96b continuation) | Now shows for all communities |

### The Core Architectural Insight

The system uses `identity_communities` table to determine which identities belong to which community. But the **actual ownership** should be derived from photos: if a person has faces in photos belonging to a community, that person belongs to that community.

**Two approaches:**
1. **Photo-derived identity set** (compute on-the-fly): For each community photo, find which identities have faces in it → that's the community's identity set. Cheap, always correct, auto-updates when faces are added/detached.
2. **Explicit tagging** (populate `identity_communities`): Call `add_identity_to_community()` when clustering/manual-merge creates cross-community links. Faster queries but requires maintenance.

**Recommended: Both.** Photo-derived set for correctness (source of truth), explicit tagging for performance (cached queries). Run a periodic sync to keep explicit tags aligned with photo-derived reality.

### Manual Merge Path for Type 2 Errors

When auto-clustering misses a match (Albert Fox in Rhodes but not suggested), the user needs:
1. A way to search for the person across ALL communities
2. A way to merge two identities (existing feature: merge on person page)
3. After merge, the merged identity automatically gains faces from both communities
4. The photo-derived identity set then includes this person in both communities
5. They appear in both sidebars' Review sections going forward

**Current state of manual merge:** The merge feature exists (`/api/identity/{id}/merge`). It combines anchor_ids from both identities. If the merged identity now has faces in both communities' photos, it will appear in both photo-derived sets automatically. **No additional work needed for Type 2 error correction** — just ensure the search works cross-community.

### Cross-Community Search Verification Needed

The search on person pages and admin pages needs to search ALL identities globally, not just community-scoped ones. When a Fox Family user searches for "Albert Fox" to merge, they need to find Rhodes identities too. Verify this works.

## Gaps to Close

1. **Build photo-derived identity set function** — new `_get_community_relevant_identity_ids(community)` that computes from photo ownership
2. **Remove ML feature zeroing** in `_compute_sidebar_counts()` — use photo-derived set instead
3. **Enable Admin section for all communities** — remove `is_rhodes` gate
4. **Make discoveries community-aware** — filter by photo-derived identity set
5. **Wire `add_identity_to_community()`** into clustering pipeline — explicit tagging for performance
6. **Backfill Fox Family identity_communities** — tag Betty, Roland, Ray Franco, and all 1652 face owners
7. **Verify cross-community search** — ensure merge workflow finds identities from other communities
8. **Update landing page identity count** — use photo-derived set or identity_communities

## Files to Modify

| File | Changes |
|------|---------|
| `app/main.py` | New `_get_community_relevant_identity_ids()`, fix `_compute_sidebar_counts()`, ungateAdmin section, make `_compute_discoveries()` community-aware |
| `app/page_routes.py` | Use photo-derived identity set in command center filtering, fix landing stats |
| `app/discoveries_routes.py` | Pass community to sidebar counts, filter discovery results |
| `app/supabase_data.py` | New function to load face→identity→community mapping |
| `core/auto_cluster.py` | Call `add_identity_to_community()` when clustering creates cross-community links |
| `app/upload_routes.py` | Call `add_identity_to_community()` after background ingest clustering |
| `tests/test_sidebar_community.py` | Update tests for new behavior |
| `tests/test_community_review.py` | New tests for photo-derived identity sets |

## Deferred (Not This Session)

- Per-community permissions (WORKSPACE-006) — currently admin-only
- "Shared person" indicator on identity cards (COMMUNITY-004)
- Per-user review section for multi-community users (future UX refinement)
- About page community content (from Session 96 BACKLOG)
