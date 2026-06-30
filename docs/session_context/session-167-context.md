# Session 167 Context — Multi-Track Autonomous Feature Sprint

**Predecessor:** [session-166-context](session-166-codex-audit.md) / assessment `docs/assessments/session-166-assessment.md`
**Date:** 2026-06-30
**Mode:** implementation (parallel) — `.claude/parallel_session_active` set
**Type:** EXPERIMENT — maximize autonomous parallel throughput across 5 tracks using
Opus-as-architect/auditor + Codex-as-coder, all Codex-audited at track boundaries.

---

## Why this session exists

Sessions 158–164 were an 8-session infrastructure firefighting arc (Supabase
disk-IO + DB-size crises → GEDCOM storage redesign PRD-064). That arc is **closed**:
DB 244 MB (from 1.3 GB), site live (health 200), CI green, tree clean. Session 165
shipped person-scoped photo nav; 166 was a one-off multi-model estimate that
incidentally fixed 3 silent production bugs.

Feature work has been starved for ~8 sessions. The user wants to (a) make broad
progress across many starved feature areas at once, and (b) **stress-test how
autonomously the current models can run** a multi-track session where **Opus
orchestrates + audits and Codex writes code**, every track Codex-audited.

## Model-orchestration contract (user directive, 2026-06-30)

- **Opus = architect + orchestrator + auditor** (main thread + each track lead subagent).
- **Codex gpt-5.5 / xhigh = coding engine.** Track leads use `codex exec "<prompt>" </dev/null`
  (CLI v0.142.4 installed; NEVER `--full-auto` — stdin hangs, Lessons 152/153/155).
  Track leads may use Codex to generate/propose implementation, then review + integrate + test.
- **Every track Codex-audited at its boundary** — kick the audit off EARLY, not at the
  very end (fox-genealogy HARNESS_VALUE_LOG lesson: late audits don't finish before
  context fills). Save audit to `docs/session_context/session-167-<track>-codex-audit.md`
  with the provenance header (`.claude/rules/ai-tool-audit.md`).
- Subagents may spawn their own subagents / Codex sessions as needed.
- **Codex pin is 21 days stale** (>14-day rule). gpt-5.5 still latest per last check
  (2026-06-09); Track A refreshes the pin's `verified_date` (CLI now 0.142.4).

## Reference: the fox-genealogy Heft-site build (multi-model precedent)

`/Users/nolanfox/fox-genealogy/` built family-history site pages using an
Opus + Codex (+ Fable 5, now offline) combination. Key transferable lessons
(`docs/HARNESS_VALUE_LOG.md`): Codex audits at scope boundaries are HIGH ROI
(3–15 real findings each); launch Codex EARLY; verify in-flight audit output
(size + tail) before declaring it incomplete; never pipe Codex through `tail`.

---

## The 5 tracks

Routes are decomposed into per-feature modules (`app/<feature>_routes.py`), each
self-registering via `from app.main import rt` and imported once at the bottom of
`main.py` (lines 7991–8133). **Conflict surface is low** — tracks touch disjoint
files. Only shared file is `main.py` (1 import line for a NEW module) + the doc
files (ROADMAP/BACKLOG/CHANGELOG), which the orchestrator reconciles at merge.

### Track A — Ops hardening & tidy-up  (isolated: scripts/ + tests/ + harness)
- **GEDCOM-TEST-FIX** (P1): the BACKLOG cites `tests/test_gedcom_versioning.py:649`
  asserting rows SURVIVE a failed import. That file appears **replaced** by
  `tests/test_gedcom_atomic_import.py` in the 164 redesign — VERIFY first; the
  atomic importer should already assert zero-rows-on-failure. If already covered,
  mark NO-OP with proof; else add the inverted assertion.
