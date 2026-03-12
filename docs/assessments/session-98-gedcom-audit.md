# Session 98 GEDCOM Audit

**Date:** 2026-03-11  
**Worktree:** `/private/tmp/rhodesli-session-98-gedcom`  
**Primary artifact:** `docs/assessments/session-98-gedcom-diff-report.json`

## Scope

Compared:
- `~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
- `~/Downloads/gedcom_20260311/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`

Audit goals:
- verify that Session 98 preserves the full exported GEDCOM shape
- identify what actually changed between exports
- separate semantic change from parser/noise artifacts
- confirm the import path remains non-destructive and Claude-auditable

## Raw Export Counts

| Entity | 2026-02-24 | 2026-03-11 | Delta |
| --- | ---: | ---: | ---: |
| Individuals | 21,836 | 21,944 | +108 |
| Families | 6,688 | 6,722 | +34 |
| Events | 41,253 | 41,526 | +273 |
| Relationships | 145,804 | 146,592 | +788 |
| Sources | 790 | 803 | +13 |
| Media objects | 655 | 668 | +13 |
| Top-level records | 29,986 | 30,154 | +168 |

## What Changed

Normalized diff summary:

| Entity | Added | Modified | Removed | Unchanged |
| --- | ---: | ---: | ---: | ---: |
| Individuals | 119 | 21,604 | 11 | 221 |
| Families | 34 | 6,591 | 0 | 97 |
| Events | 286 | 718 | 13 | 40,522 |
| Relationships | 144,962 | 0 | 144,174 | 1,630 |
| Sources | 13 | 0 | 0 | 790 |
| Media objects | 13 | 655 | 0 | 0 |
| Raw records | 180 | 28,851 | 12 | 1,123 |

Important interpretation:
- The individual count looks enormous because Ancestry rewired family xrefs and many records embed those xrefs directly.
- After stripping parser `line_number` noise, only `311` individuals show direct person-fact edits and `473` show citation/media-reference edits.
- Event-level semantic churn is much smaller than the raw record churn: `718` modified events versus `40,522` unchanged.
- The raw-record mirror is doing its job: if Ancestry changed the record text, Session 98 can preserve and diff it even when the app-level person summary did not change much.

## Individual Change Breakdown

From the normalized report:

| Bucket | Individuals touched |
| --- | ---: |
| Relationship references (`FAMC` / `FAMS` shifts) | 21,600 |
| Citation or media-object reference shifts | 473 |
| Direct person-fact changes | 311 |
| Raw-record changes | 21,604 |

High-signal top paths:
- `family_as_child_json[0]`
- `family_as_spouse_json[0]`
- `media_refs_json[0].object_xref`
- event `place` / `raw_date` deltas in a smaller subset

This is why the mirror must keep both:
- structured person/family/event fields for UX and ML
- raw GEDCOM records for full-fidelity provenance

## Redirect / Merge Findings

Detected `6` high-confidence removed-to-current redirects. These are cases where a historical GEDCOM xref disappeared but the person still clearly exists under another current xref.

Examples from the report:
- `@I132227837001@ -> @I132492569691@` (`merge_redirect`)
- `@I132293732201@ -> @I132538456563@` (`merge_redirect`)
- `@I132513647807@ -> @I132778153288@` (`rekey_redirect`)

Session 98 now stores these redirects append-only and resolves face links through them without mutating the original `gedcom_face_links` rows.

## Import Safety Findings

Two importer issues were found and fixed during this audit:

1. Raw-node `line_number` metadata was inflating diffs.
   - Fixed by recursively stripping `line_number` from snapshot raw-node payloads.

2. Versioned writes were incompatible with `current` uniqueness.
   - The importer used to insert new current rows before retiring old current rows.
   - Session 98 now stages inserts as `is_current = false`, supersedes old rows, then activates the new rows.
   - The first versioned bootstrap now also retires all legacy current GEDCOM rows, not just modified ones.

## Live Supabase Execution

Recorded in `docs/assessments/session-98-supabase-preimport-state.json`.
Final applied state recorded in
`docs/assessments/session-98-supabase-postimport-state.json`.

Live state before Session 98 migration/import:
- `gedcom_versions`: `0`
- `gedcom_individuals`: `21,809`
- `gedcom_events`: `40,140`
- `gedcom_relationships`: `145,574`
- `gedcom_face_links`: `67`

Final live dry-run against the March 11 GEDCOM:
- individuals: `147` added, `1,428` modified, `12` removed, `20,369` unchanged
- events: `41,526` added
- families: `6,722` added
- relationships: `144,962` added, `143,944` removed, `1,630` unchanged
- sources: `803` added
- media objects: `668` added
- records: `30,154` added

Live apply was executed successfully as GEDCOM version `7`
(`05ffeee9-4ae2-4d97-aaaa-fa8a45fb1ca7`).

Current live mirror counts:
- `21,944` current individuals
- `41,526` current events
- `146,592` current relationships
- `6,722` current families
- `803` current sources
- `668` current media objects
- `30,154` current raw records

Operational notes from the live rollout:
- failed versions `1` through `6` were kept as audit history instead of being
  deleted
- existing `gedcom_face_links` were verified after apply and `0` are unresolved
  against current GEDCOM individuals
- `gedcom_entity_redirects` is currently empty in production because no live
  linked GEDCOM id required redirect repair after the bootstrap import
- the importer was still hardened after apply so future first-time bootstraps
  can emit redirect lineage when conservative matching finds a safe rekey/merge
- the first post-import deploy failed because the Railway image omitted runtime
  `rhodesli_ml` modules; this was fixed by shipping the full package surface in
  commit `7e4046e`, after which Railway deployment
  `2dbb0a2f-3373-4929-b3df-552134710c9d` passed health checks
- production startup also exposed a legacy `audit_log` schema without
  `target_type`; Session 98 added a shape-filter fallback so identity-history
  sync remains available until that column is standardized everywhere

## UX / ML Outcome

Session 98 now makes the richer GEDCOM usable in three places:
- Admin GEDCOM preview shows per-entity diffs, sample changes, and detected redirects before any apply.
- Tree rendering prefers current Supabase GEDCOM relationships, with `data/relationships.json` treated as a manual overlay.
- The combined Gemini pipeline hydrates the richer Supabase GEDCOM mirror and resolves redirected GEDCOM ids before building prompt context.

## Scalable Schema Direction

What Session 98 implements now:
- append-only GEDCOM versions
- current-state views
- raw record mirror tables
- redirect lineage for retired xrefs

What this sets up next:
- multiple GEDCOM trees or future chat-derived facts can coexist more safely if they land as source-specific records first
- Session 97 lineage tables should treat GEDCOM context as a versioned input artifact, not an implicit live read
- the next structural step after Session 98 is a canonical genealogy claims layer above source mirrors, not replacing them

## Current Recommendation

Session 98 is now a deployed non-destructive GEDCOM mirror foundation:
- parser and importer preserve the full export shape
- redirects handle removed/rekeyed GEDCOM ids more safely
- the admin/web/ML surfaces can consume the richer mirror
- the audit artifact now distinguishes real change from parser noise
- live data remained append-only during failed attempts and the applied version
  is fully traceable

Future live GEDCOM mutation should continue to happen only through the versioned
import path, with tree/source manifests added before multi-tree ingestion.
