# Session 113 — Audit Logging + Embeddings Sync + Harry Fox Verification

@docs/session_context/session-113-context.md
@docs/session_context/investigation-4063-harry-fox.md

Implement audit logging for all identity mutations (AUDIT-001, P0), sync production embeddings to close the local-production divergence gap, and verify the Harry Fox cluster with complete data. This session directly addresses platform gaps exposed by the Person 4063 / Harry Fox investigation.

## CRITICAL CONSTRAINTS

1. **ZERO REGRESSIONS** — all 4584+ app tests and 590+ ML tests must pass before every commit
2. **NEVER click action buttons on production** — browser automation is READ-ONLY (Lesson 149)
3. **/clear between phases** — commit atomically per phase, /clear immediately after
4. **Plan before coding** — read the full phase, understand 2nd-order effects, then implement
5. **Supabase disk IO** — monitor after deploy. TTL caches are the mitigation. If IO spikes, note in assessment.
6. **Do not modify perf_cache.py or neighbors.py** — Session 111f performance code is frozen
7. **Production embeddings.npy has 2957 entries, local has 2872** — sync BEFORE analysis

## Pre-Requisites

1. Read `tasks/lessons.md` — especially Lessons 145, 147, 148, 149, 150
2. Read `docs/session_context/session-113-context.md`
3. Read `docs/session_context/investigation-4063-harry-fox.md`
4. Set `echo "113" > .claude/current_session.txt`
5. Set `echo "implementation" > .claude/session_mode.txt`
6. Run `make test-fast` to confirm baseline
7. Read `docs/CODING_RULES.md` for testing requirements

## Phase 0: Orient + Sync Embeddings (10 min)

**Confirm current state and sync production embeddings to local.**

1. `git status` — clean working tree
2. `git log --oneline -5` — confirm Session 112 is the latest
3. Download production embeddings: `curl` or Python script using `/api/sync/embeddings` with `RHODESLI_SYNC_TOKEN`
4. Save to `data/embeddings.npy` (overwrite local with production copy)
5. Verify: load the new file, confirm 2957+ entries, confirm `inbox_c6abb86ff55b` (Harry Fox naturalization form) has an embedding
6. Commit: `git add data/embeddings.npy && git commit -m "data: sync production embeddings (2957 entries, +85 from web uploads)"`

**Do NOT proceed until embeddings are synced.**

Commit + /clear after this phase.

## Phase 1: AUDIT-001 — Audit Logging for Identity Mutations (45 min)

**Add audit_log writes to every identity mutation route in identity_routes.py.**

### 1A: Audit helper function

Create a helper in `app/identity_routes.py` (or a new `app/audit.py`):

```python
def _log_audit(action: str, entity_id: str, user_email: str | None,
               old_value: dict | None, new_value: dict | None,
               metadata: dict | None = None):
    """Write an audit_log entry to Supabase."""
```

The `audit_log` table already exists with columns: `id`, `action`, `entity_type`, `entity_id`, `user_id`, `user_email`, `old_value`, `new_value`, `metadata`, `created_at`.

Use `get_supabase_client()` from `app/supabase_data`. Fire-and-forget with `try/except` and `logging.error` (never crash the mutation).

### 1B: Wire audit logging into mutation routes

Find each mutation call site with `grep -n "merge_identities\|confirm_identity\|reject_face\|skip_identity\|detach_face\|rename" app/identity_routes.py`. For each:

- **merge**: Log action="merge", old_value={source_id, target_id, source_anchors}, new_value={merged_into, combined_anchors}, metadata={route, user_source, distance if available}
- **confirm**: Log action="confirm", old_value={state, name}, new_value={state: "CONFIRMED"}
- **reject**: Log action="reject", old_value={face_id, identity_id}, metadata={reason}
- **skip**: Log action="skip", old_value={state}, new_value={state: "SKIPPED"}
- **rename**: Log action="rename", old_value={name: old}, new_value={name: new}
- **detach**: Log action="detach", old_value={face_id, identity_id}

