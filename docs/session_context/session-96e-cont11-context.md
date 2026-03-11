# Session 96e-cont11 Context

## Goal
Finish the incomplete stabilization work from 96e-cont10 with non-destructive,
fully documented data handling. Close the remaining regressions before live
upload validation on Rhodes and Fox Family.

## User Requirements
- All data changes must be non-destructive and reversible.
- Record all research, work, and user feedback in harness docs to survive compaction.
- Audit for broader community-related regressions, not just the originally reported issues.
- Confirm what happened with the 124 missing embeddings and whether InsightFace was run.
- Backup first, use merge-aware writes only, and leave a clear unwind trail.
- Do not consider the session done until every material finding from the pre-compact review is either fixed or explicitly accounted for in the docs.

## Findings So Far
- Local `data/photo_index.json` has 932 photos; live `/health` reports 938 photos.
- Local audit reports 3319 identities, 932 photos, 0 critical issues, 2 missing embeddings.
- Production sync API reports 3255 identities, 938 photos, 87 confirmed.
- Live `/health` reports 1885 identities because production app is loading identities from Postgres.
- Conclusion: local repo, production volume JSON, and production Postgres are not aligned.
- Structured-anchor merge regression:
  - `merge_identities()` used `set(target["anchor_ids"])`,
  - structured/dict anchors are supported elsewhere,
  - reproduced locally as `TypeError: unhashable type: 'dict'`.
- App test gate was red:
  - `pytest tests/ -x -q` failed in `tests/e2e/test_discovery_layer.py`,
  - reproduced as `/photos` rendering zero cards when community scoping failed.
- Force-state route bypassed registry history:
  - route mutated `registry._identities[...]` directly,
  - changes were not recorded in append-only identity history.
- Harness docs were stale:
  - `docs/SESSION_LOG.md` still said `124 missing embeddings -> DEFERRED`,
  - `docs/BACKLOG.md` still tracked `124` missing embeddings,
  - `docs/assessments/session-96e-cont10-assessment.md` still described the force-state deploy / Person 2973 fix as pending.
- Continuation prompt gaps:
  - no evidence yet that the production audit step from `docs/prompts/session-96e-cont10-prompt.md` was completed,
  - no evidence yet that the requested backlog entry for identity state-change audit trail was completed.
- Jacob photo / dismissed-face investigation:
  - current `Jacob Cohen` identity is still present and CONFIRMED,
  - current `Unidentified Person 863` is still present and `CONTESTED`,
  - the user now believes there may not be any truly missing face in that photo,
  - the remaining concern is auditability: whether a prior dismissal/decline was durably logged.
- Current evidence on `Person 863`:
  - face id: `inbox_dc1b6b162ec3`,
  - identity id: `7efabe31-3bbb-4788-a4bb-0e3c794ff8d5`,
  - current state exists in `data/identities.json`,
  - no matching append-only history event exists in `data/identities.json` global `history`,
  - no local `logs/events.jsonl` match was found either.
- Unexpected local `data/identities.json` diff investigation:
  - seven identities were renamed from `Unidentified Person ...` to named people,
  - the rename timestamps match approved `name_suggestion` entries in `data/annotations.json`,
  - a timestamped backup file was created when those writes happened,
  - conclusion: these were legitimate annotation approvals, not random test corruption,
  - remaining problem was auditability: the rename path updated identity data without recording identity-history events.
- Interpretation:
  - we do NOT currently have proof of ongoing face loss on the Jacob image,
  - we DO have proof that identity-state audit history is incomplete for at least one dismissed/contested face,
  - this is being treated as a real data-confidence issue that must be hardened before calling the session done.

## Root Causes Identified
- Plain deploy did not reconcile data because `init_railway_volume.py` safety gates blocked overwriting:
  - `identities.json` blocked when volume had more confirmed identities than bundle.
  - `photo_index.json` blocked when volume had more photos than bundle.
- `/photos` test failure is caused by community scoping:
  - default Rhodes community falls back correctly when community lookup fails,
  - but `_get_community_photo_ids()` returns an empty set when Supabase photo-community lookup fails,
  - causing local `/photos` to render zero cards instead of falling back to no filtering.
