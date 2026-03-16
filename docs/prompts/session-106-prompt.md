# Session 106 — Fox Triage Sprint + Rhodes Identity Labeling

**Context:** docs/session_context/session-106-context.md
**Priority:** P1 — user workflow session (triage + feedback collection)
**Runs in parallel with:** Session 105b (data integrity — backend only, no UI changes)

## Overview

This is a user-driven session in two halves:
1. **First half (triage):** Nolan uses the platform to complete Fox Family speed-run and label Rhodes community identities. Claude collects feedback, logs issues, diagnoses problems in real-time.
2. **Second half (fixes):** Based on collected feedback, create PRDs/SDDs and fix issues.

## Phase 1: Fox Family Speed-Run Completion (user-driven)

Nolan will use the speed-run cluster review at `/c/fox-family/?section=to_review&view=match` and `/admin/cluster-review`.

### Claude's role during triage:
1. Keep a running log of issues in `docs/session_context/session-106-feedback.md`
2. For each issue Nolan reports:
   - Screenshot if possible
   - Categorize: P0 (blocking), P1 (painful), P2 (annoying), P3 (cosmetic)
   - Note the exact page/URL/action that triggered it
   - Check if it's already in BACKLOG.md
3. Diagnose root causes in real-time when possible
4. Do NOT fix anything during Phase 1 — only collect and diagnose

### Expected triage areas:
- Speed-run keyboard shortcuts (Y/N/S/D)
- Cluster review grid (batch confirm/reject)
- Identity cards (name, face crops, merge)
- GEDCOM linking panel
- Find Similar panel
- Person pages
- Navigation between workstation sections

## Phase 2: Rhodes Community Identity Labeling (user-driven)

Nolan will go through Rhodes community confirmed/proposed identities and:
- Name people he recognizes
- Merge duplicate identities
- Link to GEDCOM records
- Dismiss false positives

### Claude's role:
- Same as Phase 1: collect feedback, diagnose, don't fix
- Track how many identities were labeled/merged/dismissed

## Phase 3: Fix Sprint (Claude-driven)

Based on Phase 1+2 feedback:
1. Triage all collected issues by priority
2. For P0/P1 issues:
   - Create PRD if >30 min work
   - Create BACKLOG entry with breadcrumb to feedback log
   - Fix if <30 min
3. For P2/P3 issues:
   - Create BACKLOG entries only
4. Run tests after each fix
5. Deploy fixes
6. Have Nolan verify the fixes work

## Phase 4: Assessment + Docs

1. Update feedback log with fix status
2. Write session assessment
3. Update ROADMAP, BACKLOG, CHANGELOG
4. Browser verify all fixes on production

## Non-Goals
- No ML pipeline changes
- No data model changes (Session 105b handles that)
- No architecture changes
- Focus is UX feedback and quick fixes

## Conflict Avoidance with Session 105b
Session 105b modifies ONLY:
- `app/supabase_data.py` (shadow write functions)
- `app/main.py` (save_registry, save_photo_registry)
- `app/upload_routes.py` (_background_ingest Supabase sync)
- `app/sync_routes.py` (push endpoint, reconcile endpoint)
- `scripts/reconcile_supabase.py` (new file)

Session 106 should NOT modify these files. UX fixes should be in:
- `app/identity_routes.py`, `app/page_routes.py`, `app/estimate_routes.py`
- `app/compare_routes.py`, `app/discoveries_routes.py`
- CSS/JS in templates
- Route-specific bug fixes
