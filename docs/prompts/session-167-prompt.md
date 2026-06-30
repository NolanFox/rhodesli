# Session 167 Prompt — Multi-Track Autonomous Feature Sprint

**Full context + per-track briefs:** `docs/session_context/session-167-context.md` (READ FIRST)
**Mode:** implementation, parallel, maximally autonomous. Nolan checks in intermittently.
**Orchestration:** Opus = architect/orchestrator/auditor; Codex gpt-5.5/xhigh = coding engine;
every track Codex-audited at its boundary (kicked off early).

## Goal

Stress-test autonomous multi-track throughput. Ship as much of 5 starved feature/ops
tracks as possible in parallel, each in its own worktree (or sibling repo), each
TDD'd and Codex-audited, committed to its own branch for orchestrator review + merge
at Nolan's check-ins. **No production writes, no $ spend, no irreversible/outward
actions unattended — flag those for Nolan.**

## Tracks (see context file for detail + acceptance criteria)

- **A — Ops hardening:** GEDCOM-TEST-FIX (verify; likely NO-OP post-164), OPS-002
  Supabase monitor+keep-alive, ESTIMATE-BACKFILL-166 (dry-run survey + ready script),
  GEMINI-API-CALLS-SCHEMA-166 migration SQL, Codex pin refresh.
- **B — Estimate v2 (PRD-055):** `/tools/estimate` gains GEDCOM upload + text hints +
  geography retry. `estimate_routes.py` + `tools_routes.py` + tests.
- **C — Self-service archive (PRD-060):** new `app/onboarding_routes.py` "Create Your
  Archive" flow; flag auth/permission decisions in `DECISIONS-FOR-NOLAN.md`.
- **D — Gemini Detroit fix (PROMPT-A-ITERATION-001):** Path-A residence-distance
  scoring step + eval harness; bounded eval (~$0.50 cap) on photos 02068 + 01659.
- **E — rhodes-wiki RHODES-WIKI-004 (sibling repo):** dossier auto-update from
  approved posts + first narrative `wiki/` pages + FB-ingest pipeline advance.

## Per-track exit contract

Return: branch name · commits · tests added/passing · Codex-audit verdict + path ·
open decisions for Nolan · "what shipped / what's left" paragraph. Honest partials
on budget exhaustion (Lesson 182).

## Phase plan (orchestrator)

0. Scaffolding + context/prompt (DONE). Create worktree branches sequentially (Lesson 167).
1. Dispatch track leads as background subagents.
2. Monitor; as each returns, review + run its Codex audit if not done, fix P0/P1.
3. At Nolan check-ins: report progress, surface decisions, merge approved tracks via
   `./scripts/merge.sh`.
4. Session-end: assessment, CHANGELOG/ROADMAP/BACKLOG/SESSION_HISTORY, CI green,
   `/session-review`, clear `.claude/parallel_session_active`. NO deploy until Nolan approves.

## Standing rules (session-defaults.md)
Every change tested · zero regressions · browser READ-ONLY on prod · dual test suites ·
Codex audit per track · /clear discipline · ai-tool-audit logging.
