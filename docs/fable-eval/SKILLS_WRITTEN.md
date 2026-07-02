# W7 — Reusable Skills Distilled for Opus 4.8

**Goal:** hand Opus 4.8 this project's hard-won judgment before Fable becomes pay-per-use.
**Process:** drafted under `docs/fable-eval/skill-drafts/<name>/SKILL.md` → fresh-context verifier
subagent gate (`subagents/w7-skill-verification.md`) → applied required accuracy edits → copied to
`.claude/skills/<name>/SKILL.md`. **No existing skills edited.** All three verified and installed.

## The 3 installed skills

### 1. `split-brain-data-audit` (86 lines)
- **Prevents:** rhodesli's #1 recurring bug class — write-path/read-path data divergence
  (10+ occurrences: Lessons 56→69→78→85→141→144→147→150→153→154). Costliest real incidents it
  encodes: `identity_overrides` stale-snapshot overwrite (36 faces lost, 4 days), merge orphaning
  175 faces, ingest-writes-JSON-while-prod-reads-Postgres blackout.
- **Triggers:** any save/load path, batch script the app reads, data repair/un-merge/backfill,
  new Supabase table read, new field on an in-memory dict. **Not for:** UI/docs-only work.
- **Gates:** `pytest tests/test_data_layer_invariants.py`; merge suite; grep for new `except: pass`;
  round-trip write→app-loader→assert; production page verify; per-step snapshot + restore for repairs.
- Verifier verdict: APPROVE-WITH-EDITS → E1 applied (Session-112/PRD-051 vs AD-232/Session-143
  attribution corrected). Usability: **USABLE-WITHOUT-AUTHOR** against a held-out "favorite photos" task.

### 2. `supabase-migration-safety` (92 lines)
- **Prevents:** the Sessions 154–164 GEDCOM saga — a non-atomic per-batch-commit importer bloated
  the DB to 1.3 GB and took the site down (Lessons 199/200); plus cutover pooler failures (183),
  zombie backends (184), terminate-cascade (185), PGRST002 disk-IO (187), the `OR IS NULL`
  partial-index defeat that ate 73.9% of disk reads (198).
- **Triggers:** any bulk import/backfill/migration/cutover, ≥50K-row reads, new partial index,
  pooler/PGRST debugging. **Not for:** single-row app writes, JSON work.
- **Gates:** independent-model audit of the ACTUAL script before any prod run (treat BLOCK as hard
  stop — this caught a lossy diff-base + executable KeyError in Session 164); dry-run; failed-import-
  leaves-zero-rows structural test; proven rollback; post-run SQL + page verify.
- Verifier verdict: APPROVE-WITH-EDITS → E2 applied (lesson→topic-file mapping corrected;
  198–201 live only in the `tasks/lessons.md` index).

### 3. `route-safety-audit` (84 lines)
- **Prevents:** permission regressions (Lesson 15, the project's most dangerous UI bug), the 80+
  community-prefix gaps (Session 111), cross-community leak from caching a `None` scope (151), the
  Session-90b→140 total auth outage from dropped re-exports, and the HTMX-303-redirect auth trap (11).
- **Triggers:** adding/modifying any route (esp. POST), refactoring route modules, touching
  auth/CommunityMiddleware, periodic security sweeps. **Not for:** ML pipeline / no-HTTP scripts.
- **Gates:** `pytest tests/test_permissions.py tests/test_route_permissions.py tests/test_community_prefix_audit.py`;
  grep every new POST handler for an auth/origin guard; no `RedirectResponse` from HTMX auth guards;
  re-export check on refactors.
- Verifier verdict: APPROVE-WITH-EDITS → E3 applied (`_check_admin`/`_check_login` live in
  `app/main.py`, not `app/auth.py`; `_check_origin` at `app/auth.py:245` was correct) + E4 grep caveat.

## Why these three (and not others considered)
The brief listed candidates: split-brain audit, upload-pipeline verifier, route-safety audit,
live-UX vision audit, supabase-migration safety. Chosen by **incident density × recurrence × cost
of a repeat**. Split-brain (10+ occurrences) and route-safety (regression = data corruption or auth
outage) are the two highest-recurrence classes; supabase-migration-safety encodes the single most
expensive incident (site down, DB bloat). An "upload-pipeline verifier" was folded INTO
split-brain-data-audit (invariants 2/5/7 + the post-sync verification gate) rather than shipped
separately — its scar tissue (Lessons 144/145/146) is the same class and a 4th skill would dilute.
A "live-UX vision audit" skill was omitted: it is a workflow this eval performed, not project
judgment an everyday coding model needs loaded on most tasks — it belongs in the `fable-full-eval`
periodic-eval skill, not a per-session skill.

## Safety ledger for W7
- Files created: 3 draft dirs under `docs/fable-eval/skill-drafts/`, 3 installed dirs under
  `.claude/skills/`, this file, `PORTABLE_SKILLS.md`, `subagents/w7-skill-verification.md`.
- No existing skill, rule, or setting edited. No reasoning-extraction language (verifier grep: 0 hits).
  No permission expansion (all three ADD user gates). No excluded-file edits directed. Not committed.
