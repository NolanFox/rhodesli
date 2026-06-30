# Session 167 — Codex Plan Audit (session-level)

**Auditor:** Codex CLI v0.142.4 (gpt-5.5, xhigh)
**Agent type:** Independent (fresh context)
**Scope:** The Session 167 PLAN/scaffolding — `session-167-context.md` + `-prompt.md`;
spot-checked `scripts/merge.sh`, `Makefile`, `pyproject.toml`, `tests/conftest.py`,
`app/main.py` route-import block. (Run BEFORE deep track execution — audit-at-boundary.)
**Date:** 2026-06-30 · tokens ~86,826
**Value:** STRONG — caught real cross-track merge + guardrail risks before they bit.

## Findings + orchestrator disposition

### P0
1. **Guardrails not fail-closed (money/prod).** `setup-worktree.sh` copies main `.env`;
   Track A touches Supabase/Mgmt API, Track D spends Gemini.
   → **DISPOSITION:** Mitigated — worktrees created via raw `git worktree add`, so `.env`
   (gitignored) did NOT copy. Residual: A/D reach main `.env` by absolute path (intended:
   A read-only, D bounded eval). **Action sent:** Track D hard `--max-usd`/`--max-calls`
   cap + ledger; Track A read-only only, no migrations applied.
2. **Track C may violate "admin-only for data-modifying features."**
   → **DISPOSITION:** Agreed. **Action sent:** Track C builds feature-flagged/read-only
   prototype; NO live community-creation writes; tests assert disabled POSTs don't write;
   permission design → decisions file for Nolan.

### P1
3. **`scripts/merge.sh` unsafe here** (auto-commits dirty worktrees; app-tests only).
   → **DISPOSITION:** Accepted for MERGE phase. Orchestrator will NOT blind-merge: require
   clean branch + audit artifact + base SHA; run `make lint && make test-fast && make test-ml`
   post-merge. (Harden or bypass merge.sh.)
4. **Parallel flag doesn't block Codex/merge.sh commits to main.**
   → **DISPOSITION:** Low risk for worktree agents (each on its own branch, can't be on main).
   **Action sent:** Codex must not commit; the Opus lead commits after review.
5. **Cross-track shared-doc conflicts** (ROADMAP/BACKLOG/CHANGELOG/SESSION_HISTORY/
   conftest.py/app/components/*). My briefs didn't forbid these — real gap.
   → **DISPOSITION:** **Action sent to ALL tracks:** do NOT edit shared docs/conftest/
   components; scoped notes only; orchestrator reconciles at merge. Track C: main.py = 1 import line.
6. **B/D conflict on `rhodesli_ml/gemini_extraction.py`; A/B on `gemini_api_calls` schema.**
   → **DISPOSITION:** **Action sent:** D owns the prompt-builder; B stays app-layer + keeps
   gemini logging backward-compatible (no dependency on un-applied SQL columns).

### P2
7. Isolation OK only if pytest runs from worktree cwd → **VERIFIED already** (Q1, meta-lessons).
8. **Track B brief contradicts PRD-055:** brief said `.ged upload`; PRD-055 says GEDCOM
   **paste**, file upload OUT of scope; existing xfail tests are paste-oriented.
   → **DISPOSITION:** **Action sent to B:** follow PRD-055 (paste), align to xfail tests.
9. **Track D "$0.50 cap" vs "keep trying" contradiction.** → **Action sent to D:** hard caps;
   failure-to-replicate is acceptable (document, don't loop).
10. **Track E denied write to rhodes-wiki** by `.claude/settings.json` deny list (cross-repo
    invariant). → **DISPOSITION:** CONFIRMED. **Action sent to E:** wind down + report; the
    work must run from a DEDICATED rhodes-wiki session. Track E BLOCKED this session.

### P3
11. Exact worktree lookup in merge tooling (not `grep $BRANCH`). → merge-phase note.
12. Track C decisions file → `docs/feedback/session-167-track-c-decisions.md` (namespaced). → sent.
13. Post-merge route-registration smoke for `onboarding_routes` after `_reorder_routes_atomic()`. → merge-phase note.
