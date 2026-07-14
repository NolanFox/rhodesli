# Session 170 — Phase A: Make the Public Front Door Safe (security + spam boundary)

**Predecessor:** Session 169b (2026-07-05 security + growth evaluation) — read
`docs/fable-eval/2026-07-05-security-growth/INDEX.md` FIRST, then `GROWTH_ROADMAP.md` and
`SECURITY_VERDICT.md`. Assessment: `docs/assessments/session-169b-security-growth-eval-assessment.md`.

This session IMPLEMENTS Phase A of the roadmap. It is the gated implementation sprint the eval
deliberately deferred. Use the `multimodel-sprint` pattern (Codex codes from a written spec →
independent audit before push → read-only prod browser-verify). Load skills: `route-safety-audit`,
`split-brain-data-audit`, `supabase-migration-safety` (only if a migration is touched).

---

## 1. Project identity / non-negotiables
rhodesli — heritage photo archive for the Jewish community of Rhodes. FastHTML+HTMX / Supabase-
Postgres (source of truth) / R2 / Railway / InsightFace + Gemini. Admin: NolanFox@gmail.com. Deploy =
`git push origin main`. Invariants: Postgres canonical; UI never deletes a face; provenance human >
model; every change gets tests (happy+failure+regression); browser automation READ-ONLY on prod
(Lesson 149); `make test-fast` green before every commit; `core/neighbors.py`/`core/pfe.py`/`data/*`
frozen.

## 2. Honest current state (works / broken)
- **WORKS:** the public compare tool, person/photo share pages (strong OG cards, good on mobile),
  community `/c/<slug>/` routing + fail-closed identity/photo scoping (Session 169).
- **BROKEN / unsafe (this session fixes the safety subset):**
  - Anonymous `/api/compare/upload` PERSISTS uploads to R2 + `pending_uploads` (source of the 51
    spam entries). Compare should be ephemeral. `app/compare_routes.py:1571-1700`.
  - Logged-in compare uploads AUTO-APPROVE into the archive. `app/compare_routes.py:1684`.
  - **P0 cross-community leak:** `/c/rhodes/tree` renders the global/Fox GEDCOM — `/api/tree/data`
    filters community only for nav prefix, not data. `app/page_routes.py:10950`. Map/Timeline/
    Connect likely the same (audit them).
  - Anonymous person comments publish instantly, unmoderated. `app/person_routes.py:2291-2334`.
  - Missing path-traversal guard on `/photos/{filename:path}` + `/uploads/facecompare/`.
    `app/main.py:1439`.
  - No batch-reject for pending uploads (only one-at-a-time `/admin/pending/{job_id}/reject`).

## 3. Technical map / IDs the next agent needs
- Compare upload flow: `app/compare_routes.py` (`/api/compare/upload` :1571, `/upload-multiple`
  :3024, `/pair/upload` :4207, `/contribute` :3355 [login-gated — the correct pattern]).
- Pending queue: `_load_pending_uploads`/`_save_pending_uploads` (`app/main.py:2106-2127`); admin
  routes `app/admin_routes.py` (`/admin/pending` :538, `/reject` :1390, `/batch-approve` :1609).
- Auth gate: `_check_admin` (`app/main.py:1972`, global `ADMIN_EMAILS`). Rate limiter (in-memory,
  20/hr/IP): `app/rate_limit.py`.
- Tree data: `app/page_routes.py:10939` (`/api/tree/data`).
- Full patch-level specs for each item are in `GROWTH_ROADMAP.md` Phase A table (A1-A7).

## 4. The work — Phase A items (from GROWTH_ROADMAP.md; all S/M, none blocks another)
- **A1** Make anonymous compare ephemeral (no `pending_uploads` row / no R2 object). Update the stale
  test `tests/test_community_routing_safety.py:384`.
- **A2** Explicit disclosed "Add to archive" step (login OR email+Turnstile) posting to the existing
  `/api/compare/contribute` route.