- `merge_identities()` regression:
  - recent dedup change uses `set(target["anchor_ids"])`,
  - structured/dict anchors are supported elsewhere in the codebase,
  - merging into such an identity raises `TypeError: unhashable type: 'dict'`.
- `process_directory()` still lacks a real post-batch orphan sweep.
- `force-state` route mutates registry state directly instead of using registry history machinery.
- Postgres-backed registry loads were too thin:
  - `IdentityRegistry.load_from_postgres()` loaded only the base `identities` rows,
  - full-fidelity user-modified identity payloads live in `identity_overrides`,
  - append-only registry history was not loaded at all,
  - result: state could survive while audit/replay breadcrumbs disappeared.
- Approved annotation rename path was bypassing registry history:
  - `/admin/approvals/{ann_id}/approve` mutated `identity["name"]` directly,
  - annotation approval breadcrumbs existed,
  - identity rename breadcrumbs did not.
- Discovery review actions were bypassing registry history:
  - `/api/discovery/reject` mutated `negative_ids` directly,
  - `/api/discovery/confirm` mutated `candidate_ids` directly,
  - `/api/discovery/undo` mutated `candidate_ids` directly,
  - discovery log captured the ML signal, but registry history did not capture the identity mutation.
- Admin review queue e2e failure was not a data problem:
  - `/admin/review-queue` crashed in the real app process with `NameError: photo_url is not defined`,
  - Playwright then saw an empty page instead of review items.
- Compare pair route had a hidden resilience bug:
  - cross-photo summary rendering was wrapped inside archive lookup error handling,
  - any archive-side exception removed the cross-photo section even though it did not depend on archive data.
- Contributor page failure was a cache robustness bug:
  - `_get_featured_photos()` assumed every cached photo had a `filename`,
  - a stale/minimal cache entry could crash `/my-contributions` with `KeyError: 'filename'`.

## Embeddings Findings So Far
- Commit `357a5ae` increased `data/embeddings.npy` size from `12073703` to `12366572` bytes.
- Commit message states: downloaded 23 photos from R2, ran InsightFace locally, generated 130 embeddings, mapped 122/124 missing face IDs.
- Local audit now reports `missing_embeddings = 2`, consistent with that claim.
- Deep dive on the remaining 2 missing embeddings:
  - one face on the Holocaust collage photo only reappears when InsightFace threshold is lowered to ~`0.3`,
  - the newspaper wedding photo still detects fewer faces even with lower threshold,
  - conclusion: the 2 residual misses are detector-threshold variance, not fabricated work.

## Code Fixes In Progress
- Patched `core/registry.py` to normalize mixed anchor formats during merge dedup.
- Added registry-level `force_state()` so forced state changes record append-only history.
- Patched `app/identity_routes.py` to call registry `force_state()` instead of mutating `_identities` directly.
- Patched `app/main.py` community scoping helpers so Supabase lookup failures fall back to `None` (no filtering) rather than empty sets.
- Added post-batch orphan repair plumbing in `core/ingest_inbox.py` to create emergency INBOX identities if a completed ingest batch still leaves unassigned faces.
- Patched `app/admin_routes.py` review queue to use `_main_mod.photo_url(...)` so the real app server no longer crashes building review thumbnails.
- Patched `app/admin_routes.py` annotation approval path to call `registry.rename_identity(...)` so approved name suggestions record append-only identity history.
- Patched `core/registry.py` with audited helpers for:
  - `add_candidate_face(...)`,
  - `remove_candidate_face(...)`,
  - `add_negative_reference(...)`,
  - plus undo support for those new event types.
- Patched `app/discoveries_routes.py` so reject / confirm / undo use audited registry helpers instead of mutating lists directly.
- Patched Postgres identity load/save path:
  - shadow writes now include `metadata`, `created_at`, and `updated_at`,
  - registry events now sync into Supabase `audit_log` as `target_type=identity_event`,
  - Postgres loads now merge `identity_overrides` back over base identities,
  - Postgres loads now restore append-only identity history from audit-log identity events.
- Patched `app/compare_routes.py` so "Top cross-photo matches" always renders even if archive lookup fails.
- Patched `app/page_routes.py` so `_get_featured_photos()` skips incomplete cached photo records instead of crashing contributor pages.

