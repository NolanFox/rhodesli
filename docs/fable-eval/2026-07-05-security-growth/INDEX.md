# 2026-07-05 — Security investigation + multi-Rhodesli growth evaluation

Triggered by: owner found 51 anonymous "Compare Upload" pending entries; worried about key exposure /
breach. Plus: "make rhodesli valuable for other Rhodeslis, non-spammy — lay out all the work."

Multi-model: Opus (orchestrate + verify) · Codex gpt-5.5/xhigh (independent security audit + eval
draft + brief audit-gate) · Fable 5 (live-site architect/evaluator, read-only).

## Read in this order
1. **SECURITY_VERDICT.md** — the owner-facing answer. TL;DR: no breach, no key exposure; 51 = public
   compare tool as designed. Two real limited findings: rotate committed `ML_SERVICE_TOKEN`; add
   `/photos` path-traversal guard. (Backed by `codex-security.md`.)
2. **GROWTH_ROADMAP.md** — THE deliverable. 28 items, phases A (safety, days) → B (trust-loop, wk2)
   → C (multi-tenant, wks 3-5) → D (polish), + concierge-pilot playbook + outreach-ethics.
3. **UX_NEWCOMER_AUDIT.md** — 11 live-site findings, desktop+mobile, screenshot-grounded (`screenshots/`).
4. **SPAM_BOUNDARY_DESIGN.md** — the ephemeral-compare vs explicit-contribute fix (roadmap item A1/A2).
5. **MULTITENANT_READINESS.md** — G1-G9 gap table; minimum safe concierge path (flag OFF).
6. **EVALS.md** — Fable-leveraged-value scorecard (vision-delta 7/11 findings absent from code-only drafts).

## Verified-by-orchestrator highlights
- **NEW P0 (both code drafts missed; Fable caught by loading the page):** `/c/rhodes/tree` renders the
  global/Fox GEDCOM — `/api/tree/data` (`app/page_routes.py:10950`) uses community only for nav prefix,
  not data scoping. Cross-community leak (Lesson 151 class). Map/Timeline/Connect are likely siblings.
- Logged-in compare uploads auto-approve into the archive (`app/compare_routes.py:1684`) — confirmed.

## Provenance
opus-draft.md + codex-draft.md → FABLE_EVAL_PROMPT.md → codex-audit.md (SHIP-WITH-FIXES, applied) →
Fable run (read-only, fresh unauthenticated Playwright; no source edits, no commits, no paid API).

## Status
EVALUATION complete. Implementation is a SEPARATE gated sprint (Phase A do-first items recommended
next). Nothing here mutated production, data, or source code.