- **A3** Remove logged-in auto-approve (`compare_routes.py:1684`) — non-admin contributions → pending.
- **A4** Pending hygiene: `community_id` on every entry; 30-day expiry for anonymous sources; R2
  lifecycle on `uploads/pending/`.
- **A5** Add batch-reject + one-time cleanup of the existing ~51 Compare-Upload entries (snapshot
  first — `split-brain-data-audit` + reversible unwind artifact).
- **A6** Person comments pending-by-default (admin approve).
- **A7** Security carry-overs: path-traversal guard on `/photos` + `/uploads/facecompare/`; **rotate
  `ML_SERVICE_TOKEN`** (USER ACTION — see §7).
- **P0 tree leak** (roadmap C3, but pull it FORWARD if it's quick): scope `/api/tree/data` (and
  Map/Timeline/Connect) to the community or show an honest empty state. This is the #1 pre-pilot bug.

Recommended order: A7-traversal + A6 + A5 (quick, isolated) → A1 + A3 (compare policy) → A2 (UI) →
A4 (hygiene) → tree-scoping. Commit atomically per item; `make test-fast` between.

## 5. Landmines / do-not-touch
- **Split-brain (10+ prior occurrences):** any data-write MUST hit Postgres, not just JSON. A5 cleanup
  MUST snapshot + write a reversible unwind artifact before deleting rows/R2 objects.
- Prod browser is READ-ONLY — verify with unauthenticated GETs/screenshots only (Lesson 149).
- Turnstile (A2) is a NEW external dep — if the owner doesn't want it, login-gate contribution instead.
- Don't widen `SELF_SERVICE_ARCHIVE_ENABLED` — that's Phase C, gated on owner permissions.
- Rate limiter is in-memory (resets on deploy) — adequate at pilot scale per the roadmap; don't
  over-invest in persistent limits now (that's Phase C).

## 6. Deferrals (not this session)
Phase B (trust-loop: contribution receipt + notify), Phase C (multi-tenant: owner perms, privacy
enforcement, storage scoping, owner console), Phase D (SEO/measurement). Full detail in
`GROWTH_ROADMAP.md`.

## 7. Open questions needing HUMAN judgment (surface at session start)
1. **USER ACTION — rotate `ML_SERVICE_TOKEN` on Railway** (committed value in
   `docs/session_logs/session-116-log.md`). Confirm done before treating security as fully closed.
2. A2: Turnstile vs login-only for anonymous contribution? (owner preference — cost/friction tradeoff).
3. Confirm Phase A scope + priority order with the owner before coding (they said they'd read
   `GROWTH_ROADMAP.md` and may adjust).
4. Reject the 51 now (manually) or wait for the A5 batch-reject tool to ship and use it?

## 8. Per-item confidence tier
- **VERIFIED (code-checked this session):** compare persists anonymous uploads (A1); logged-in
  auto-approve (A3); tree cross-community leak (P0); missing `/photos` traversal guard (A7); committed
  `ML_SERVICE_TOKEN`; no batch-reject exists (A5); anonymous comments instant-publish (A6).
- **CARRIED-FORWARD (Fable live-site, screenshot-grounded, not re-verified by orchestrator):** compare
  mobile overflow; root changelog-speak copy; 142-vs-88 count mismatch; nav collisions. (Phase B — not
  this session, but true enough to act on.)
- **ASSUMED (needs a first check):** Map/Timeline/Connect share the tree-leak bug; the ~51 count
  (auth-gated, not re-counted).

## NEXT ACTION
`echo "170" > .claude/current_session.txt` → read `INDEX.md` + `GROWTH_ROADMAP.md` → confirm Phase A
scope with owner (§7) → start with A7 path-traversal guard + A6 (smallest, highest-safety, isolated),
writing a Codex coder-spec + independent audit before push per `multimodel-sprint`.
