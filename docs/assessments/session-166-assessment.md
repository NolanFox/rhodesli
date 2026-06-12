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

---

## Per-Act Status (session-review)

| User request | Status | Evidence |
|--------------|--------|----------|
| Run full geo+date+API analysis on the photo | **PASS** | `gemini_api_calls` row (1, manual-tagged); 3-model run in artifact dir |
| Update website + Supabase | **PASS** | `date_labels` 1910/1912/fable-5.0; live page "circa 1912 · New York, New York" (verified after deploy, ~440s) |
| Log API outputs in Supabase; differentiate manual vs platform structurally | **PASS** | `experiment_id=manual-...` + `gemini_config.operator=claude-code-manual`; schema-drift filter fixed so logging works at all |
| Run Fable 5.0 + Codex 5.5 xhigh + compare, determine best | **PASS** | candidate-fable/codex/gemini.json + DECISION.md; winner Fable 5.0 |
| Log all 3 outputs; website gets best; record decision; schema supports it | **PASS** | chosen→DB (+provenance), all 3 + decision→repo artifact (AD-251 methodology) |
| Meyer + Reva both GEDCOM-linked; correct if needed | **PASS (already correct)** | both linked (`@I132127405051@`/`@I132127405052@`, family `@F5091@`); no correction needed |
| Re-run with fully-enriched prompt | **PASS** | GEDCOM loader fixed → 4876-char enriched context (Meyer+Reva residential history, 11 children, 1926 ceiling) |
| Document learnings + wire into harness | **PASS** | rule + AD-251 + Lessons 205–207 + CHANGELOG/ROADMAP |

## Auto-Fix Summary
The independent **Codex post-execution audit** (gpt-5.5/xhigh) served as the auto-fix pass.
- Issues found: 6 (0 P0, 3 P1, 2 P2, 1 P3)
- Auto-fixed: 6 (all) — commit `53081ca6`
- Deferred: 0
- No separate auto-fix worktree subagent needed — all concerns resolved inline with tests + a community-filter regression guard. Record: `docs/session_context/session-166-codex-audit.md`.

## Concerns / Red Flags
- None outstanding. The GEDCOM-loader outage (Lesson 205) means historical estimates computed during the ~2-month window were visual-only — flagged in "Next session should verify" as a candidate backfill (not a regression introduced this session).

## Retrospective — what worked / what didn't

### What worked
- **Running the real production pipeline on one concrete photo** surfaced TWO silent multi-month regressions (broken Gemini logging + dead GEDCOM context) that all 4341 unit tests passed straight through. Highest-yield debugging move of the session — see Lesson 208.
- **Driving the production route helpers locally against live Supabase** (patching only the image loader + auth) gave a byte-faithful write path without re-implementing it.
- **Cross-provider comparison via native tooling**: Fable through an `Agent` subagent (`model: fable`), Codex through `codex exec -i image.jpg` — both saw the same image + prompt, run in parallel. Fair and cheap.
- **GEDCOM enrichment is the dominant accuracy lever**: the spouse-death ceiling (1926) + apparent-age anchoring turned a vague "1890–1920 oval portrait" into a confident ~1912 / NYC. The model that used it best (Fable) won.
- **Codex post-exec audit earned its keep**: caught two data-integrity risks in the new write path (full-document overwrite, cross-community GEDCOM leak) that the unit tests did not.

### What didn't / friction
- **First Gemini call returned `None`** (transient API error) and was briefly mistaken for a hard failure; a direct re-run worked. Transient ≠ broken — recheck before concluding.
- **Python `urllib` SSL had no CA roots** (cert verify failed) — needed a `certifi` context; `curl` worked. Minor but cost a cycle.
- **Dual photo-ID space** (canonical SHA256 `8346decbf2b2f8c1` vs storage `inbox_55868a49_9_IMG_1260`) cost time locating the photo across `photos` / `date_labels` (already Lesson 25/63).
- **"No-TTL cache" surprise**: the direct Supabase write didn't appear on the live site until the deploy restarted the app (Lesson 206). The website update was gated on a deploy I'd have done anyway, but it wasn't obvious up front.
- **Silent deferral caught late**: the GEDCOM-backfill follow-up wasn't logged to BACKLOG until the user explicitly asked "did we fix everything?" — now **ESTIMATE-BACKFILL-166** + **GEMINI-LOG-AUDIT-166**.
