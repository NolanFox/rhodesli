# W3 — Data-Integrity / Split-Brain Risk Audit

**Auditor**: Fable 5 subagent (read-only, fresh context)
**Scope**: identity/photo write paths (`app/main.py`, `app/supabase_data.py`, `app/upload_routes.py`, `core/registry.py`, `core/photo_registry.py`, `app/sync_routes.py`), invariant tests, architecture docs
**Date**: 2026-07-02
**Method**: pure code reading, line numbers verified by direct file reads. No tests run, no network.

---

## Verified defects (airtight code-path proof)

### VD-1 — `save_photo_registry` swallows Postgres write failure; upload cache-invalidation then serves stale data
- **Status**: active
- **Evidence**: `app/main.py:3302-3312` (strict write wrapped in `try/except` that only `logging.error`s and returns normally — no return value, no cache-TTL trick); contrast `save_registry` at `app/main.py:1837-1843` which at least returns `False` and extends TTL. `app/upload_routes.py:1368` sets `_main_mod._photo_registry_cache = None`, and `load_photo_registry` (`app/main.py:3256-3268`) then reloads **from Postgres only**.
- **Failure scenario**: Admin edits photo metadata (or ingest updates face_ids) → Supabase write fails (flake/timeout) → JSON backup has the change, Postgres does not, in-memory cache has it. Any subsequent cache invalidation (every upload does one) reloads from stale Postgres → the mutation silently vanishes. JSON is never read in postgres mode, so it's unrecoverable without manual intervention.
- **Why tests miss it**: `tests/test_data_parity_invariants.py:25-45` only asserts `save_photo_registry` *calls* the shadow-write functions; `tests/test_session105_split_brain.py:147-158` tests that strict raises inside `supabase_data`, but nothing asserts the *caller* surfaces or recovers from that raise. No test covers "write failed → cache invalidated → mutation gone."
- **Lessons**: 144, 150 (split-brain #7/#8), 136 (invisible write loss).

### VD-2 — `save_registry` failure return is ignored by ~29 of 30 callers; SWR refresh silently reverts the user's change after ≤600s
- **Status**: active (partially mitigated for merge only)
- **Evidence**: `app/main.py:1837-1843` returns `False` on Postgres failure and extends `_registry_cache_ts`. The **only** caller that checks is the merge path (`app/identity_routes.py:1611,1622` — `save_ok is False`). ~30 other `save_registry(` call sites in `app/main.py` + `app/identity_routes.py` alone ignore the return. `_background_registry_refresh` (`app/main.py:1622-1631`) unconditionally replaces `_registry_cache` with a fresh `load_from_postgres()` once the TTL lapses.
- **Failure scenario**: Admin confirms/renames/tags an identity → Supabase write fails → route returns success HTML (change visible from the in-memory cache) → 600s later the SWR background refresh reloads stale Postgres and the confirm/rename evaporates with zero user-visible error. This is exactly the FB-036/BUG-001 class the TTL-extension "fix" was meant to paper over — the extension only delays the revert by one TTL window.
- **Why tests miss it**: `tests/test_data_layer_invariants.py:141` (`test_save_registry_writes_to_postgres`) asserts the write happens on the happy path. No test simulates write-failure-then-TTL-expiry-then-refresh. Mocked Supabase clients never fail with the timing that matters.
- **Lessons**: 136, 150, 153 (silent write loss / split-brain), 151 (caching around failure states).

### VD-3 — `sync_relationships` is delete-all-then-insert with no transaction: mid-failure leaves the relationships table empty or partial
- **Status**: active
- **Evidence**: `app/supabase_data.py:189-216` — `delete().neq("id", …)` wipes the table (line 191), then inserts in batches of 200 (lines 210-213); the whole thing is wrapped in one `except Exception` that logs a warning (line 215-216). PostgREST calls are separate HTTP requests — no atomicity.
- **Failure scenario**: 1000+ relationships, delete succeeds, batch 3 of 6 fails → table left with ~40% of rows; caller sees nothing (warning log only). Next `sync_from_supabase_on_startup` (`app/supabase_data.py:314-345`) then faithfully rebuilds `relationships.json` from the truncated table — the loss propagates to the JSON "backup" on the next restart, destroying the recovery copy.
- **Why tests miss it**: `tests/test_supabase_data.py` mocks succeed atomically; there is no test injecting a failure between delete and insert. The `except: pass` structural guard (`tests/test_data_parity_invariants.py:75`) allows `except Exception: log` — which is exactly this pattern.
- **Lessons**: 199 (non-atomic multi-step import = failure leaves wrong row set), 136.

### VD-4 — Optimistic-concurrency + name protection silently disabled when the prefetch flakes
- **Status**: active
- **Evidence**: `app/supabase_data.py:858-859` — if the `identities` prefetch fails: `logger.warning("DATA-020 name prefetch failed (proceeding without protection)")`, leaving `postgres_versions`/`postgres_names` empty. Then line 874 `pg_version = postgres_versions.get(identity_id, 0)` → version check never skips; line 892 name protection never fires.
- **Failure scenario**: Bulk write (e.g., upload pipeline's full-registry upsert, `app/upload_routes.py:1316-1317`) races a concurrent merge during a Supabase flake window → the stale batch overwrites the merge result — precisely the Session 132 bug this code was added to prevent, re-enabled during exactly the degraded conditions when stale writes are most likely.
- **Why tests miss it**: Session 132 tests verify the skip logic *when the prefetch succeeds*. No test asserts behavior when the prefetch itself raises (e.g., should it abort the batch instead of proceeding unprotected?).
- **Lessons**: 153 (9th split-brain: stale layer overwrites), 151 (never cache/continue through failure states that disable safety boundaries).

---

## Risk findings (ranked, likelihood × blast radius)

### R-1 — Upload pipeline Supabase sync is non-strict and fully swallowed; new photos invisible until restart
- **Status**: active
- **Evidence**: `app/upload_routes.py:1296-1317` — all shadow-write calls in `_background_ingest` omit `strict=True` (each failed sub-batch logs and continues, `app/supabase_data.py:775-778,938-941`); `app/upload_routes.py:1358-1361` catches everything: "Even if sync fails completely, the JSON files have the data. Startup orphan detection will catch and repair on restart."
- **Failure scenario**: Upload succeeds to JSON + R2, Supabase sync fails → production (DATA_SOURCE=postgres) never shows the photos; uploader sees success. The "repair on restart" backstop only fires on the next deploy — potentially weeks. This is a designed-in reopening of Lesson 144's exact window.
- **Why tests miss it**: `tests/test_data_parity_invariants.py:48` only asserts `_background_ingest` *calls* `shadow_write_photo_faces_batch` (source-grep, not behavior). No test asserts strictness or a retry/alert on failure.
- **Lessons**: 144 (the canonical DATA_SOURCE split-brain), 146.

### R-2 — Partial batch commits: strict mode raises AFTER earlier sub-batches already committed
- **Status**: active
- **Evidence**: `app/supabase_data.py:865-941` (`shadow_write_identities_batch` loops in batches of 100; a failure in batch N raises after batches 1..N-1 are upserted); same shape in `shadow_write_photos_batch` (753-778) and `shadow_write_photo_faces_batch` (812-821). `save_registry`'s "synchronous, failures visible" write (`app/main.py:1836`) therefore isn't all-or-nothing.
- **Failure scenario**: Bulk operation (flatten-merge-chains, recluster, resync) writes 3400 identities; failure at batch 20 leaves Postgres with a half-old/half-new identity graph — e.g., a merge target updated but its source's `merged_into` not written → the pre-Session-131 orphan class.
- **Why tests miss it**: split-brain tests assert raise/swallow semantics per call, never the partial-state left behind. Lesson 199's structural rule ("failed import = zero rows") was applied to the GEDCOM importer but not to these REST batch writers.
- **Lessons**: 199, 154, 145.

### R-3 — `/api/sync/resync-supabase` re-upserts the entire volume JSON over Postgres (the Lesson-206 "destructive" endpoint still exists)
- **Status**: active / user-gated (admin-only)
- **Evidence**: `app/sync_routes.py:564-640` — loads `identities.json` + `photo_index.json` from the volume and upserts ALL rows. JSON backup writes are best-effort background threads that can silently fail (`app/main.py:1810-1818`, "JSON backup write failed (non-critical)"). Version guard skips only `pg_version > incoming` (`app/supabase_data.py:874`), so equal-version content drift (e.g., a direct Supabase repair that didn't bump `version_id` — Lessons 170/206 territory) is overwritten.
- **Failure scenario**: Admin hits resync to fix a cache issue → any manual Supabase repair or any change whose JSON backup thread failed is reverted wholesale. `.claude/rules/multimodel-photo-estimate.md` already documents this endpoint as destructive — but the mitigation is documentation, not code.
- **Why tests miss it**: no test asserts resync refuses to downgrade content, and none can — the version field doesn't capture content identity.
- **Lessons**: 206, 153, 56/69/78 (deploy-overwrite family).

### R-4 — Ingest's full-registry JSON read races `save_registry`'s background JSON backup write
- **Status**: active (low likelihood, high blast radius)
- **Evidence**: `app/upload_routes.py:1274` and `1299` load `identities.json` mid-ingest (comment says they must, because new identities exist only in JSON); `app/main.py:1808-1820` writes the same file from a background thread on every admin save, from an in-memory registry that was loaded from Postgres and does NOT contain the not-yet-synced upload identities.
- **Failure scenario**: Admin confirms an identity while a background ingest is running → backup thread overwrites `identities.json` without the new upload identities → ingest (or the post-sync orphan check at 1326-1353) reads the clobbered file → new-face identities lost from both stores or spuriously recreated as duplicates.
- **Why tests miss it**: single-threaded tests; no concurrency test exercises ingest + save_registry interleaving.
- **Lessons**: 25/63 (dual ID/data spaces), 144, 155.

### R-5 — `photo_faces` sync is additive-only: stale face→photo rows are never pruned
- **Status**: active (bounded by "UI never deletes a face")
- **Evidence**: `app/supabase_data.py:782-821` — upsert only; no delete of rows absent from the incoming set. `PhotoRegistry.load_from_postgres` (`core/photo_registry.py:437-448`) rebuilds `face_to_photo` from ALL rows in the table.
- **Failure scenario**: A face detached/reassigned between photos, or a photo pruned (Session 105 reconciliation pruned 1 stale photo), leaves a `photo_faces` row pointing at the removed photo → phantom membership resurfaces in `face_to_photo` on every load; the exact "additive-only shadow sync is not reconciliation" pattern.
- **Why tests miss it**: `tests/test_data_integrity.py:169` checks `face_to_photo` points to valid photos in *local JSON data*, not against live Supabase rows; CI has no live table (Lesson 211-adjacent).
- **Lessons**: 123, 145.

### R-6 — No-TTL module-global caches make direct DB writes invisible until restart (and one cache never expires at all)
- **Status**: active, documented-but-unenforced
- **Evidence**: `_photo_registry_cache` has NO TTL (`app/main.py:3255-3268` — only `None` check; reset only via `_invalidate_all_caches`/restart); `_date_labels_cache` same shape (`app/main.py:2315-2344`). Lesson 206 documents this for date_labels; the photo registry has the same property.
- **Failure scenario**: Any out-of-band Supabase write (repair script, multimodel estimate, manual fix) is invisible on the live site; operator concludes the fix "didn't work" and re-runs something destructive (see R-3, or the in-app reanalyze that re-spends Gemini).
- **Why tests miss it**: cache-freshness is untestable with mocks that never diverge from the cache; no structural test asserts every module-global data cache has either a TTL or a documented invalidation owner.
- **Lessons**: 206, 111, 150.

### R-7 — Schema-drift filter for `gemini_api_calls` fails open on an empty table
- **Status**: active (minor)
- **Evidence**: `app/supabase_data.py:488-495` — column discovery reads `probe.data[0].keys()`; if the table has zero rows, `probe.data` is empty → returns `None` → caller inserts the unfiltered row (line 566-567 comment: "best-effort, original behavior"), reproducing the exact PGRST204 whole-row-drop the Session 166 fix addressed, precisely on a fresh/pruned table.
- **Why tests miss it**: Session 166 tests cover the drifted-column path with a populated probe; none covers an empty-table probe. (Could use PostgREST OpenAPI or `information_schema` instead of a data row.)
- **Lessons**: 105, 152, 205 (schema-drift family).

### R-8 — Annotations startup sync is merge-only: rows deleted in Supabase persist forever in the JSON cache
- **Status**: active (low severity — JSON is backup-only for most read paths, but annotations JSON is still read in fallbacks)
- **Evidence**: `app/supabase_data.py:290-312` — `ann_data.setdefault("annotations", {})[id] = data` merges Supabase rows INTO the existing file; never removes rows absent from Supabase (contrast: gedcom_matches at line 358 does a full replace of the list).
- **Failure scenario**: Annotation deleted/rejected in Supabase → deploy → JSON still carries it; any code path that falls back to the annotations JSON resurrects it.
- **Why tests miss it**: no reconciliation test for startup sync deletion semantics.
- **Lessons**: 123.

---

## Mitigated (credit where due — do not re-fix)
- **identity_overrides resurrection** (Lesson 153, 9th split-brain): structurally blocked by `tests/test_data_layer_invariants.py:23-104` and the Session 168 suite (29 anti-reintroduction guards, promoted out of `slow` into CI). **mitigated**.
- **Merge orphaned faces** (Lesson 154): post-merge verification + force-add in `core/registry.py:750-769`. **mitigated**.
- **JSONB string-encoded arrays** (Lesson 142): guarded on read (`core/registry.py` `_ensure_list`, ~1957) AND write (`app/supabase_data.py:671-686`), plus `tests/test_data_layer_invariants.py:181`. **mitigated**.
- **Silent `except: pass`** (Lesson 136): AST-based structural guard `tests/test_data_parity_invariants.py:75-107` — though note it deliberately permits `except Exception: log-and-continue`, which is the pattern behind VD-1/VD-3/R-1.
- **GEDCOM non-atomic importer** (Lesson 199): PRD-064 Option B-plus shipped Session 164 (single-transaction importer, `docs/prds/064_gedcom_history_storage_redesign.md`). **mitigated** for GEDCOM — but the same atomicity rule has NOT been applied to the REST batch writers (see R-2/VD-3).
- **Count-based parity check** (`tests/test_session105_split_brain.py:206-263`, `/health` parity): catches gross identity-count divergence at startup — but counts match under VD-2/VD-4-style *content* divergence, so it is early-warning only, not a guard.

---

## Stale-doc drift (docs contradicting current code)

| Doc | Stale claim | Reality |
|---|---|---|
| `docs/architecture/DATA_MODEL.md` | "All canonical data is stored in JSON files … There is no relational database for canonical data"; data-integrity rules center on `identities.json` atomic writes; stats from Feb 2026 (124 photos, 292 identities) | Supabase Postgres is the sole read source since Session 112 (PRD-051); JSON is write-only backup (`app/main.py:1652-1654,3248-3253`). 1127 photos / 1824 identities. **Highest-risk doc** — it is loaded into every session context and teaches the pre-split-brain-fix architecture. |
| `docs/architecture/OVERVIEW.md` | Diagram: "Layer 1: Canonical Data (Railway volume) identities.json / photo_index.json"; "Layer 2 (Community Annotations via Postgres) is planned but not yet implemented"; Phases C–F "NOT STARTED" | Postgres canonical; annotations/relationships/GEDCOM all live in Supabase; Phases C–E shipped long ago (ROADMAP shows C COMPLETE, E ~80%). |
| `docs/architecture/PHOTO_STORAGE.md` | "Dimensions must be cached in photo_index.json"; "photo_index.json is only modified during photo ingestion" | Dimensions come from the Supabase-backed photo registry (`app/main.py:3410-3436`); photo_index.json is rewritten as backup on every `save_photo_registry`. |
| `docs/architecture/PERMISSIONS.md` | "Upload photos: No/No/Yes (admin only)"; binary permission model | Contributor/logged-in uploads with auto-approve shipped Session 104; anonymous contributions tracked (Sessions 104/121). Matrix is materially wrong for uploads. |

**Classification**: all four are `stale-doc` — no code defect, but they actively mis-train every fresh session/agent toward JSON-canonical mental models, which is the root posture behind lessons 56/69/78/141 (re-adding production-origin JSON to sync paths).

---

## Top-3 structural recommendations (one line each)
1. Make **write-failure loud end-to-end**: `save_registry`/`save_photo_registry` failures must surface to the HTTP response (and Sentry), not just logs — VD-1/VD-2 are the live descendants of the #1 repeat-offender pattern.
2. Apply the **Lesson-199 atomicity rule to REST batch writers**: staged upsert + verify (or at minimum retry-with-abort-before-any-write), and abort `shadow_write_identities_batch` when the concurrency prefetch fails (VD-4) instead of proceeding unprotected.
3. Rewrite `DATA_MODEL.md`/`OVERVIEW.md` now — they are session-context inputs, and their JSON-canonical language is a standing prompt-injection toward the exact failure class this audit covers.
