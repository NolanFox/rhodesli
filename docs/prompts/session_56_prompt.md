# Session 56 Prompt — Landing Page Refresh + P1 UX Polish
Saved: 2026-02-21
See docs/session_context/session_56_planning_context.md for full planning context.
See docs/session_context/session_56_checkpoint.md for progress tracking.

## Session Goals
1. P1 UX Quick Wins (12 issues)
2. Landing Page Refresh (live-data feature showcase)
3. Lazy loading for /timeline and /photos
4. Production browser verification
5. Session documentation + verification gate

## Key Rules
- Browser verify with Chrome extension after EVERY UI change
- Push frequently (every 2-3 fixes)
- Both test suites: pytest tests/ -x -q AND pytest rhodesli_ml/tests/ -x -q
- All landing page stats must be LIVE (never hardcoded)
- No doc over 300 lines, CLAUDE.md under 80 lines
