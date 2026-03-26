# PRD-057: Triage Workflow Redesign — Confirm vs Identify

**Date:** 2026-03-26
**Session:** 139
**Status:** In Progress

## Problem Statement

The app conflates two distinct actions:
1. **Confirming** a cluster is a real person (cluster validation)
2. **Identifying** who that person is (naming)

Users want to:
- Confirm an unnamed cluster as a distinct person (cluster validation)
- Later return to name/identify that person
- Filter confirmed people by "named" vs "needs identification"

## Industry Precedent

- **Google Photos**: Clusters exist without explicit confirmation. Naming is separate. Unnamed groups visible in People.
- **Apple Photos**: Similar model -- unnamed clusters are valid face groups.
- **Rhodesli**: Explicit confirm step is MORE intentional (heritage archive accuracy), which is appropriate for this domain.

## Design

### No Schema Change Needed

The existing `_is_real_name()` function in `core/registry.py` already distinguishes named vs unnamed identities:
- Names starting with "Unidentified Person" are placeholder names
- All other names are considered "real" names

### Workflow Separation

- **Confirm** = cluster validation (state -> CONFIRMED, name stays "Unidentified Person NNN")
- **Identify** = naming action (rename to real name)
- **Already done in Session 138**: confirm button enabled for unidentified persons (FB-006)

### New: People Page Filter

Add filter tabs above the people grid on `/people`:
- **All** (default) -- shows all CONFIRMED identities
- **Named** -- shows CONFIRMED with real names (not starting with "Unidentified Person")
- **Needs Name** -- shows CONFIRMED with placeholder names

Implementation: HTMX-driven filter switching reloads the grid with a `?name_filter=` query parameter.

### New: Sidebar Count Breakdown

Update the sidebar "People" count to show the breakdown:
- Format: "N People (X named, Y unidentified)"
- Only show breakdown when there are unidentified confirmed people

## Acceptance Criteria

1. People page has 3 filter tabs: All, Named, Needs Name
2. Each filter shows the correct subset of CONFIRMED identities
3. Filters work with existing sort options (A-Z, Most Photos, Newest)
4. Sidebar People count shows named/unidentified breakdown
5. No schema changes required
6. No changes to identity state machine

## Out of Scope

- New state machine states (e.g., IDENTIFIED) -- too much churn
- Auto-confirm on merge -- needs separate analysis (Session 111d risk)
- Changes to speed-run or focus mode workflows

## Related

- Session 138 FB-006: confirm for unidentified persons
- `core/registry.py` `_is_real_name()` function
- `app/browse_routes.py` `/people` route
