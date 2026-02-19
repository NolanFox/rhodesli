# Session 50: Estimate Overhaul + Gemini Upgrade + Progressive Refinement Architecture

## Session Identity
- **Previous session:** Session 49C (urgent bug fixes, v0.49.3)
- **Goal:** Four tracks:
  1. 49C followup — harden compare upload error handling
  2. Estimate page — overhaul into standalone tool
  3. Gemini model upgrade — centralize config, plan progressive refinement architecture
  4. ROADMAP + BACKLOG sync — bring docs current with actual state
- **Time budget:** ~45 min
- **Priority:** HIGH — estimate page is publicly visible and broken; ROADMAP/BACKLOG are stale

## Phases
- Phase 0: Orient + verify 49C
- Phase 1: Harden compare upload (loading, errors, validation)
- Phase 2: PRD-020 Estimate overhaul
- Phase 3: Implement estimate fixes (3A-3E)
- Phase 4: Gemini model audit + progressive refinement AD
- Phase 5: Update PRD-015 for 3.1 Pro
- Phase 6: ROADMAP + BACKLOG sync
- Phase 7: Verification gate
- Phase 8: Final docs + changelog

## Key Context
- Estimate page shows "0 faces" everywhere, no upload, no pagination
- Gemini 3.1 Pro released Feb 19, 2026 — use for ALL vision work
- Progressive refinement: re-run VLM when verified facts accumulate
- ROADMAP/BACKLOG stale since Session 47

## Constraints
- DO NOT call Gemini API
- DO NOT implement PRD-015 face alignment
- DO NOT modify identity data or photo_index.json
- Commit after every phase
- Test before every commit