Also wire into `app/match_facecompare_routes.py` (merge via match mode) and any speed-run merge paths.

### 1C: Wire audit logging into tag routes

`grep -n "tag\|assign\|negative" app/identity_routes.py` — find face tag assignment and negative match routes. Log these too.

### Tests

- `test_merge_writes_audit_log` — mock Supabase, verify insert called with correct action/entity_id
- `test_confirm_writes_audit_log`
- `test_reject_writes_audit_log`
- `test_rename_writes_audit_log`
- `test_skip_writes_audit_log`
- `test_audit_log_failure_does_not_crash_mutation` — verify try/except works

### 2nd Order Effects
- Supabase egress: audit_log writes are small (< 1KB each), writes don't count against egress budget
- Performance: fire-and-forget with try/except, no blocking
- Existing tests: mutation tests should still pass since audit is additive

Commit + /clear after this phase.

## Phase 2: Verify Harry Fox Cluster with Production Data (20 min)

**With synced embeddings, run the full analysis and document findings.**

1. Load local `data/embeddings.npy` (now has production data)
2. Compute distances from naturalization form (`inbox_c6abb86ff55b`) to:
   - All 4 Harry Dayton faces
   - All 3 Person 4063 faces
   - Albert Fox centroid
3. For each Harry face, determine: closer to nat form or Albert?
4. Generate the full distance matrix (nat form + Harry 4 + Person 4063 3)
5. Write findings to `docs/session_context/investigation-4063-harry-fox.md` (append "## Verified Analysis" section)
6. If any Harry face is definitively closer to Albert, note it as a data quality concern in BACKLOG

### Tests
- `test_naturalization_form_has_embedding` — verify `inbox_c6abb86ff55b` exists in embeddings.npy

Commit + /clear after this phase.

## Phase 3: Deploy + Verify (15 min)

1. Run both test suites: `source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q`
2. Deploy: `railway deploy`
3. Verify deploy success (DOCKERFILE builder, not RAILPACK)
4. Browser verification (READ-ONLY):
   - [ ] Health endpoint returns 200
   - [ ] Person page loads for a confirmed identity
   - [ ] Check Supabase dashboard for disk IO status
5. Test audit logging works: perform a rename or skip on a test identity via curl, then query audit_log
6. `git log origin/main..HEAD` — must be empty (all pushed)

## Phase 4: Harness Outputs (10 min)

1. Write `docs/assessments/session-113-assessment.md`
2. Write `docs/session_logs/session-113-log.md`
3. Update `ROADMAP.md` — mark AUDIT-001 done, note embeddings sync
4. Update `CHANGELOG.md` — v0.99.22
5. Update `BACKLOG.md` — AUDIT-001 status, any new items from Harry Fox analysis
6. Update `docs/ml/ALGORITHMIC_DECISIONS.md` if any new AD entries
7. Verify: `git log origin/main..HEAD` is empty

## Verification Checklist

### Audit Logging
- [ ] Merge writes audit_log entry with source/target IDs
- [ ] Confirm writes audit_log entry
- [ ] Reject writes audit_log entry
- [ ] Skip writes audit_log entry
- [ ] Rename writes audit_log entry
- [ ] Audit failure doesn't crash the mutation
- [ ] Match mode merge also writes audit

### Embeddings
- [ ] Local embeddings.npy has 2957+ entries
- [ ] `inbox_c6abb86ff55b` has embedding
- [ ] Harry Fox analysis completed with ground truth data

### Standard
- [ ] All app tests pass (4584+)
- [ ] All ML tests pass (590+)
- [ ] Deploy SUCCESS (DOCKERFILE)
- [ ] Browser verified (READ-ONLY)
- [ ] Assessment written
- [ ] ROADMAP/CHANGELOG/BACKLOG updated
- [ ] No unpushed commits
