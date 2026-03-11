# Session 98 GEDCOM Research Notes

**Date:** 2026-03-11  
**Purpose:** document the external and internal sources that shaped Session 98

## Sources Reviewed

1. FamilySearch GEDCOM specification
   - https://gedcom.io/specifications/FamilySearchGEDCOMv7.html
   - Relevant sections used:
     - lines 255-256: cross-reference identifiers are unique within one document and are not retained between data streams
     - lines 268-272: pointers are encoded as xrefs to pointed-to structures
     - lines 111-114: GEDCOM is meant to represent individuals, families, events, sources, citations, and supporting documents
     - lines 1055-1063 and 1608-1614: source records, source citations, and multimedia links are first-class structures
     - lines 991-995: multimedia records can reference one or more external files

2. Session 97 lineage package
   - `/private/tmp/rhodesli-prd038-plan/docs/prds/038_longitudinal/PROMPT_AND_STATE_LINEAGE.md`
   - `/private/tmp/rhodesli-prd038-plan/docs/session_context/session-97-context.md`
   - `/private/tmp/rhodesli-prd038-plan/docs/ml/ALGORITHMIC_DECISIONS.md` (`AD-217`, `AD-218`)

3. Ancestry support pages
   - official support article titles were located via web search:
     - `Uploading and Downloading Tree Data`
     - `Why Can't I Merge My Family Trees?`
   - Direct fetches from this environment returned `403 Access denied`, so I treated the visible search-result summaries as weak confirmation only.

## What The Sources Mean For Session 98

### 1. GEDCOM xrefs are transport pointers, not stable product identities

The FamilySearch spec is explicit that cross-reference identifiers are unique
inside one document and are not retained between data streams. That means a
GEDCOM exporter can legitimately renumber records between exports even when the
human person or family did not disappear.

Session 98 consequence:
- do not treat `@I...@`, `@F...@`, `@S...@`, or `@O...@` as durable product ids
- preserve them exactly as imported
- add redirect / rekey handling for records that disappear between versions
- avoid showing raw xrefs as user-facing identifiers

### 2. Flattened person rows are not a faithful GEDCOM mirror

The spec treats sources, citations, multimedia links, notes, and family/event
substructures as core parts of the dataset, not optional decoration. The March
11 export also empirically confirmed that reality: the tree contains repeated
names, dense `SOUR` / `PAGE` / `DATA` provenance, `OBJE` references, and
Ancestry custom tags.

Session 98 consequence:
- mirror top-level `INDI`, `FAM`, `SOUR`, and `OBJE` records
- preserve raw record text and a structured raw node tree
- store names, notes, citations, media refs, custom tags, and rich event data
- keep a raw `gedcom_records` table even when the app consumes thinner views

### 3. Redirect lineage is required for non-destructive updates

Because xrefs are transient transport pointers, a removed row is not always a
true deletion. It can also be:
- a rekey to a new xref
- a merge into an existing person record
- a family rewire that changes `FAMC` / `FAMS` without changing the person

Session 98 consequence:
- add `gedcom_entity_redirects` as append-only lineage
- resolve `gedcom_face_links` through redirects instead of rewriting the link
- keep old rows for audit and rollback instead of destructive updates

### 4. Versioned GEDCOM context should be an explicit AI/ML input artifact

Session 97 requires:
- `prompt_manifests`
- compact prompt lineage on `gemini_api_calls`
- canonical state-event envelopes
- `ml_run_manifests` and assignment-event lineage

That aligns with GEDCOM best practice: the prompt should not silently read
"whatever GEDCOM happens to be current." It should know which GEDCOM source
version it consumed.

Session 98 consequence:
- the GEDCOM mirror schema keeps version metadata on imported rows
- the combined pipeline now hydrates richer current GEDCOM context
- next schema work should attach `gedcom_version_id` or equivalent GEDCOM
  manifest identity to Gemini / ML run lineage, not only raw `gedcom_context`
  text blobs

## Research-Driven Design Rules

1. Mirror first, canonicalize second.
2. Keep raw GEDCOM records because the exporter contains meaning outside the
   existing thin schema.
3. Treat xrefs as version-local references and model redirect lineage.
4. Keep source-specific mirrors separate from future canonical genealogy
   claims.
5. Make AI/ML lineage point to GEDCOM version/manifests explicitly so prompt
   analysis stays replayable.

## Open Follow-Up

The next schema layer after Session 98 should be a source-agnostic genealogy
claims model above the GEDCOM mirror. That is the right place for:
- multiple family trees
- chat-derived family facts
- conflict resolution across sources
- replayable acceptance / rejection / undo events compatible with Session 97
