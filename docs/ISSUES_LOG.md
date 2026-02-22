# Rhodesli Issues Log

Living document of bugs and UX issues found during testing.
Updated during interactive sessions. Items that need action get
copied to BACKLOG.md with breadcrumbs back here.

## Recurring Incidents

### DATA-001: Deploy Data Loss (CRITICAL, recurring)
- **Status**: RESOLVED (AD-135 Supabase migration, Session 59C)
- **Severity**: P0
- **Occurrences**: 5
  1. Session 12 — data integrity fix not deployed, stale data served for weeks
  2. Session 16 — overnight session overwrote web triage work (Zeb Capuano regression)
  3. Session 25 — annotations.json overwritten by deploy (Claude Benatar inscription)
  4. Session 49B/59B — full interactive session lost (9 confirms, 3 birth years, 2 merges). Recovered from .bak file.
  5. Multiple minor occurrences: Lessons 43, 56 (blind push), 69 (annotations.json)
- **Impact**: Hours of manual data entry destroyed. Community trust at risk.
- **Root cause**: JSON on Railway volume + Docker bundle overwrite
- **Band-aid**: Triple safety gate in init_railway_volume.py (AD-134, Session 59B)
- **Structural fix**: Supabase migration (AD-135, planned Session 59C)
- **Resolution**: Structural fix implemented Session 59C (2026-02-22). User data in Supabase Postgres (4 tables: identity_overrides, annotations, relationships, gedcom_matches). Dual-write ensures every user action persists to Supabase. Startup sync rebuilds JSON cache from Supabase. Deploys cannot overwrite user data. See AD-135.
- **Breadcrumbs**: AD-134, AD-135, Lessons 43/56/69/78/85, docs/design/FUTURE_COMMUNITY.md
- **Priority justification**: Every occurrence costs hours of manual re-entry and risks losing community contributions that cannot be recreated. This is the #1 operational risk in the project.

## Open Issues
<!-- Populated from interactive session logs -->

## Resolved Issues
<!-- Moved here when fixed, with commit hash -->
