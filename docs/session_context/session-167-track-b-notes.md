# Session 167 — Track B (Estimate v2 / PRD-055) — Notes & Open Decisions

**Branch:** `session-167/estimate-v2`
**Scope:** `app/estimate_routes.py` + its tests only (per coordinator course-correction).

## What shipped
- **Flow 1 — GEDCOM paste:** optional "Paste family tree info" textarea on
  `/tools/estimate`. A lightweight, library-free line parser
  (`_parse_gedcom_text_for_context`) extracts name + birth/death year + place
  from level-0 `INDI` records and injects them as Gemini `gedcom_context`.
  Results show a **"Family tree context"** badge. Invalid/empty paste → silent
  fallback to visual-only.
- **Flow 2 — text hints:** already shipped (S150); now routed through a unified
  `_build_estimate_user_context` with an explicit `enrichment_level` taxonomy.
- **Flow 3 — geography retry:** `POST /api/estimate/retry` reuses the stored
  upload (no re-upload), re-runs Gemini with the user location reconciled
  against visual evidence (`_geography_retry_context`), shows original vs
  revised side by side. `upload_id` is regex-validated; shares the per-IP rate
  limit.
- **Flow 4 — backward compat:** upload-only path unchanged; regression test
  asserts no badge / no `gedcom_context` when nothing extra is supplied.

## Decisions I resolved (flag for Nolan if you disagree)

1. **PASTE only, no `.ged` file upload.** PRD-055 lists file upload as OUT OF
   SCOPE; the coordinator confirmed paste-only. (An earlier draft had a `.ged`
   file field — removed.) If a `.ged` upload is wanted later, the parser already
   accepts raw GEDCOM text, so wiring an `UploadFile` → `.decode()` is a small
   follow-up.

2. **`enrichment_level` lives in the existing `gemini_config` JSONB, NOT new
   SQL columns.** PRD-055's data-model section proposed new
   `gemini_api_calls` columns (`user_context`, `retry_parent_id`,
   extended `enrichment_level`). Per the coordinator, no migration is applied
   this session, so logging stays backward-compatible: `enrichment_level` (one
   of `gedcom_user_provided` / `text_hints` / `geography_retry`) is recorded
   inside `gemini_config`. **OPEN:** if you want these queryable as top-level
   columns + a `retry_parent_id` link from retry→original, that's Track A's
   `GEMINI-API-CALLS-SCHEMA-166` migration + a one-line wiring here.

3. **Lightweight regex parser instead of `rhodesli_ml.importers.gedcom_parser`.**
   PRD-055 explicitly endorses a regex/line extractor for paste input. The full
   parser needs `python-gedcom` + a real file + heavy enrichment — overkill and
   slower for a public, untrusted paste box. Caps: 2 MB text, 60 individuals,
   6000-char context block.

4. **Retry steering is app-layer** (`gedcom_context=_geography_retry_context`),
   NOT a change to the shared `build_extraction_prompt` (Track D owns that). I
   also pass `photo_metadata['user_location']` so the feature auto-upgrades if
   Track D later teaches the prompt builder about `user_location`.

## Known limitations / follow-ups
- Retry depends on the upload still existing in `uploads/estimate/`. If R2/local
  cleanup removes it, the endpoint returns a friendly "no longer available"
  message (no crash). No TTL/cleanup policy was added.
- The combined-context label is "gedcom_user_provided" when BOTH GEDCOM and text
  hints are present (GEDCOM dominates). If you want a distinct `gedcom+hints`
  level, it's a one-liner.
