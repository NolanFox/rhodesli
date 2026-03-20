# Session 127 Context — Accessibility + Remaining Polish + Codex Audit

**Predecessor:** [Session 126 Context](session-126-context.md)
**Assessment:** [Session 126 Assessment](../assessments/session-126-assessment.md)

## Goal

Ship remaining polish items from Session 126 UX audit, fix last flaky test, execute SQL indexes on production, and run a Codex security + accessibility audit. Antigravity handles visual delight on remaining pages.

## Carryover from Session 126

### Must Do
1. **SQL indexes on production** — `curl` the `/api/admin/run-migrations` endpoint after deploy. BACKLOG OPS-126-001.
2. **Flaky test** — `test_confirmed_anchors_in_face_to_photo` fails in full suite ordering. Same root cause pattern as Session 126 Phase 1 (stale cache state). BACKLOG TEST-001.
3. **Touch targets** — Cluster review badges `py-0.5` (16px), engagement pagination `px-2 py-1`. BACKLOG UX-AUDIT-001.
4. **SVG aria-labels** — ~20 icon elements without accessibility labels across tools_routes, main.py, discoveries_routes. BACKLOG UX-AUDIT-002.

### Should Do (P3 from Session 126 context, not yet addressed)
5. Top bar stat pills: "TO REVIEW" vs "PROPOSALS" labeling ambiguity
6. Focus/View All/Match button ordering — primary action should be leftmost
7. Person page: Born/Died/From "Unknown" — add community contribution CTA for confirmed people
8. Low-quality face crop fallback in grid cards
9. Merge search box: add friction gate for CONFIRMED people (prevent accidental merges)

## Codex Audit Scope

Run Codex as READ-ONLY auditor focused on:
- **Security**: Auth guard coverage, CSRF, input sanitization, Supabase RPC safety
- **Accessibility**: aria-labels, focus management, keyboard navigation, color contrast
- **Dead code**: Unused routes, orphaned functions, stale imports

Codex writes findings to `docs/session_context/session-127-codex-audit.md`. Claude Code triages and fixes high-impact items.

## Antigravity Scope

Antigravity handles CSS/template improvements on files Claude Code doesn't touch:
- `app/browse_routes.py` — card hover transitions, grid spacing
- `app/estimate_routes.py` — form styling, result card transitions

**CRITICAL**: Antigravity must `git checkout -b session-127/antigravity-polish` BEFORE making changes. Session 126 Antigravity committed to main instead of branch — enforcement needed.

## Technical Notes
- Session 126 blue→indigo sweep is complete. No blue CSS should remain in route files.
- Antigravity lightbox on person pages shipped in Session 126 (commit 7dd6cb0).
- 3394 tests pass, 0 failures on main as of Session 126 end.
- Deploy: `git push origin main` triggers Railway auto-deploy (Dockerfile builder).

## Breadcrumbs
- Session 126 UX audit: `docs/session_context/session-126-codex-ux-audit.md`
- Session 126 assessment: `docs/assessments/session-126-assessment.md`
- Antigravity constraints: `memory/feedback_antigravity_constraints.md`
- Lessons: `tasks/lessons.md`
