# Path Forward — after Session 168

**As of:** 2026-07-02 · v0.99.89 · CI green · site live + verified.
Two lanes: **(A) move the site ahead** (product) and **(B) sharpen the sprint methodology** (harness).
The next sprint should run under the `multimodel-sprint` skill (HD-036).

## Lane A — Product / growth loop (next autonomous-safe wins)
Ranked by value × safety (all LOW-risk unless noted):
1. **G5 — canonical URL fix** (P2, from Fable R2). `/c/<slug>/` pages emit a canonical WITHOUT the community
   prefix (contradicts og:url; SEO indexes non-Rhodes content under Rhodes URLs). Touches the global `<head>`
   in `app/main.py` (`fast_app(canonical=False)` + `Link(rel=canonical)` in `og_tags`) → **sequential, browser-verify
   head tags on 3 page types post-deploy.** Pairs naturally with the new `/sitemap.xml` (both want community canonicals).
   BACKLOG: `CANONICAL-COMMUNITY-URL-168`.
2. **G9 — shared-person badge on public surfaces** (P3, COMMUNITY-004). Add `_cross_community_badge` to the public
   people grid + person-page name block. **MED risk — verify the identity_communities lookup is cached before an
   88-item loop (N+1).** BACKLOG: `SHARED-PERSON-BADGE-PUBLIC-168`.
3. **Mobile audit continuation** — Fable R2 fixed the help grid; do a systematic pass over person/photo/compare on
   375px (touch targets, overflow, stacked layouts). Memory flags mobile as historically critical.
4. **WORKSPACE-002/003** (sharing mode UX, add-photos-to-community flow) — depends on WORKSPACE-001 (done).

## Lane A — needs a USER decision first (do not run autonomously)
- **DETROIT-PROMOTE-167** — port the shadow candidate-force into `rhodesli_ml/gemini_extraction.py`; acceptance
  REQUIRES a bounded Gemini eval (~$0.30 spend gate). Fully specced. Say "run the Detroit eval" to green-light.
- **F7b** — refresh the volume-JSON backup from Postgres (production volume write; `/health` still shows
  `data_parity.synced:false, photo_diff:147` = the Fader collection never synced to the backup). Direction-sensitive
  (never the resync-supabase endpoint). Ready to run on your OK.
- **F12** — set `SELF_SERVICE_ARCHIVE_ENABLED=true` on Railway (exposes a write surface to all logged-in users;
  suggest a pre-flight browser walkthrough).
- **COMMUNITY-001 remainder** — `/c/<slug>/about` still shows Rhodes copy; needs your per-community about text.
- **F13** — commit RHODES-WIKI-004 from a dedicated rhodes-wiki session (cross-repo boundary).

## Lane B — Sharpen the sprint methodology (from the meta-analysis §4)
Ranked by ROI:
1. **Extend `scripts/simulate_ci_data.py` → a full `scripts/simulate-ci.sh`** (highest ROI). Combine in one pass:
   dep-subtraction (fold in `check_ml_suite_ci_safe.py`), data-subtraction (the HEAD-worktree, already built), and
   **invalid-but-set Supabase creds** (Lesson: CI sets secrets → `is_auth_enabled()` True → surfaces auth-env
   failures). Run WITHOUT `-x` to find everything in one pass. This removes the entire "local-green ≠ CI-green"
   failure class mechanically (the only kind that sticks — Lessons 102/140). Candidate to wire into `session-defaults.md`
   pre-push and/or a PostToolUse advisory hook.
2. **Coder wall-clock watchdog** — a background timer per Codex dispatch that alerts at 2× budget, so the manual
   kill (that saved 30+ min on Job P1) becomes structural, not orchestrator-attention-dependent.
3. **Worktree-isolated parallel-coder wrapper** — only worth building when a session carries 3+ independent coding
   jobs; watch Lesson 180 (absolute paths escape worktrees → instruct relative paths + diff-check main-tree writes).
4. **Use + refine the `multimodel-sprint` skill** every sprint; the skill's §"improvements not yet tried" is its
   own backlog. Port it live in fox-genealogy on the next research sprint (the research adaptation is written but
   untested end-to-end).

## First actions for the next session
1. `bash scripts/harness-check.sh` + confirm CI green (`gh run list --branch main --limit 1`).
2. Invoke `/multimodel-sprint` (or state the roles) → Phase A bootstrap: `bash scripts/bootstrap-gate-files.sh <NN>`.
3. If product lane: dispatch Fable on ONE bounded dive (start with G5+G9+mobile as a "community-polish" scope).
4. Pre-push: run BOTH `scripts/check_ml_suite_ci_safe.py` AND `scripts/simulate_ci_data.py` (ML-4), then the
   independent audit (ML-1, hard gate).
