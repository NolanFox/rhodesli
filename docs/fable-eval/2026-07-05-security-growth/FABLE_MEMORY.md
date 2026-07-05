# Fable working memory — 2026-07-05 security+growth eval

Persist findings here as you go so nothing is lost if the run is interrupted.

## Fixed context (do not re-derive)
- Security question CLOSED: 51 "Compare Upload" pending = public compare tool as-designed, no breach,
  no live key exposed. Two limited real findings (path-traversal guard missing; ML_SERVICE_TOKEN in
  a committed session log) → implementation sprint, not this run.
- Product goal: make it valuable for OTHER Rhodes families, non-spammy. Concierge pilot, NOT broad
  self-service (both independent drafts agree).
- The gate: global-admin permission model (`_check_admin`, `app/main.py:1972`) → new owners can't
  triage their own archive (WORKSPACE-006). Privacy stored not enforced. Compare/contribution
  conflated. Self-service onboarding built but flag-OFF.

## Deliverables to produce (write to this run dir)
- [ ] UX_NEWCOMER_AUDIT.md  (LIVE-SITE screenshots, desktop + mobile, newcomer's eyes — YOUR core job)
- [ ] SPAM_BOUNDARY_DESIGN.md
- [ ] MULTITENANT_READINESS.md
- [ ] GROWTH_ROADMAP.md  (THE deliverable — sequenced, phased, concierge-pilot playbook)
- [ ] EVALS.md

## Rules
- READ-ONLY on prod (screenshots/reads/nav only; never click a mutating control — Lesson 149).
- $0 paid-API. No source edits/commits. Bounded subagents (2-3 reads each). Verify counts.
- On usage limit: stop cleanly, report what's done + what remains (resume-friendly).

## Running notes
(append as you work)
