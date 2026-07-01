# Session 168 Prompt

**Date:** 2026-07-01
**Mode:** Autonomous multi-model (Opus orchestrator/designer · Fable architect/auditor · Codex coder)
**Origin:** Interactive request — "continue our previous pattern (Fable architect+auditor, Codex coder, Opus designer). Do a holistic deep dive (Fable), then implement all the fixes you can. Run mostly autonomously while I'm away."

## Goal
Move the live Rhodesli site ahead. Fable does a holistic deep-dive to identify the
highest-value, lowest-risk work; Opus orchestrates; Codex implements; Fable audits.

## Guardrails (autonomous session)
- LOW-risk, S/M-effort items only without human review.
- EXCLUDE: production data mutation, Supabase schema migrations, destructive ops,
  anything requiring a live Gemini spend beyond a bounded eval. Those get logged
  for the user, not executed.
- Browser automation on production is READ-ONLY.
- Every change gets tests; `make test-fast` green before every commit.
- Codex audit after each implementation batch (per HD-030 dual-audit).

## Known follow-ups on the table (from Session 167)
- **NL-QUERY-REDOS-167** (P2): ReDoS in `rhodesli_ml/nl_query.py`; fix regex + add ML suite to CI.
- **DETROIT-PROMOTE-167** (P1): promote candidate-force from shadow harness to production
  prompt builder. NOTE: involves a bounded Gemini eval — gate before spending.
- **ESTIMATE-BACKFILL-166** (P2): re-run visual-only estimates — production data mutation + Gemini spend, DEFER to user.

## Phases
0. Orient + Fable holistic deep dive → prioritized findings report
1. Triage findings into an autonomous batch (Opus)
2. Dispatch Codex coders per finding (parallel where file-disjoint)
3. Fable audits each batch
4. Closeout (assessment, CHANGELOG, ROADMAP, deploy, browser verify)
