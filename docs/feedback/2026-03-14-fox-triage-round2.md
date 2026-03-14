# Fox Triage Round 2 — 2026-03-14 Session 101 Phase 6

Nolan drives triage. Claude fixes or logs.

## Feedback Items

### FB-120: GEDCOM search very slow (~1 minute)
- **Severity:** P2 (performance)
- **Context:** After confirming Person 3659 (10 faces, Albert Fox), the GEDCOM "Link to Family Tree" panel loaded but search took ~1 minute to return results for "Albert Fox" (196 results)
- **Root cause:** Supabase ILIKE query on multiple columns (name, given_name, surname) with OR filter across 21K GEDCOM records. "Fox" is a very common surname. The `load` trigger auto-fires on panel open.
- **Fix:** BACKLOG — needs Postgres index on GEDCOM name columns, or text search, or debounce/lazy-load
- **BACKLOG:** UX-077

### FB-121: Save Name + Link to Tree are confusing separate actions
- **Severity:** P1 (UX confusion)
- **Context:** User must (1) type name, (2) click Save Name, (3) search GEDCOM, (4) click Link — but these should be unified
- **Fix:** FIXED — GEDCOM Link now auto-renames identity to GEDCOM name when identity still has auto-generated name. OOB swap updates name input field with green border. User just needs to Link and the name is set.
- **Files changed:** `app/relationship_routes.py` (api/gedcom/link endpoint)
