# W3 — Data-Integrity / Split-Brain Risk Audit

**Synthesis of** `subagents/w3-data-integrity.md` (full file:line evidence there). Read-only code
review; no tests run, no network. rhodesli's #1 recurring bug class is write-path/read-path data
divergence (10+ documented occurrences). This audit connects that history to **current** code.

## Headline
The costliest historical incidents are **structurally mitigated** (identity_overrides resurrection,
merge orphans, JSONB string-arrays, GEDCOM non-atomic import). But the **same failure family is
alive** in the REST batch-write layer: write failures are logged-and-swallowed, then a cache
invalidation or SWR refresh reloads stale Postgres and the user's change silently reverts. Four
verified defects + eight risk findings below.

## Risk table (ranked by likelihood × blast radius)

| ID | Class | Status | Evidence (file:line) | Failure in one line | Lesson |
|----|-------|--------|----------------------|---------------------|--------|
| VD-1 | Verified | **active** | `app/main.py:3302-3312` vs `1837-1843`; `app/upload_routes.py:1368` | `save_photo_registry` swallows Postgres failure → next cache invalidation reloads stale Postgres → metadata edit vanishes unrecoverably | 144,150,136 |
| VD-2 | Verified | **active** (merge-only mitigated) | `app/main.py:1837-1843`, `1622-1631`; `identity_routes.py:1611,1622` | `save_registry` failure return ignored by ~29/30 callers; SWR refresh reverts confirm/rename ≤600s later, no error | 136,150,153,151 |
| VD-3 | Verified | **active** | `app/supabase_data.py:189-216` | `sync_relationships` = delete-all-then-batch-insert, no txn; mid-failure empties/partials the table, then propagates to the JSON "backup" on restart | 199,136 |
| VD-4 | Verified | **active** | `app/supabase_data.py:858-859,874,892` | Optimistic-concurrency + name protection silently disabled when the prefetch flakes → stale batch overwrites a concurrent merge (the Session-132 bug, re-enabled in degraded windows) | 153,151 |
| R-1 | Risk | **active** | `app/upload_routes.py:1296-1317,1358-1361` | Upload Supabase sync non-strict + fully swallowed → new photos invisible on prod until a restart "repair" that may be weeks away (Lesson-144 window reopened by design) | 144,146 |
| R-2 | Risk | **active** | `app/supabase_data.py:865-941,753-778,812-821` | Batch writers commit sub-batches then raise → half-old/half-new identity graph (pre-131 orphan class); Lesson-199 atomicity never applied here | 199,154,145 |
| R-3 | Risk | **active / user-gated** | `app/sync_routes.py:564-640`; `app/main.py:1810-1818` | `/api/sync/resync-supabase` re-upserts entire volume JSON over Postgres; equal-version content drift (manual repairs) silently reverted — mitigation is only a doc | 206,153,56/69/78 |
| R-4 | Risk | **active** (low prob, high radius) | `app/upload_routes.py:1274,1299`; `app/main.py:1808-1820` | Ingest's JSON read races `save_registry`'s background JSON-backup write → clobbered `identities.json` → new-face identities lost or duplicated | 25/63,144,155 |
| R-5 | Risk | **active** (bounded) | `app/supabase_data.py:782-821`; `core/photo_registry.py:437-448` | `photo_faces` sync additive-only; stale face→photo rows never pruned → phantom membership resurfaces every load | 123,145 |
| R-6 | Risk | **active, documented-unenforced** | `app/main.py:3255-3268,2315-2344` | No-TTL module-global caches (`_photo_registry_cache`, `_date_labels_cache`) make out-of-band DB writes invisible until restart → operator re-runs destructive fix | 206,111,150 |
| R-7 | Risk | **active** (minor) | `app/supabase_data.py:488-495,566-567` | `gemini_api_calls` schema-drift filter reads `probe.data[0]`; empty table → returns None → unfiltered insert → PGRST204 whole-row drop returns (Session-166 bug, on a fresh/pruned table) | 105,152,205 |
| R-8 | Risk | **active** (low sev) | `app/supabase_data.py:290-312` vs `358` | Annotations startup sync is merge-only; rows deleted in Supabase persist in the JSON cache and resurrect on fallback | 123 |

## Mitigated — do NOT re-fix (credit where due)
- **identity_overrides resurrection** (Lesson 153): blocked by `tests/test_data_layer_invariants.py:23-104`
  + Session 168's 29 anti-reintroduction guards (now in CI, not `slow`).
- **Merge orphaned faces** (Lesson 154): post-merge verify + force-add, `core/registry.py:750-769`.
- **JSONB string-encoded arrays** (Lesson 142): guarded read (`core/registry.py` `_ensure_list`) +
  write (`app/supabase_data.py:671-686`) + `test_data_layer_invariants.py:181`.
- **GEDCOM non-atomic importer** (Lesson 199): PRD-064 single-transaction importer shipped S164.
- **Caveat:** the AST guard `tests/test_data_parity_invariants.py:75-107` deliberately permits
  `except Exception: log-and-continue` — which is exactly the shape behind VD-1/VD-3/R-1. The guard
  gives false comfort here.

## Stale-doc drift (contradicts current code — highest-leverage cleanup)
These four docs are loaded into session context and **actively mis-train agents toward the
JSON-canonical mental model that is the root posture behind the deploy-overwrite lessons
(56/69/78/141).** All are `stale-doc` (no code defect, but a standing prompt-injection risk):

| Doc | Stale claim | Reality |
|-----|-------------|---------|
| `docs/architecture/DATA_MODEL.md` | "no relational database for canonical data"; JSON atomic-write rules; 124 photos/292 identities | Postgres sole read source since S112; JSON write-only backup; ~1127 photos/1824 identities. **Highest-risk doc.** |
| `docs/architecture/OVERVIEW.md` | "Layer 1 canonical = Railway volume JSON"; "Postgres … not yet implemented"; Phases C–F "NOT STARTED" | Postgres canonical; annotations/relationships/GEDCOM in Supabase; C complete, E ~80%. |
| `docs/architecture/PHOTO_STORAGE.md` | dimensions must be cached in photo_index.json; JSON modified only at ingest | Dimensions from Supabase registry; photo_index.json rewritten as backup every save. |
| `docs/architecture/PERMISSIONS.md` | Upload = admin-only; binary model | Contributor/anon uploads + auto-approve shipped S104/S121. |

## Top-3 structural recommendations
1. **Make write-failure loud end-to-end** — `save_registry`/`save_photo_registry` failures must
   surface to the HTTP response + Sentry, not just logs (VD-1/VD-2 = live descendants of the #1
   repeat-offender).
2. **Apply Lesson-199 atomicity to the REST batch writers** — staged upsert + verify, or retry-then-
   abort-before-any-write; abort `shadow_write_identities_batch` when the concurrency prefetch
   fails (VD-4) instead of proceeding unprotected.
3. **Rewrite DATA_MODEL.md / OVERVIEW.md now** — they are session-context inputs; their JSON-canonical
   language is a standing nudge toward the exact failure class this audit covers.

## User Decisions (no action taken this run)
All fixes above require source-code edits (excluded). VD-1/VD-2/R-1/R-2 → Phase 2 sprint.
R-3/R-6 (destructive endpoints / cache design) are user-gated. Doc rewrites → `QUICK_WINS_QUEUE.md`.
