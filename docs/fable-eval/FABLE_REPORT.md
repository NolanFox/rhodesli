# FABLE_REPORT — rhodesli full evaluation (2026-07-02)

## What happened
A single autonomous Fable-5 run evaluated the rhodesli repo and its live product end-to-end across
8 workstreams, and distilled the project's hard-won judgment into 3 reusable skills for Opus 4.8.
It read the live site **logged-out, read-only** (15 screenshots, desktop + mobile), ran 7 bounded
read-only subagent dives, and synthesized 12 evidence-backed artifacts under `docs/fable-eval/`.
**No source code was changed, nothing was committed or pushed by the Fable agent, no paid API was
called.** The run survived a mid-synthesis connection drop with full context and finished to the
Definition of Done. The live site is, on the whole, **genuinely impressive** — museum-quality design,
a real growth loop, and a standout AI photo-analysis page — with a small set of high-value gaps.

## Top 3 things Nolan should look at first
1. **Two active cross-community data leaks + two unthrottled auth endpoints** (the repo's #1 bug
   class, live in code). `/c/<slug>/photos` renders the **full multi-community corpus** on any
   Supabase blip (it fails *open*; the identity path fails *closed*), `/collections` is entirely
   unscoped, and `/login/modal` + `/forgot-password` have no rate limit. All four are small,
   test-gateable diffs → `QUICK_WINS_QUEUE.md` QW-1/QW-2 (+ QW-3 community-404 cache). Evidence:
   `CODE_FINDINGS.md`, `DATA_INTEGRITY_AUDIT.md`.
2. **The public contribution loop leaks admin state and contradicts itself.** On a public photo page
   whose CTA is "can you help identify?", **all faces show a red "Dismissed" badge**; the People page
   says "131 awaiting identification" but its "Needs Name (0)" filter is empty; and two of three
   archive cards (including your own 670-photo Fox Family) show **"0 PEOPLE / 0 identities."** These
   sit exactly on the Find→Recognize→Respond step and are what the one real community tester churned
   on (silent failures). Evidence: `SITE_VISION_AUDIT.md` (V2-1/2/3/5), `GROWTH_10X.md` Bet 2.
3. **Two decorative-but-real harness risks + 18 GB of reclaimable disk.** Three **live secrets in
   plaintext** in `.claude/settings.local.json` (rotate today), permission deny-rules neutered by
   `bypassPermissions`, and **854 MB of production-data backups committed to git** inflating 17 stale
   worktrees to 16 GB. Plus: the two architecture docs `@`-imported into *every* session still
   describe the JSON-canonical system that stopped existing 4 months ago. Evidence: `HEALTH_AUDIT.md`.

## What shipped (artifacts + skills)
- **3 verified skills installed** to `.claude/skills/`: `split-brain-data-audit`,
  `supabase-migration-safety`, `route-safety-audit` (drafted → fresh-context verifier gate
  APPROVE-WITH-EDITS ×3 → E1/E2/E3 applied → installed; usability **USABLE-WITHOUT-AUTHOR**).
  Summaries: `SKILLS_WRITTEN.md`, `PORTABLE_SKILLS.md`.
- **8 evaluation artifacts:** `SITE_VISION_AUDIT.md` (W2), `DATA_INTEGRITY_AUDIT.md` (W3),
  `CODE_FINDINGS.md` (W4), `HEALTH_AUDIT.md` (W1), `GROWTH_10X.md` (W5, 3 ranked bets),
  `GEMINI_ESTIMATE_READINESS.md` (W6), `QUICK_WINS_QUEUE.md` (W8), `EVALS.md` (self-grade 8.5/10).
- **Support:** `FABLE_MEMORY.md`, 7 raw dives in `subagents/`, 15 screenshots in `screenshots/`.

## Queued as User Decisions (forbidden actions — logged, never executed)
- **Rotate 3 live secrets** + remove `sudo rm:*`/garbage allow-rules (`HEALTH_AUDIT.md` #3/#4).
- **Reclaim ~18 GB** (worktree prune, untrack data-backups, checkpoint/branch cleanup) — all deletions
  gated (`HEALTH_AUDIT.md` #1/#2/#6/#8).
- **DETROIT-PROMOTE-167:** NOT-READY — needs `photo_year`-source design + production integration, then
  a ~$0.50 bounded paid eval (`GEMINI_ESTIMATE_READINESS.md` UD-1/2/3).
- **Global-head fixes** (nav contrast V2-6, favicon QW-5): touch the excluded global layout → Phase 2.
- **Doc rewrites** (`DATA_MODEL.md`/`OVERVIEW.md`/`PERMISSIONS.md`): outside `docs/fable-eval/` →
  orchestrator's to execute (QW-4).
- **Phase-2 code sprint:** run QW-1/2/3 + the W3 write-failure-visibility fixes under full test gates
  with the new skills loaded and an independent audit before push.

## Safety ledger
- **Production auth state:** anonymous throughout. Fresh Playwright browser, never logged in.
- **Production request methods observed:** GET only (navigation + screenshot + DOM/console/network
  reads). **Zero** clicks on mutating controls, **zero** form submits, **zero** non-GET requests to
  `rhodesli.nolanandrewfox.com`. Network read confirmed only crop/asset GETs (35/35 200 OK).
- **External API spend:** **$0.** No Gemini/paid calls, no Supabase/R2/Railway writes, no
  `--execute` scripts, no migrations, no deploys.
- **Files created/edited by the Fable agent:** only `docs/fable-eval/**` (12 artifacts + 7 subagent
  files + 15 screenshots + 3 skill drafts) and the 3 new `.claude/skills/<name>/SKILL.md` dirs (after
  the verifier gate). **No** existing app/source/test/rule/settings/frozen/doc-outside-fable-eval file
  was edited. Working tree confirmed clean outside those paths.
- **Commits/pushes by the Fable agent:** none. (The orchestrator made `wip(fable-eval)` checkpoint
  commits of the artifacts during the run for crash-safety; the merge/push remains orchestrator-gated.)
- **Tests run:** none of the full suite. No targeted `pytest`/`ruff` was ultimately required to land
  a finding (all defects were airtight code-path proofs or live DOM/network reads); file:line claims
  were verified by direct reads. Referenced test files' existence was confirmed via `ls`.
- **Unverified claims (labeled honestly):** mobile parity captured for only 3 of ~12 surfaces
  (rest desktop-only — flagged in `SITE_VISION_AUDIT.md`); the "not verbatim in BACKLOG" novelty claim
  is Proxy for 2-3 bug-recall items (not exhaustively grepped); W4 did **not** run a stored-XSS
  render-site pass or an IDOR/cross-community authorization sweep (flagged in its coverage appendix);
  all repo counts/sizes/CI-status were verified before citing, except where a cell is marked Proxy.

## Workstreams left incomplete (honest)
None of the 8 priority workstreams were dropped. **Partial coverage, explicitly bounded:** W2 mobile
parity (3/12 surfaces); W4 stored-XSS + IDOR sweeps (out of the auth-presence mandate). Everything
else met its output contract and cap.
