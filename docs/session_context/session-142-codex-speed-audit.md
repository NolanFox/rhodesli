# Session 142 — Codex Speed Audit: Batch Gemini GEDCOM Performance

**Auditor**: Codex CLI v0.115.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: `scripts/batch_gemini_for_person.py` + `app/estimate_routes.py` — batch Gemini API call performance
**Date**: 2026-03-27
**Status**: RESEARCH ONLY — no code changes made

---

## Core Problem

The batch path rebuilds GEDCOM state per photo instead of per run. `_build_gedcom_context_for_photo()` calls `load_gedcom_data()` for every photo (estimate_routes.py:1144), and that loader paginates full GEDCOM tables and reconstructs `ParsedGedcom` from scratch (run_combined_pipeline.py:191, 244, 281). With 15,000+ individuals, the current shape is `O(photo_count * full_gedcom_load)`.

**Already cached** (not the bottleneck):
- `_load_gedcom_face_links()` has TTL cache (relationship_routes.py:390)
- `load_registry()` is cached/SWR (main.py:1640)
- `_build_caches()` fast-paths after first call (main.py:4521)

---

## P0 — Critical (60-90s per photo eliminated)

1. **Load GEDCOM once per batch and inject it.** Preload `gedcom_data = load_gedcom_data()` once before the batch loop and pass it into the context builder, instead of calling `load_gedcom_data()` inside `_build_gedcom_context_for_photo()` on every photo (estimate_routes.py:1144). Changes hot path from repeated full Supabase scans to one load plus cheap per-photo joins.

2. **Current batch cache is useless.** The script's `_gedcom_cache` is keyed by `photo_id` (batch_gemini_for_person.py:299), but each photo is processed once in the loop (line 515), so this cache never hits. The comment "load once per unique set of identified faces" (line 296) is inaccurate.

3. **Make `_build_gedcom_context_for_photo()` batch-aware.** Add optional injected deps: `gedcom_data`, `registry`, and a precomputed `face_id -> identity` map. Currently written for one-off admin use, then reused in batch without a batch-friendly API (estimate_routes.py:1091).

4. **Cache key should be identity set, not photo_id.** `build_gedcom_context(..., variant="first_order")` (run_combined_pipeline.py:167) doesn't use `photo_id` meaningfully — photos with the same identified people can reuse the same context string. Key by sorted linked `identity_id` or GEDCOM xref set.

---

## P1 — High (additional per-photo overhead)

1. **Precompute batch-friendly GEDCOM context builder.** `build_photo_context()` loops faces and calls `_find_identity_for_face()` (gedcom_context.py:126), which scans all identities each time (gedcom_context.py:355). For batch, build once: `face_id -> identity_id`, `identity_id -> gedcom_xref`, `gedcom_xref -> pre-rendered summary`.

2. **Pre-render per-person first-order summaries once.** `_build_person_context()` and `_build_family_context()` are deterministic string builders (gedcom_context.py:168, 244). Amortize across batch, not per photo.

3. **Deduplicate prompt context.** `build_photo_context()` appends one section per face, not per unique identity (gedcom_context.py:126). Same person via multiple face IDs duplicates family context. Dedup by `identity_id`, dedup relatives across sections, cap total context tokens.

4. **Add compact batch variant.** Current `first_order` context includes parents, spouses, siblings, children, many events. For date/location estimation, a compact summary (birth/death, residence history, key occupation, spouse/children summary) reduces Gemini latency and cost.

---

## P2 — Medium (secondary bottlenecks)

1. **Reuse single Gemini client.** `_call_gemini_full()` constructs new `genai.Client` per photo (batch_gemini_for_person.py:367). Reusing one client per run reduces connection/setup overhead.

2. **Make logging cheaper.** `log_gemini_call()` is synchronous blocking insert (supabase_data.py:534). Batch sends `prompt_text`, `full_response`, `gedcom_context` every call (lines 493-496). Options: hash-based manifest IDs, buffer inserts, full prompt only on failures.

3. **Avoid full-table photo_faces scan.** `get_photos_for_identities()` paginates entire `photo_faces` table (batch_gemini_for_person.py:110). Since target `face_ids` are known, query only those in chunks.

4. **Consider limited concurrency.** Batch loop is strictly serial with sleep between photos (lines 515, 634). After P0/P1 fixes, a small worker pool with quota-aware throttling would improve wall-clock time.

5. **Latent OCR issue.** `find_business_owner_context()` scans every GEDCOM individual (gedcom_context.py:59). Not on current batch path (no `visible_text` passed, line 302), but should use name index if enabled later.

---

## P3 — Low (cleanup)

1. **Reduce INFO log volume.** Per-face INFO logging (estimate_routes.py:1131) is noisy in batch runs.

2. **Warm all caches at batch start.** `_build_caches()`, `load_registry()`, `_load_gedcom_face_links()`, and GEDCOM preload — do once for predictability.

3. **Minor duplicate loads.** Script reads `date_labels.json` twice (lines 166, 503), loads `embeddings.npy` up front (line 281). Small compared to GEDCOM loads.

4. **Unused import.** `build_prompt_lineage_fields` imported but unused (line 272).

---

## Recommended Implementation Order

1. Add process-wide GEDCOM preload + inject into `_build_gedcom_context_for_photo()` (P0)
2. Precompute face/identity/xref maps and compact per-person summaries (P1)
3. Make logging lighter or buffered (P2)
4. Consider concurrency and smaller cleanups (P2/P3)

## Expected Impact

- **P0 alone**: Eliminates ~60-90s per photo of redundant Supabase loading. For 67 photos, saves ~67-100 minutes.
- **P0 + P1**: Additional savings from amortized context building. Per-photo GEDCOM work drops to milliseconds.
- **P0 + P1 + P2**: Logging and client reuse save ~1-2s per photo additional.

---

*This was static analysis only; no live profiling or Supabase-backed timing tests were run.*
