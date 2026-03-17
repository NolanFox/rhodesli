# Session 111d Context — Outstanding Feedback Fix Sprint

**Predecessor:** [Session 111c context](session-111c-prompt.md) (no separate context file)
**Feedback source:** [docs/feedback/session-111-feedback.md](../feedback/session-111-feedback.md) — 70 items total

## Scope

Fix ALL remaining open feedback from Sessions 111, 111b, 111c. This is a fix sprint — no new features. Every item is traced to an FB-NNN ID.

## What Was Fixed Already (Sessions 111b + 111c)

| FB | Description | Fixed In |
|----|-------------|----------|
| FB-026 | Suggestions sorted by face count | 111b |
| FB-033 | CI test failure (upload_date) | 111b |
| FB-034 | Rhodes clusters in Fox Family | 111b |
| FB-041 | Compare page community prefix | 111b |
| FB-047 | "View in Admin Queue" community prefix | 111b |
| FB-052 | Confirm button label (partial — label only) | 111b |
| FB-059 | Discovery loading skeleton | 111b |
| FB-039/056/061/062 | Bulk merge feedback | 111c |
| FB-055 | Select All checkbox | 111c |
| FB-025 | Speed-run latency (partial — lazy-load) | 111c |
| FB-027 | Next Cluster button | 111c |
| FB-067 | Search beyond 150 cards | 111c |

## What's Still Open — Prioritized

### P0 — Blocks Core Triage Workflow

| FB | Description | Root Cause | Files |
|----|-------------|------------|-------|
| FB-068 | "Confirm as {Name}" doesn't merge — no visible feedback | Confirm endpoint only promotes state, doesn't merge with suggested match. HTMX swap may also be broken. | `app/main.py` (confirm_url), `app/identity_routes.py` (confirm handler) |
| FB-066 | Green checkmark on photo overlay doesn't work | Endpoint `/api/face/quick-action` exists but no visible effect. HTMX target `#photo-modal-content` may not swap. | `app/identity_routes.py:1301`, `app/page_routes.py:3999` |
| FB-036/037 | Speed Loop tagging doesn't persist (BUG-001) | Tag assignment endpoint silently fails. Recurring. | `app/identity_routes.py` tag endpoints |
| FB-069 | Overall performance too slow | `save_registry()` writes ALL identities on every confirm. No caching of suggestions/clusters. | `app/main.py` save_registry, `app/cluster_review_routes.py` |
| FB-029 | Rhodes photos in Fox Family speed-run (DATA BREACH) | `group_inbox_identities()` has no community filter | `core/grouping.py` |

### P1 — Important UX Issues

| FB | Description | Root Cause | Files |
|----|-------------|------------|-------|
| FB-070 | GitHub CI failure emails | `test_partial_has_public_page_link` assertion wrong | `tests/test_internal_photo_links.py` |
| FB-057 | Focus mode doesn't auto-advance | HTMX response doesn't swap next card | `app/identity_routes.py` confirm/skip handlers |
| FB-040 | Stale card remains after merge | OOB swap targets wrong element ID | `app/identity_routes.py` merge handler |
| FB-054/058 | Thumbnail mismatch in Similar Identities | Different face selection between list and detail | `app/main.py` neighbor_card |
| FB-048 | No "View Person" link in tag popup | Missing link in tag dropdown | `app/page_routes.py:3958` |
| FB-051 | Photo filename search broken | May work but community prefix missing on results | `app/identity_routes.py:788` |
| FB-065 | Post-merge findability | `search_identities()` excludes merged | `core/registry.py:2037` |
| FB-030 | Cluster count resets | Counter in URL param, lost on page reload | `app/cluster_review_routes.py` |
| FB-031 | Face grid distorted on gear click | CSS grid overflow in narrow container | `app/main.py` face_card |
| FB-064 | Override redirect wrong community | Needs production verification | `app/identity_routes.py` |

### P2 — Polish

| FB | Description | Files |
|----|-------------|-------|
| FB-028 | Toast doesn't persist to next screen | HTMX swap clears toast |
| FB-038 | "View More" resets checkboxes | innerHTML swap loses state |
| FB-044 | Best match duplicated in Similar list | Exclude best match from neighbor query |
| FB-053 | Identity ID format inconsistent | One-time renumbering migration |

### Deferred (Not This Session)

| FB | Description | Reason |
|----|-------------|--------|
| FB-035 | Bad cluster quality | Needs labeled data, ML-102 |
| FB-042/043 | Help Identify unclear/crops too small | Needs IA review, UX-102/103 |
| FB-045/046 | Help Identify Focus mode inconsistency | Needs IA review, UX-105/106 |
| FB-049 | Sentry circular import | Complex refactor, INFRA-005 |
| FB-052 | Confirm+merge in one click (full PRD) | Needs PRD-level design, UX-108 |

## Parallelization Analysis

### Can parallelize (different files):
- **Track A**: Performance fixes (`app/main.py` save_registry, `app/cluster_review_routes.py` caching)
- **Track B**: CI fix + test fixes (`tests/`)
- **Track C**: Identity routes fixes (`app/identity_routes.py` — confirm handler, tag handler, search)
- **Track D**: Page routes fixes (`app/page_routes.py` — photo overlay, face grid, tag popup)

### Cannot parallelize (file conflicts):
- FB-068 and FB-069 both touch `app/main.py` — must be same track or sequential
- FB-066 and FB-048 both touch `app/page_routes.py` — same track

## Breadcrumbs
- Feedback file: `docs/feedback/session-111-feedback.md`
- BACKLOG items: PERF-008, PERF-009, UX-094 through UX-115, CI-002, DATA-022, DATA-023, COMMUNITY-015/016
- Memory: Speed-Run Performance Root Causes (session 111 memory entry)
