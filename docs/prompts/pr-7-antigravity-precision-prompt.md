# Prompt For Antigravity On PR #7: Precision Fix

Work only on branch `modern-ui-research` and PR #7:
https://github.com/NolanFox/rhodesli/pull/7

Before editing, re-read:
- `docs/assessments/pr-7-modern-ui-antigravity-revision.md`
- `docs/session_logs/pr-7-modern-ui-codex-log.md`
- `docs/session_context/pr-7-modern-ui-codex-context.md`

This is one final docs-only precision fix before Session 99 prompt writing.

Please update `docs/assessments/pr-7-modern-ui-antigravity-revision.md` with this repo-backed correction:

1. Fix the `/?section=...` preservation invariant.
- Right now the doc says the workstation root preserves `The HTMX sidebar structure (hx-get="/?section=...") and section count badges.`
- That overstates the contract.
- The actual section navigation in `app/main.py::sidebar` is regular anchor `href` navigation, not HTMX section swapping.
- Replace that line with a repo-accurate preservation statement built around:
  - the sidebar navigation structure for the workstation root
  - the explicit section links (`/?section=to_review`, `/?section=skipped`, `/?section=photos`, etc.)
  - the visible count badges
  - the overall command-center shell where relevant
- If you mention HTMX on this route, limit it to features that are actually HTMX-driven on that page rather than the main section navigation.

2. Preserve attribution boundaries.
- user-directed orchestration
- Antigravity-authored research/revision
- Codex-authored audit/handoff artifacts
- PR-thread collaborative boundary

When finished:
- commit only the revised Antigravity-authored document
- comment on PR #7 summarizing the precision correction
