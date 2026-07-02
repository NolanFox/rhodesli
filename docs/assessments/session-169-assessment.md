# Session 169 Assessment — Fable 5 Full-Evaluation + Gated Phase-2 Ship

**Date:** 2026-07-02 · **Models:** Opus 4.8 (orchestrator) · Codex gpt-5.5/xhigh (coder + auditor, ×4 independent runs) · Fable 5 (evaluator, 1 autonomous run + 1 resume) · 1 general-purpose subagent (docs)

## What the user asked for
Run a full Fable-5 evaluation of rhodesli doing everything the Fable-5 community playbook suggests
(Vox read-only health-check, Fishbein roadmap/10x, Sisinty+Reddit write-skills-for-Opus) + more;
research it first; have Codex do independent research + its own prompt; synthesize one big prompt;
Codex audits it; when Opus+Codex agree, dispatch ONE Fable agent to run to completion; produce
evals measuring Fable-unique value; package reusably (for fox-genealogy etc.) + self-improving
("loop engineering"). Then (interactive) ship the safe fixes.

## Shipped (evidence)
- **Research** documented + sourced → `docs/fable-eval/RESEARCH.md` (Anthropic Fable-5 docs + 4 tweets + practitioner guides).
- **Two independent drafts** (Opus `opus-draft.md` + Codex `codex-draft.md`) → merged `FABLE_EVAL_PROMPT.md`.
- **Codex prompt-audit** verdict BLOCK → all P0/P1 applied (cut unsafe unsupervised impl; tool-enforced prod read-only; anti-stall caps) → `codex-audit.md`. Opus+Codex agreed.
- **1 Fable agent** ran the eval to Definition of Done (mid-run connection drop → resume-same-agent recovered it). Self-grade **8.5/10**.
- **3 reusable skills installed + verifier-gated** (`.claude/skills/split-brain-data-audit`, `supabase-migration-safety`, `route-safety-audit`).
- **Reusable + self-improving skill** `~/.claude/skills/fable-full-eval/` (repo-portable; §Self-improvement appended with 10 validated meta-lessons this session).
- **Phase 2 (gated) shipped to prod**: QW-1/2/3 security/data-integrity fixes + nav-contrast + favicon + 3 doc rewrites. Independent Codex fix-audit (SHIP-WITH-FIXES) caught 2 real P2 leaks → applied. `make test-fast` 4638 pass, ruff clean, pushed, deploy verified (favicon 200, nav class live).
- **Infra**: 16 GB stale worktrees reclaimed (content archived first); 8 secret-bearing allow-rules stripped.

## Deferred (with reason)
- **Detroit paid eval (~$0.50)** — user-approved but readiness analysis says NOT-READY (blocked on unbuilt `photo_year`-source + production-integration; $0 dry-run showed empty test set). Spend HELD; productive path = $0 design+implement steps 1–3 first. → `GEMINI_ESTIMATE_READINESS.md` Track-E note.
- Higher-risk eval findings (public "Dismissed" badge leak V2-1, archive "0 PEOPLE" V2-2/V2-5, count reconciliation V2-3, `/collections` scoping) → ranked in `QUICK_WINS_QUEUE.md` / eval artifacts for focused follow-up (product decisions).
- Secret ROTATION (R2/Resend keys) — user action; I stripped plaintext from settings but cannot rotate keys.

## Red flags / honest gaps
- Fable W2 mobile parity captured for 3 of ~12 surfaces (flagged in its coverage note, not claimed).
- QW-1 route-level test asserts no-500 + no-sentinel; does not seed a multi-community `_photo_cache` to assert specific foreign-filename absence (helper-level + audit manual verification cover the property).
- The reusable `fable-full-eval` skill lives at user level (outside git) — backed by the shared-memory pattern; not repo-versioned.

## Next session should verify FIRST
1. CI green on the push (`gh run list --branch main --limit 1`).
2. The QW-1 fail-closed behaves correctly for a REAL empty community (scope=set() vs None) on prod.
3. Whether to run the Detroit design+implement sequence (then the $0.50 eval).

## AI Tool Usage
- **Codex CLI v0.142.5 (gpt-5.5, xhigh)** — independent (fresh context) ×4: research+draft, prompt-audit (BLOCK), QW-2/3 coder, fix-audit (SHIP-WITH-FIXES). Value: **STRONG** — the two audits caught a BLOCK-worthy unsafe implementation track and 2 real P2 production leaks the coders missed. Would not have caught these on self-review.
- **Fable 5** — evaluator/skill-distiller (1 run + 1 resume). Value: **STRONG** — vision findings (Dismissed-badge leak, 0-people archives, LA/Florida contradiction) a code-only pass misses; honestly disproved one false positive via a network read.
- **general-purpose subagent** — 3 doc rewrites. Value: MODERATE (mechanical, accurate).
