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
- [x] UX_NEWCOMER_AUDIT.md  (LIVE-SITE screenshots, desktop + mobile, newcomer's eyes — YOUR core job)
- [x] SPAM_BOUNDARY_DESIGN.md
- [x] MULTITENANT_READINESS.md
- [x] GROWTH_ROADMAP.md  (THE deliverable — sequenced, phased, concierge-pilot playbook)
- [x] EVALS.md

## Rules
- READ-ONLY on prod (screenshots/reads/nav only; never click a mutating control — Lesson 149).
- $0 paid-API. No source edits/commits. Bounded subagents (2-3 reads each). Verify counts.
- On usage limit: stop cleanly, report what's done + what remains (resume-friendly).

## Running notes
- Browser pass DONE (Playwright, fresh unauthenticated browser — correct newcomer posture; owner's
  Chrome would carry an admin session). Desktop 1440x900 + mobile 390x844. 17 screenshots in
  `screenshots/`. Health 200; sitemap live (1267 URLs: 1127 photo + 136 person + tools/help/root).
- Key live findings (each screenshot-grounded, code-linked):
  1. /c/rhodes/tree renders the FOX family GEDCOM (Meyer Fox, Sadie Fox Levine, Fader/Newman) —
     `/api/tree/data` app/page_routes.py:10939 has NO community filter (slug only used for nav
     prefix). NEW finding both code-drafts missed. desktop-11-tree-loaded.jpeg.
  2. /tools/compare mobile: horizontal overflow, docScrollWidth 793 vs viewport 390 (nav doesn't
     collapse on tools pages). mobile-04-compare.jpeg.
  3. /tools/compare has ZERO retention/consent disclosure while anonymous uploads persist to R2 +
     pending queue (compare_routes.py:1664-1700). desktop-06-tools-compare.jpeg.
  4. Root page copy is internal changelog-speak ("removes the old Rhodes-by-default ambiguity",
     "demo archive"); Fox Family personal archive publicly listed (privacy unenforced, visible).
     desktop-01-root.jpeg.
  5. Unprefixed /help mixes ALL communities (Fox Dayton/Fader alongside Rhodes) — documented
     fail-open. desktop-07/08.
  6. Count inconsistency: /c/rhodes/ says "142 PEOPLE IDENTIFIED"; /c/rhodes/people says "88 people,
     87 named". desktop-09-people-grid.jpeg.
  7. Person page nav broken ("RhodesliPhotos" collision, stray "Explore More Photos"); 3 different
     nav systems across root/landing/person. desktop-04-person-page.jpeg.
  8. Anonymous person comments are LIVE immediately, no moderation (person_routes.py:2291-2334,
     status:"visible") — unmoderated public write surface.
  9. NOT bugs (verified): landing zero-stats + empty face circles = scroll-triggered lazy-load;
     stats read 1,127/142/3,372/2,124 in-viewport. desktop-03.
  10. Photo page excellent on mobile; person page mobile good; landing mobile good. Tree load ~10s
     text-only placeholder. Photo page exposes internal model names ("gemini-3.1-pro-preview").
- Logged-in compare uploads are AUTO-APPROVED into archive (compare_routes.py:1684-1704) — big
  deal once self-service signup widens.
- Deliverable status: ALL COMPLETE — [x] browser evidence (17 screenshots) · [x] UX_NEWCOMER_AUDIT.md
  (11 findings F1-F11 + strengths + loop walkthrough) · [x] SPAM_BOUNDARY_DESIGN.md (ephemeral-by-
  default + explicit contribute; alternatives table; migration note) · [x] MULTITENANT_READINESS.md
  (G1-G9 gap table; minimum pilot path) · [x] GROWTH_ROADMAP.md (A/B/C/D phases, 28 items w/
  acceptance criteria, pilot playbook, OUTREACH-ETHICS) · [x] EVALS.md (vision-delta 7/11 vs both
  drafts; 2 false positives avoided; honest Unverified list: map/timeline/connect unaudited).
