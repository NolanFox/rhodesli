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

### FB-122: Charles Fox lost his name (DATA REGRESSION)
- **Severity:** P0 (data integrity)
- **Context:** "Charles Fox" (previously 68 faces) appeared on the Fox Family People page as "Person 2986" (44 faces). The name existed only in production Postgres, not in local identities.json. During session 101 triage operations, save_registry() likely overwrote the Postgres name.
- **Root cause:** Production-local data divergence (Lesson 78 recurring). The non-blocking Postgres sync (Phase 4, commit ba8443f) may have contributed — background thread could fail silently.
- **Fix:** FIXED — renamed via production API to "Charles Fox". Now has 54 faces after merge.
- **Prevention needed:** save_registry() should NEVER overwrite a named identity with an auto-generated name. Need a guard in the Postgres sync path.
- **BACKLOG:** DATA-017

### FB-123: Person 2795 — unmerged confirmed cluster (11 faces)
- **Severity:** P2 (data quality)
- **Context:** Person 2795 (98772230) is CONFIRMED with 11 faces from the Charles Fox Collection but has no name and no GEDCOM link. May be a split from Charles Fox during earlier triage, or a separate person. Nolan mentioned "Esther Burd has a second unmerged one."
- **Fix:** NEEDS DECISION — Nolan should review the face crops on the person page and decide if it should merge into Charles Fox, Esther Burd, or remain separate as a new person.
- **URL:** /c/fox-family/person/98772230-f4a2-4a10-b6cf-36d915e29225

### FB-124: Merge search can't find people with lost names
- **Severity:** P2 (UX)
- **Context:** When searching "charles" in the merge search during speed-run, "No matches found" because Charles Fox's name had been wiped to "Unidentified Person 2986". The identity appeared in Suggested Matches but not in search.
- **Fix:** Already fixed by restoring name. Broader fix: merge search should also search by identity ID number (e.g., "2986") as a fallback.
- **BACKLOG:** UX-078