- **OPS-002** (P1): `scripts/supabase_monitor.py` — checks `/health` `supabase`
  field + Management-API project `status`; alerts if `!= ACTIVE_HEALTHY` or
  `supabase != ok`; optional lightweight keep-alive query (prevent inactivity
  auto-pause). Wire a routine/cron design (don't enable unattended). Source OD-015, L200.
- **ESTIMATE-BACKFILL-166** (P2): **DRY-RUN SURVEY ONLY.** Identify GEDCOM-linked
  photos whose `date_labels` were computed visual-only in the ~2-month loader-outage
  window (Lesson 205). Produce a report + a ready-to-run batch script
  (`scripts/backfill_gedcom_estimates.py`). DO NOT write prod / spend Gemini $ unattended.
- **GEMINI-API-CALLS-SCHEMA-166** (P3): write the migration SQL adding the missing
  lineage columns to `gemini_api_calls` (do not apply unattended).
- **Codex pin refresh** (harness hygiene): bump `verified_date` in
  `.claude/rules/codex-model-pin.txt` (gpt-5.5 still latest; CLI 0.142.4).

### Track B — Estimate v2  (PRD-055; `app/estimate_routes.py` + `app/tools_routes.py` + tests)
Add to `/tools/estimate`: (1) optional **GEDCOM upload** (.ged) → parse → inject as
context into the Gemini prompt; (2) **text hints** field ("wedding in Rhodes, ~1930s");
(3) **geography retry** (re-prompt when location confidence low / candidate distance
high). Reuse the production enrichment path (`_build_gedcom_context_for_photo` shape).
Acceptance criteria in `docs/prds/055_estimate_v2.md`. e2e (`tests/e2e/`) + unit tests.
Stretch if early: PRD037-003 cost-estimate UI element.

### Track C — Self-service archive / "Create Your Archive"  (PRD-060; NEW `app/onboarding_routes.py`)
Build the well-specified PRD-060 flow: a `/create-archive` (or per PRD) landing +
form that lets a community start its own archive (name, description, first upload
entrypoint). Isolate in a new route module + 1 import line in `main.py`. **FLAG**
(do not silently decide) anything touching auth/permission write paths or
`identities`/community write tables — leave a `DECISIONS-FOR-NOLAN.md` in the track
worktree. Tests for the new routes. Ties to WORKSPACE-001 (personal archive auto-create, already shipped).

### Track D — Gemini Detroit prompt fix  (ML/prompt + eval harness; PROMPT-A-ITERATION-001 / PRD-LOCATION-001)
The date/location prompt mispredicts NYC for Detroit photos 02068 + 01659 even WITH
GEDCOM context; the AD-242 sycophancy guard raised confidence on the wrong answer
(L174). Implement **Path A**: a Round-2.5 step forcing Gemini to compute
GEDCOM-residence-date-distance per candidate location BEFORE naming a primary.
Build/extend the eval harness; run a **bounded** eval (the 2 Detroit photos, hard
~$0.50 cap). Document pass/fail in `docs/feedback/session-167-detroit-eval.md`.
User mandate: "keep trying until we replicate it with Gemini."

### Track E — rhodes-wiki RHODES-WIKI-004  (sibling repo `/Users/nolanfox/rhodes-wiki/`)
Dossier auto-update from approved posts (when a post is approved, append photo refs
to each linked `people/<family>/<person>.md` `photos:` field) + first `wiki/`
Karpathy-style narrative pages on top of the canonical vault (link-down rule +
disclosure-stamp footer). Advance the FB-ingest pipeline (manual Chrome-nav capture,
NO automated scraping — the design that avoids tripping FB bot detection; Lessons
191–197). rhodes-wiki is a SEPARATE git repo — work there directly, never write to
rhodesli (cross-repo invariant). Its own tests + Codex audit.

---

## Guardrails (apply to every track)

1. Worktree isolation (rhodesli tracks) or sibling repo (Track E). Commit to the
   track branch only — `.claude/parallel_session_active` blocks main commits.
2. Use RELATIVE paths in the worktree (Lesson 180 — absolute paths leak to main repo).
3. `source /Users/nolanfox/rhodesli/venv/bin/activate` then run tests from the
   worktree cwd. Verify one test imports the WORKTREE's `app/` (not main) before trusting results.
4. Every change gets tests (happy + failure + regression). `make test-fast` green before each commit.
5. NO production data writes, NO Gemini/$ spend, NO browser action-clicks unattended.
   Anything irreversible or outward-facing → STOP and flag for Nolan.
6. Codex audit at track boundary, kicked off early; provenance header; saved to
   `docs/session_context/session-167-<track>-codex-audit.md`.
7. On budget exhaustion: stop honestly and report partial state + a resume note (Lesson 182).
8. Each track returns: branch name, commits, tests added/passing, Codex-audit verdict,
   open decisions for Nolan, and a one-paragraph "what shipped / what's left."

## Deferred / not in scope this session
- WORKSPACE-002–006 (depend on cross-cutting permission work), Multi-GEDCOM merge,
  ENV-001/OBS-001 env split, COMMUNITY-002 switcher — fold-in candidates for a
  follow-up once these 5 land. COMMUNITY-004 (shared-person indicator) is a Track B/C
  stretch if time allows.

## Post-session planning
Candidate next session: merge + browser-verify all tracks live; pick up WORKSPACE
sharing-mode arc; run the ESTIMATE-BACKFILL-166 batch (with user $ approval).
