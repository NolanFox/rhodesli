# EVALS — Fable-leveraged value scorecard (2026-07-05 run)

Comparators exist for this run: two independent code-first drafts (`opus-draft.md`,
`codex-draft.md`) written before this evaluation. "Delta" claims below are measured against what
those two documents actually contain, not against a hypothetical.

## 1. Vision-delta — findings a code-only review missed
**Score: 7 / 11 audit findings are absent from BOTH prior drafts.** (Denominator = the 11
enumerated findings F1-F11 in `UX_NEWCOMER_AUDIT.md`.) — **Evidence-backed**

| Finding | In either draft? | Evidence |
|---|---|---|
| F1 Fox GEDCOM rendered on /c/rhodes/tree (no community filter in `/api/tree/data`) | No — neither draft mentions tree scoping at all | `screenshots/desktop-11-tree-loaded.jpeg` + `app/page_routes.py:10939` |
| F3 /tools/compare mobile horizontal overflow (793px @ 390 viewport) | No — codex only says "mobile improved but not proven" | `screenshots/mobile-04-compare.jpeg` + measured scrollWidth |
| F4 Root page renders internal changelog-speak + "demo archive" | No | `screenshots/desktop-01-root.jpeg` |
| F6 Three nav systems; "RhodesliPhotos" logo collision | No | `screenshots/desktop-04-person-page.jpeg`, `mobile-01-root.jpeg` |
| F7 Count contradiction (142 identified vs 88/87 people, same community) | No | `desktop-02` vs `desktop-09` |
| F8 Anonymous person comments publish instantly, unmoderated | No — both drafts audited compare/upload writes, missed this write surface | `app/person_routes.py:2291-2334` |
| F9/F10 Empty AI headers, internal model names, uncurated teaser faces | No | `desktop-05`, `desktop-03` |
| F2 compare consent gap | Partially (codex had the code fact; the *zero-disclosure UI* evidence is new) | `desktop-06` |
| F5 /help cross-community mix | Known as code policy (S168 fail-open); live dilution evidence new | `desktop-07/08` |
| G2 privacy unenforced | In both drafts (code); this run added the front-page live proof | `desktop-01` |

Also counts toward judgment quality: **2 false positives avoided** — the landing zero-stats row and
blank face circles looked like P0 bugs in full-page screenshots and were verified as scroll-
triggered lazy-load before reporting (`desktop-03`, in-viewport values 1,127/142/3,372/2,124).
**Evidence-backed.**

## 2. History-delta — lesson × current-code connections
**Score: 5 explicit connections wired into the deliverables.** — **Evidence-backed (each cites both ends)**
1. F7 count contradiction ↔ split-brain lesson family (78/144/150): flagged as the same recurring
   class, hence roadmap B6 demands ONE canonical definition, not a spot fix.
2. Pending-uploads cleanup (A5) ↔ data-repair protocol (snapshot-before-each-step,
   `feedback_data_repair_protocol`): unwind artifact required in the acceptance criterion.
3. Stale test comment "compare writes temp files only" (`tests/test_community_routing_safety.py:384`)
   ↔ Lesson 21/58 (assertions must match current behavior): called out in the migration note.
4. Tree reader ignoring the community-scoped schema ↔ Lesson 205 class (reader missed in a schema
   repoint = silent wrong-data, not an error): C3 framed as a reader-audit, and the recommendation
   to audit map/timeline siblings follows the "grep every reader" prevention rule.
5. Pilot kill-criterion design ↔ the churned-tester history (Session 169 W3/W4): B1/B2 promoted to
   pre-pilot specifically because the last external user churned on silent outcomes.

## 3. Roadmap-ambiguity-delta — ranked plan with kill criteria
**Score: 28 roadmap items, 28 with acceptance criteria (28/28); 4 explicit kill/deferral
triggers.** — **Evidence-backed** (`GROWTH_ROADMAP.md`: phased A1-A7/B1-B8/C1-C7/D1-D4; pilot kill
criterion; moderation-ML volume trigger; C7 flag-flip gate; FB-cadence cap). Three documented
disagreements with the prior drafts, each argued with evidence (CAPTCHA priority, rendered-surface
scoping omission, pre-pilot loop-closing) — refinement, not restatement.
**Proxy element:** sizes (S/M/L) are judgment estimates, not measured.

## 4. Long-horizon completion
**Score: 5 / 5 deliverables complete in one autonomous run** (UX_NEWCOMER_AUDIT, SPAM_BOUNDARY_
DESIGN, MULTITENANT_READINESS, GROWTH_ROADMAP incl. pilot playbook + outreach-ethics, EVALS), plus
FABLE_MEMORY maintained incrementally for interrupt-resume. 17 screenshots captured desktop+mobile;
prod touched read-only (unauthenticated GETs, zero form/upload/auth interactions; Playwright chosen
over owner-Chrome specifically to avoid carrying an admin session). — **Evidence-backed** (file
listing + screenshots dir).

## Honest limits (Unverified / not done)
- Map, Timeline, Connect surfaces not audited (budget); flagged as likely-sibling leaks of F1 —
  **Unverified**, listed as a pre-pilot check in MULTITENANT_READINESS.
- Help-Identify SUBMIT experience (what a contributor sees after submitting) described from code +
  prior evals, not exercised — mutation-safety rule forbids it on prod. **Proxy.**
- The ~51 pending-entry count was taken as given from the brief (admin page requires auth). The
  *mechanism* was verified in code; the count was not re-counted. **Proxy.**
- Share previews validated via OG meta tags in DOM, not via Facebook's actual scraper rendering.
  **Proxy.**
- No paid API spent; no data mutated; no commits made. Session log check: this run wrote only under
  `docs/fable-eval/2026-07-05-security-growth/`.
