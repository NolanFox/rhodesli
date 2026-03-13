# PRD-039: Batch Cluster Review — Speed-Run Mode

**Status:** Draft
**Date:** 2026-03-13
**Session:** 100c
**Author:** Nolan Fox + Claude Code

---

## Problem

Fox Family has ~1600 INBOX identities across 635 photos. The current Upload Review dashboard shows three sections (Grouped Identities, Potential Review Groups, Proposal Matches) as a grid — admin must click into each person page, review, navigate back. At this pace, reviewing 312 clusters would take hours.

## User Flow (Speed Run)

1. Admin navigates to `/c/fox-family/admin/upload-review?mode=speed`
2. Page shows first cluster: large face thumbnails (up to 8), suggested name, face count, match confidence
3. Action buttons: **Confirm All** (green), **Reject All** (red), **Skip** (grey), **Dismiss** (muted)
4. After action: HTMX swaps in next cluster — no page reload
5. Progress bar at top: "47 of 312 clusters reviewed"
6. Keyboard shortcuts: `Y`=confirm, `N`=reject, `S`=skip, `D`=dismiss
7. Speed-run link from existing dashboard: "Start Speed Run →"

## Existing Infrastructure

| Endpoint | File:Line | What it does |
|----------|-----------|-------------|
| `POST /api/cluster-review/confirm-all` | `cluster_review_routes.py:1179` | Promote all candidates for an identity |
| `POST /api/cluster-review/reject-all` | `cluster_review_routes.py:1224` | Reject all candidates for an identity |
| `GET /admin/upload-review` | `cluster_review_routes.py:777` | Dashboard with 3 sections |
| Community scoping | `cluster_review_routes.py:790-801` | Filter by community identity set |
| Grouped identities logic | `cluster_review_routes.py:810-894` | Multi-face INBOX clusters, sorted by face count |

**Bug found:** confirm-all and reject-all use `IdentityRegistry.load()` / `registry.save()` directly, bypassing `load_registry()` / `save_registry()`. Must be fixed to support DATA_SOURCE=postgres.

## New Endpoints

### `GET /admin/cluster-review/next?offset=N&community_slug=X`
Returns a single cluster card (HTMX partial) with:
- Large face thumbnails (up to 8)
- Identity name + face count
- Match confidence (if proposal-based)
- Confirm All / Reject All / Skip / Dismiss buttons with `hx-post` + `hx-target="#speed-run-card"`
- Each action button includes `offset` param so response auto-advances to next card
- When no more clusters: renders "All done!" completion card

### `POST /api/cluster-review/dismiss`
Parameters: `identity_id`, `offset`. Returns next cluster card (auto-advance).
Server-side: sets identity state to SKIPPED (reversible). No localStorage needed.

### Modified: confirm-all and reject-all
When `speed_run=true` param present: return next cluster card instead of success message.
Also fix: use `load_registry()` / `save_registry()` instead of direct JSON load/save.

## Speed-Run Page Layout

```
┌─────────────────────────────────────────┐
│ Speed Run Review        47 of 312       │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░  15%       │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ face │ │ face │ │ face │ │ face │  │
│  │  1   │ │  2   │ │  3   │ │  4   │  │
│  └──────┘ └──────┘ └──────┘ └──────┘  │
│                                         │
│  Person 7a3f (4 faces)                  │
│                                         │
│  [Confirm All] [Reject All] [Skip] [D] │
│                                         │
│  Press Y/N/S/D for keyboard shortcuts   │
└─────────────────────────────────────────┘
```

## Data Model

No new tables. Uses existing identity states:
- Confirm All → promotes candidates to anchors (existing `promote_candidate()`)
- Reject All → moves candidates to negative_ids (existing `reject_candidate()`)
- Dismiss → sets state to SKIPPED (existing state, reversible)
- Skip → no data change, just advances offset

## Acceptance Criteria

1. Speed-run page loads in <2s for Fox Family
2. Confirm-all merges all cluster faces into target identity
3. Reject-all rejects all candidates
4. Dismiss sets identity to SKIPPED and hides from queue
5. Auto-advance works without page reload (HTMX swap)
6. Progress counter shows accurate "N of M reviewed"
7. Community-scoped — Fox Family sees only Fox clusters
8. Keyboard shortcuts Y/N/S/D work (guarded: don't fire inside input fields)
9. Existing dashboard view unchanged (speed-run is additive, `?mode=speed`)
10. confirm-all and reject-all use `save_registry()` (Postgres-compatible)

## Out of Scope

- Split clusters (assigning individual faces to different identities)
- Manual face drawing / annotation
- Cross-community merge from within speed-run
- Renaming identities during speed-run (use person page for that)
- Undo within speed-run (use existing person page to undo)

## Priority Order

1. Fix confirm-all/reject-all to use save_registry() (P0 — data path bug)
2. Next cluster endpoint with auto-advance
3. Speed-run page layout with progress bar
4. Keyboard shortcuts
5. Dashboard link to speed-run