## Data Safety Status
- No additional data files have been modified in this continuation yet.
- No production reconciliation has been applied yet.
- Any later data reconciliation must go through a backup-bearing path with an explicit merge/sync report.
- Backup/recovery mechanisms confirmed in codebase:
  - atomic temp-file + rename writes,
  - `.bak.{timestamp}` file backups,
  - `data/backups/`, `data/auto_backups/`, `data/cleanup_backups/`,
  - `scripts/backup_to_r2.py` / `scripts/restore_from_r2.py`,
  - `scripts/sync_from_production.py` backup-first behavior.

## Verification Performed So Far
- `python scripts/data_integrity_audit.py --data-dir data/ --json`
- `pytest tests/test_data_integrity_audit.py -q` -> 51 passed
- `pytest rhodesli_ml/tests/ -x -q` -> 566 passed
- `pytest tests/ -x -q` -> fails in `tests/e2e/test_discovery_layer.py`
- Focused regression pack after latest fixes:
  - `pytest tests/test_postgres_reads.py tests/test_supabase_shadow.py tests/test_supabase_migration.py tests/test_registry.py tests/e2e/test_discovery_layer.py::test_admin_review_queue_sorted[chromium] -q`
  - result: `176 passed`
- `pytest tests/test_compare.py -q` -> 47 passed
- `pytest tests/test_annotations.py tests/test_registry.py tests/test_compare.py -q` -> 122 passed
- `pytest tests/test_discoveries.py tests/test_registry.py -q` -> 108 passed
- `pytest tests/test_contributor_roles.py tests/test_face_count.py -q` -> 33 passed
- Latest local audit after auditability fixes:
  - identities: 3319
  - photos: 932
  - orphans: 0
  - duplicates: 0
  - merge chains: 0
  - missing upload dates: 0
  - missing embeddings: 2 (`inbox_a56c556100a9`, `inbox_e64c25fc88a7`)
- `railway deployment list` -> latest deployment `19c0917b-720a-4eb2-ae41-0b81ea45d123` SUCCESS
- `curl https://rhodesli.nolanandrewfox.com/health` -> 200

## Next Actions
- Finish rerunning required app + ML suites.
- Document the Jacob/Person 863 ambiguity as a prior auditability incident with breadcrumbs for future recurrence.
- Perform merge-aware, backup-first production reconciliation only after code/test state is clean and fully documented.
- Reconcile harness docs and create an explicit unwind trail for:
  - legitimate annotation-approved renames,
  - historical audit gaps,
  - remaining 2 embedding misses,
  - any production drift still present after deploy/verification.

## Final Closeout
- Required gates are now green:
  - `pytest tests/ -x -q` → `4091 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` → `566 passed`
- Latest live deployment:
  - Railway deployment `49b4b3af-d47f-40b7-98d8-044398b4bee5` → `SUCCESS`
  - `/health` returned `200` with `1885` identities and `938` photos
- Photo-face contract bug closed:
  - local and live `d5bc8746012a6da3` now preserve `11` face records,
  - live page shows the archival-record note and includes `Caden Franco Sadis` in the people strip,
  - live `92229cbf4ca92644` now preserves `4` face records and surfaces the archival-record note instead of silently hiding the unmatched record.
- Remaining low-risk archival face records:
  - `inbox_a56c556100a9` → `Caden Franco Sadis`
  - `inbox_e64c25fc88a7` → `Unidentified Person df1a2b64`
- InsightFace follow-up conclusion:
  - InsightFace was run locally in the earlier session,
  - the 124 missing embeddings were reduced to 2,
  - the remaining issue was not fabricated work but a registry/artifact drift problem that the UI had been handling unsafely.
- Reversible data trail now exists in:
  - `docs/assessments/session-96e-cont11-local-audit-before.json`
  - `docs/assessments/session-96e-cont11-local-audit-after.json`
  - `docs/assessments/session-96e-cont11-local-delta.json`

## User Feedback Captured
- The user emphasized:
  - no destructive data handling,
  - explicit unwind breadcrumbs,
  - small incremental pushed commits,
  - confidence that community support would not break Rhodes or Fox uploads,
  - and concern that dismissed / declined non-faces might be disappearing without audit history.
- The Jacob/Person 863 review ended with the user’s updated interpretation:
  - there may not be a truly missing visible face on that image,
  - but the incident should still be documented as a prior auditability scare so future recurrences are easy to trace.
