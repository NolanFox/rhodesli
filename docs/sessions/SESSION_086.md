# Session 86 — P1 UX Fixes + MLS Experiment + Gemini Completion
Started: 2026-03-04
Version: v0.88.0 → v0.89.0
Detailed log: docs/session_logs/session-86-log.md
Assessment: docs/assessments/session-86-assessment.md

## Summary
- Extracted app/utils.py (8 pure functions, zero deps)
- Resolved AD-027: Euclidean AUC 0.9903 vs MLS 0.9454 — keep Euclidean
- Completed Gemini alignment: 271/271 photos ($0.0004)
- UX-037: Merge confirmation dialogs on all ~10 merge buttons
- UX-039: Inline admin controls (rename, state actions, merge search)
- Face labels visible for all users + connected navigation
- Browser verification: 6/6 PASS

## Commits
1. d69460b - docs(session): session 86 orient
2. fefee23 - refactor(app): extract pure utility functions to app/utils.py
3. 07fe04f - fix(merge): UX-037 confirmation dialog on all merge buttons
4. e22939f - feat(person): UX-039 inline admin controls on person page
5. d210a55 - feat(ux): face labels visible for all users + connected nav tests
6. 8e3a65d - eval(ml): resolve AD-027 — MLS vs Euclidean (Euclidean wins)
7. 4d582a7 - fix(ml): complete Gemini alignment for last 2 blocked photos
8. 817d9af - fix(ux): face labels on public photo page visible for confirmed faces

## Red Flags
- Pre-existing test ordering failures under xdist
- data_loaders/compare/estimate extraction deferred
- Chrome extension unavailable — curl verification used
