# Session 166 Assessment — Multi-Model Photo Estimate + 3 Production Bug Fixes

**Date:** 2026-06-12 · **Mode:** interactive · **Version:** v0.99.86
**Trigger:** User asked to run a full date/location estimate on photo
`8346decbf2b2f8c1` (`IMG_1260.JPG` — Meyer Fox + Reva Heft), update the website +
Supabase, compare three models, write the best, and make manual runs
structurally distinguishable from platform runs.

## Shipped (with evidence)

- [x] **Gemini 3.1 Pro estimate, manual-tagged** — `gemini_api_calls` row written
  (`experiment_id=manual-multimodel-8346decbf2b2f8c1-2026-06-12`,
  `operator=claude-code-manual`, cost $0.0167, 27.3 s, status success). Confirmed
  via direct Supabase query.
- [x] **3-way model comparison** — Gemini / Fable 5.0 / Codex gpt-5.5-xhigh, same
  enriched prompt + image. All converged on decade 1910 / NYC / medium, ceiling
  1926. Raw outputs + `DECISION.md` in `docs/experiments/photo-estimates/8346decbf2b2f8c1-2026-06-12/`.
- [x] **Determination: Fable 5.0 wins** (Gemini near-tie; Codex over-weighted the
  print-format range toward 1900). Reasoning in DECISION.md + Lesson 207.
- [x] **Chosen estimate written to Supabase** — `date_labels` (decade 1910, best
  1912, range 1906–1920, NYC, `model=fable-5.0`, full `analysis_provenance`) +
  `photo_locations` (NYC, geocoded). Verified via query.
- [x] **Website renders it** — local render of the public AI-analysis section
  shows "circa 1912 · Range 1906–1920 · New York, New York · Estimated by AI".
  Production surfacing gated on deploy restart (see Open).
- [x] **Bug fix 1 — schema-drift-safe Gemini logging** (`bf8ff267`) +
  tests (`tests/test_gemini_api_logging.py::TestSchemaDriftFilter`).
- [x] **Bug fix 2 — GEDCOM loader Session-164 fix** (`bf8ff267`) — context now
  builds (verified: full Meyer+Reva residential history, 11 children, 1926
  ceiling) + regression tests (`TestGedcomLoaderSession164Schema`).
- [x] **Bug fix 3 — manual/platform provenance** (`bf8ff267`) + tests
  (`TestOperatorProvenance`).
- [x] **Harness wiring** — `.claude/rules/multimodel-photo-estimate.md`, AD-251,
  Lessons 205–207, CHANGELOG, this assessment.
- [x] `make test-fast` 4341 passed, 0 regressions.

## Design decision (user-directed)

`date_labels` is keyed by `photo_id` (upsert = last-write-wins); the website
renders one row, so it cannot hold competing estimates. `gemini_api_calls` is
Gemini-shaped. **Decision (AD-251):** chosen estimate → DB (+ provenance); ALL
candidates + the decision → versioned repo artifact. No migration. Documented
upgrade path: a `photo_estimate_experiments` table if DB-queryable experiments
are wanted at scale.

## Open / Next session should verify FIRST

1. **Production browser-verify** the live photo page shows "circa 1912 / NYC"
   after the Railway redeploy completes (deploy poll running at session end).
2. The GEDCOM-loader fix (Lesson 205) restored enrichment **platform-wide** —
   spot-check that other GEDCOM-linked photos' future estimates now include
   context (and that no IO regression appeared — Lesson 198 guard).
3. Consider a backfill: re-run estimates for GEDCOM-linked photos whose stored
   estimates were computed visual-only during the ~2-month loader outage.

## AI Tool Usage

- **Tools**: Gemini 3.1 Pro (estimate candidate), Fable 5.0 (Agent subagent,
  candidate), Codex gpt-5.5-xhigh (candidate + post-exec audit).
- **Task**: cross-model photo-dating comparison; Codex also audited the 4
  changed files (independent, fresh context).
- **Value**: STRONG — the comparison itself was the deliverable and produced a
  clear, defensible winner + a reusable methodology (AD-251). Codex audit
  findings logged in `docs/session_context/session-166-codex-audit.md`.
