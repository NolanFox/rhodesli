# Session 106 Context — Fox Triage Sprint + Rhodes Identity Labeling

**Predecessor:** Session 105b (data integrity — COMPLETE, deployed, data_parity.synced=true)
**Priority:** P1 — user workflow session

## Purpose

Nolan needs to use the platform for productive triage work:
1. Complete the Fox Family speed-run (remaining ~1000+ INBOX identities)
2. Label Rhodes community identities he recognizes
3. Collect feedback on UX issues encountered during real usage

## Current Platform State
- Fox Family: 1,272 photos, 1,144 identities, ~85 confirmed
- Rhodes: 498 photos, 778 identities, ~85 confirmed
- Speed-run mode: shipped Session 100c, keyboard shortcuts Y/N/S/D
- Cluster review: shipped Session 100f, batch select/confirm grid
- Both communities accessible via `/c/fox-family/` and `/c/rhodes/`

## Known Issues Going In
- 3 pre-existing flaky xdist tests (ordering issues, not functional bugs)
- data_parity.synced=true (fixed Session 105b — 15 structural tests guard all write paths)
- BACKLOG has ~30 open P1/P2 items from previous sessions
- DATA-015 (dead sync functions) FIXED — birth_year_estimates + person_comments now synced

## Breadcrumbs
- Speed-run: PRD-039 (docs/prds/039_speed_run.md)
- Cluster review: PRD-040 (docs/prds/040_batch_cluster_validation.md)
- Fox Family: Session 95 (community platform), Session 96e (stabilization)
- UX issue tracker: docs/ux_audit/UX_ISSUE_TRACKER.md
- Feedback items from prior sessions: FB-120 through FB-168
