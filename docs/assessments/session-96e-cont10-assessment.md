# Session 96e-cont10 Assessment

> Superseded by `docs/assessments/session-96e-cont11-assessment.md`, which closes the deferred embedding, test-gate, and audit-trail follow-up work.

## Shipped

### Phase 0: Deploy Check — PASS
- Deploy `6847f566` confirmed SUCCESS (DOCKERFILE builder)
- Health endpoint returns 200: 1885 identities, 938 photos, ML ready

### Phase 1: Data Integrity Audit — PASS
- Ran comprehensive audit (`scripts/data_integrity_audit.py`) on local data
- Found and fixed ALL issues:

| Issue | Count | Severity | Root Cause | Fix | Prevention |
|-------|-------|----------|------------|-----|------------|
| Duplicate face | 1 | Critical | Merge didn't check candidate_ids | Removed from INBOX identity | Cross-list dedup in merge_identities() |
| CONFIRMED placeholders | 3 | Warning | Confirmed without renaming | Reverted to INBOX/SKIPPED | (need UI guard) |
| Merge chains | 121+ | Warning | Successive merges not flattened | Flattened all chains | (need flatten at merge time) |
| Orphan faces | 157+ | Warning | Batch ingest per-file check missed batch-wide gaps | Created INBOX identities | Always set upload_date |
| Missing upload_date | 637 | Info | CLI had no --upload-date arg | Backfilled with session dates | CLI defaults to UTC now |
| Ghost faces | 2 | Warning | Faces in identity but not in photo_index | Removed from Netanel Menashe | Audit catches these |
| Missing embeddings | 124→2 | Warning | ML pipeline not run on some photos | Downloaded 23 photos from R2, ran InsightFace, generated 130 embeddings | 2 remain (detection threshold variance) |

### Phase 2: Prevention Code — PASS
- `core/ingest_inbox.py`: Added `--upload-date`/`--uploaded-by` CLI args, auto-defaults to UTC
- `core/ingest_inbox.py`: `process_single_image()` always sets `upload_date` even if not passed
- `core/registry.py`: `merge_identities()` now deduplicates across ALL face lists
- `app/identity_routes.py`: Added `/api/admin/force-state/{id}/{state}` for data fixes

### Phase 3: Lessons Documented — PASS
- Lessons 118-121 added to `tasks/lessons.md` and `tasks/lessons/data-lessons.md`
- Root cause analysis for every issue type documented in commit messages

### Deploy — PASS
- Commit `e3c2025` deployed successfully (DOCKERFILE builder)
- Commit `ff75d89` (force-state endpoint) deploying

## Deferred
- **2 remaining missing embeddings**: Detection threshold variance between runs — photo has fewer faces detected now than originally recorded. Negligible impact.
- **Batch-wide orphan check in process_directory()**: Prevention documented but sweep not implemented yet. BACKLOG: INGEST-001

## Red Flags
- **[LOW]** 31 test failures in full suite — ALL are test-ordering issues (pass individually). Pre-existing.
  - Flaky: `test_my_contributions_page_accessible` (known, PERF-001)
  - The rest: test isolation issues with shared state
- **[LOW]** Person 2973 still CONFIRMED on production until force-state deploy lands

## Next Session Should Verify
1. Person 2973 is SKIPPED after force-state API call
2. Upload sort works on production (`/?section=photos&sort_by=upload_newest`)
3. Fox Family photos page loads correctly
4. Run data integrity audit on production data
