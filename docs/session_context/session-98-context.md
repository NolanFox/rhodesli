# Session 98 Context — GEDCOM Mirror, Diff, And UX Audit

**Prepared:** 2026-03-11
**Prepared by:** Codex
**Worktree:** `/private/tmp/rhodesli-session-98-gedcom`
**Branch:** `codex-session-98-gedcom`
**Status:** In progress

## Why This Is Session 98

Session 97 already exists as the PRD-038 longitudinal planning package with
live breadcrumbs and review artifacts. Renumbering that package would create
avoidably risky harness churn. This GEDCOM hardening effort is therefore
Session 98 and must remain compatible with Session 97 lineage requirements.

## User Requirements Captured

1. Update GEDCOM handling locally, on the web, and in Supabase without
   interfering with Session 96 work on `main` or the existing Session 97
   planning worktree.
2. Treat the Ancestry export as a mirror target: nothing in the GEDCOM should
   be silently lost.
3. Track everything that changed version over version, including merges,
   relationship changes, preferred date/place changes, and new facts.
4. Keep all data work non-destructive and auditable until Claude reviews it.
5. Preserve clear provenance in harness artifacts because Claude Code will
   audit the work.
6. Make the resulting data usable by app UX and by future AI/ML pipelines.
7. Stay compliant with Session 97 lineage requirements:
   `prompt_manifests`, enriched `gemini_api_calls`, canonical state events,
   `ml_run_manifests`, and assignment events.
8. Think ahead to multiple family trees and non-GEDCOM family knowledge
   sources without painting the schema into a corner.

## Hard Constraints

1. No destructive data operations.
2. If any data-affecting step is eventually executed, checked-in backup and
   diff artifacts must exist first.
3. Prefer dry-run and preview flows before apply flows.
4. Session 96 on `main` must remain untouched.
5. Session 97 artifacts must keep their existing numbering and references.

## Current Repo Findings

1. The current parser preserves only a subset of the export:
   primary name, sex, birth/death, a few event tags, family links, and one
   marriage event.
2. The versioned importer in `scripts/import_gedcom_version.py` currently
   focuses mainly on individual rows and field diffs.
3. Legacy sync paths still perform destructive relationship replacement.
4. The family-tree UI still relies on `data/relationships.json`, not directly
   on versioned GEDCOM relationship state.
5. Session 97 already defines the desired lineage direction for prompts and
   canonical state mutations.

## Raw GEDCOM Audit Baseline

Source files:
- `~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
- `~/Downloads/gedcom_20260311/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`

New export high-level counts:
- `21,944` `INDI` records
- `6,722` `FAM` records
- `803` top-level `SOUR` records
- `668` top-level `OBJE` records

Notable tags present in the new export that the current parser does not
preserve well enough:
- repeated `NAME` records
- `NOTE` with `CONT` / `CONC`
- dense `SOUR` / `PAGE` / `DATA` / `WWW` provenance
- `OBJE` media links and crop metadata
- Ancestry custom tags such as `_APID`, `_MTTAG`, `_WLNK`
- generic `EVEN` records with semantic meaning in `TYPE`
- additional fact tags like `DIV`, `NATU`, `BAPM`, and others

## Initial Diff Signal

Using the current parser only:
- old: `21,836` individuals / `6,688` families
- new: `21,944` individuals / `6,722` families
- same-xref individual modifications observed: `66`
- added individual xrefs observed: `119`
- removed individual xrefs observed: `11`

This undercounts true semantic change because the parser currently drops large
portions of the GEDCOM structure.

## Read Order For Implementation

1. `AGENTS.md`
2. `docs/AGENT_HARNESS.md`
3. `docs/session_context/session-98-context.md`
4. `docs/prds/038_longitudinal/PROMPT_AND_STATE_LINEAGE.md`
5. `docs/prds/038_longitudinal/LINEAGE_AND_REPLAY.md`
6. `rhodesli_ml/importers/gedcom_parser.py`
7. `scripts/import_gedcom_version.py`
8. `app/admin_routes.py`
9. `app/relationship_routes.py`
10. `tests/test_gedcom_versioning.py`
11. `tests/test_gedcom_admin.py`
12. `rhodesli_ml/tests/test_gedcom_parser.py`

## Required Outputs

1. Session 98 harness artifacts with reproducible commands.
2. A parser/import path that preserves full GEDCOM record content.
3. A non-destructive diff report between the February 24 and March 11 exports.
4. Schema changes that preserve raw records and support future scalable use.
5. UX changes or preview surfaces that make the richer GEDCOM usable in-app.
6. Tests for merges, relationship edits, preferred fact changes, and deleted
   facts.
7. A Session 98 assessment file before closeout.

## Current Implementation Status

Session 98 now includes:
- rich GEDCOM parsing for raw records, sources, media, names, citations, and
  custom tags
- snapshot/diff tooling for individuals, events, families, sources, media,
  relationships, and raw records
- redirect lineage for removed or rekeyed GEDCOM people
- admin preview updates, tree overlay updates, and richer ML-context hydration
- a migration package that remains additive and non-destructive

Still required before final closeout:
- final merge choreography after Sessions 96 and 97
- explicit note of whether live Supabase mutation was or was not executed
- if live schema mutation remains blocked, preserve the checked-in preflight
  artifact explaining why
