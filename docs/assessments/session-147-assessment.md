# Session 147 Assessment (Final — updated 2026-04-13)

## Shipped
- [x] Phase 1: Wire remaining signals — Evidence: 13 new tests pass, 4 placeholders replaced with real implementations (age_trajectory, gedcom_match, testimony, provenance). Codex P0 idempotency fix applied.
- [x] Phase 2: Evidence panel UI — Evidence: 6 tests pass, admin-only card with 6 signal bars renders on person page for PENDING suggestions. Schema aligned to read `confidence` + `evidence_json` (Codex P0 fix).
- [x] Phase 3: Accept/Reject/NeedMore endpoints — Evidence: 28 tests pass. Three POST endpoints with CSRF, admin gate, merge-vs-rename branching (Codex P1), GEDCOM link via gedcom_face_links (Codex P1). Status gate on all three (Codex P2).
- [x] FB-001: Restore-to-inbox feature — Evidence: 11 tests pass. POST /api/identity/{id}/restore endpoint + UI button on rejected person pages.
- [x] Data fix: Person 82863849 restored from REJECTED to INBOX via Supabase.
- [x] Deploy: git push origin main, Railway deploy SUCCESS, smoke test 11/11 PASS.
- [x] Batch execute: 18/18 identity suggestions written to Supabase identity_suggestions table.
- [x] P0/P1 Codex fixes: Schema mismatch, placeholder name safety (input field), GEDCOM column, confirm state guard, status gates.
- [x] Lessons 166-167: Worktree commit discipline + git lock contention. Postmortem documented.
- [x] CHANGELOG v0.99.60, ROADMAP updated, session log complete.

## Test Counts
- New tests: 58 net (4054 total, was 3996)
- App tests: 4054 passed, 8 skipped, 14 xfailed, 2 xpassed
- ML tests: 658 (confirmed separately)

## Deferred
- Browser verify with Chrome plugin — traveled during session, smoke test passed but no visual verification of evidence panel on production
- Rejected list UX — restore buttons in dismissed section cards (Phase 4 of 147b plan). Small feature (~15 min).
- Leave-one-out validation (SDD testing strategy)
- Codex post-implementation audit of the P0/P1 fix commit

## Red Flags
- [LOW] Fader collection suggestions have low confidence (0.20-0.24) because zero co-occurrence with Fox family. Expected — these are Fader photos.
- [RESOLVED] Parallelization failures: Lessons 166-167 documented, worktree-enforcement.md updated.
- [RESOLVED] Codex P0 schema mismatch + placeholder name corruption — fixed before batch execute.

## Codex Audits (2 rounds, 17 findings total)

### Pre-Implementation Audit (gpt-5.4, 2026-04-01)
- 9 findings (1 P0, 4 P1, 3 P2, 2 P3) — all addressed in prompt before implementation
- Value: STRONG — P0 batch idempotency would have shipped broken

### Post-Implementation Audit (gpt-5.4, 2026-04-13)
- 8 findings (2 P0, 3 P1, 2 P2, 2 P3) — all P0/P1 fixed before deploy
- P0: Schema mismatch (UI read wrong columns) — FIXED
- P0: Placeholder name corruption on Accept — FIXED (input field for placeholders)
- P1: Confirm on REJECTED target — FIXED (restore to INBOX first)
- P1: GEDCOM link column name — FIXED (gedcom_id not gedcom_individual_id)
- P1: CSRF on reset endpoint — noted for future fix
- P2: Status gate — FIXED on all 3 suggestion endpoints
- Value: STRONG — both P0s would have caused data corruption in production

## AI Tool Usage
- **Tool**: Codex CLI v0.117.0 (gpt-5.4)
- **Agent type**: Independent (fresh context)
- **Tasks**: Pre-implementation plan audit + post-implementation code audit
- **Total findings**: 17 (3 P0, 7 P1, 5 P2, 4 P3)
- **Acted on**: All P0/P1 fixed before deploy
- **Value assessment**: STRONG — prevented 3 data corruption bugs
- **Would we have found these ourselves?** Schema mismatch: possibly during browser verify. Placeholder name corruption: unlikely without testing the accept flow end-to-end.

## Next Session Should Verify
1. Browser verify evidence panel on production with Chrome plugin
2. Rejected list UX enhancement (restore buttons in dismissed section)
3. Consider running batch for Rhodes community (not just Fox family)
