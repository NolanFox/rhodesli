# Session 144 Assessment

## Shipped
- [x] Phase 0: GEDCOM v9 import — 21,998 individuals, 107 face links, Albert's 3 wives linked
  - Evidence: Direct DB query confirms 21,998 current individuals, 6,741 families
  - Import script hardened: datetime serialization, non-fatal change log, error handler
- [x] Phase 1: GEDCOM context enrichment (AD-234)
  - Evidence: 7 new tests pass for spouse timeline, birth annotation, confirmed block
  - Albert's context now includes chronological spouse timeline with photo dating constraints
- [x] Phase 2: Geographic data model expansion
  - Evidence: 2 new tests for location candidates rendering
  - Gemini prompt updated to request structured location with candidates
- [x] Phase 3: Batch re-run preparation
  - Evidence: Read-merge-write semantics implemented, batch plan documented
  - Actual API calls deferred to manual execution (355 photos, exceeds daily quota)
- [x] Phase 4: Anchor comparison prototype (AD-233)
  - Evidence: 4 new tests for anchor comparison prompt builder
  - Prompt generates structured output for multi-image aging comparison
- [x] FB-001: GEDCOM search location clarity — FIXED
- [x] FB-002: Face analysis person names — FIXED
- [x] FB-003: Gemini anchor research logged with 6 feature ideas
- [x] Lessons 163-164 documented

## Gaps (from prompt review)
- Phase 1c `verified_facts` parameter: Not wired as explicit parameter. Instead, confirmed
  identities block is built from existing `identified_faces` + `identities` args. Functionally
  equivalent but doesn't add a new parameter name. ACCEPTABLE — the block works.
- Phase 2 map view update: Map pins still use `photo_locations` table. New `location_primary`
  schema only affects date_labels. Geocoding step needed to populate lat/lng.
- Phase 4 Admin UI button: Prompt builder exists but no "Compare with anchor" button on
  photo page. This needs a route handler + UI element. BACKLOG: ANCHOR-UI-001.

## Deferred
- Batch re-run execution: 355 photos need GEDCOM context. Exceeds 250 RPD daily limit.
  Plan documented in `docs/session_context/session-144-batch-plan.md`. Not a BACKLOG item —
  operational, to be run manually.
- GEDCOM importer architectural rework: 175K+ rows cause OOM/timeout. Lesson 163.
  This IS a BACKLOG item: GEDCOM-ARCH-001.
- Dual-write to photo_locations table: Geocoding step needed after batch completes.

## Red Flags
- [medium] GEDCOM importer took 30+ min and crashed on change_log write. Fixed with
  non-fatal wrapper but root cause (175K rows, 700K change_log entries) needs architectural
  rework. Change log could be limited to added/removed only.
- [low] Face analysis name mapping only works for single-face photos. Multi-face needs
  bbox-based matching (face_index is left-to-right, face_ids are lexically sorted).
- [low] 355 photos still lack GEDCOM context from previous batch runs.

## AI Tool Usage
- **Tool**: Codex CLI v0.117.0
- **Agent type**: Independent (fresh context)
- **Task**: Security + code quality audit of Phase 0 changes
- **Findings**: 4 P1, 1 P2, 1 P3 — ALL fixed
- **Value assessment**: STRONG — caught cache key mismatch and datetime serialization gap
  that would have caused silent failures in production

## Next Session Should Verify
1. Run canary batch (3 photos) to validate enriched Gemini output quality
2. Verify spouse timeline appears in Gemini context for Albert/Esther photos
3. Check production photo pages for face analysis person names
4. Run remaining 355 photos over 2 days (250 RPD limit)

## Test Stats
- 3946 app tests pass (13 new)
- 35 GEDCOM context tests pass (7 new)
- 22 multi_pass tests pass (4 new)
