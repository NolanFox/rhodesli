# Session 90: Cleanup + Data Safety + Test Hygiene

**Context**: `docs/session_logs/session-89e-claude-review-log.md`
**Predecessor**: Session 89e Claude review (c666acd)

## Problem Statement

Session 89e left cleanup items and exposed two structural risks:
1. Critical data (identities, photos, embeddings) lives only on the Railway volume
2. The test suite is bloated (3700+ tests, ~7 min) with brittle integration tests

This session addresses immediate cleanup AND begins structural hardening.

## Session Protocol
- Set `.claude/current_session.txt` to `90`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, /clear between acts

---

## Act 1: Orient + Immediate Cleanup (15 min)

1. Read this prompt and context
2. **Clean up phantom duplicate on production**:
   - Photo `a75e6b54b0eb6c50` is SHA256 of `unknown.jpg`, auto-generated during repair
   - Person 877 (identity `1e0b3bc8-c823-4434-b12f-39c6dcf82cd2`) may be the phantom's identity — verify first
   - Use `scripts/cleanup_isolated_photo.py` or direct API to remove the phantom
   - VERIFY the real Benatar photo (`inbox_0c57277a_0_unknown`) still works after cleanup
3. **Set Benatar photo metadata**: Change source/collection from "Unknown" to "Claude Benatar upload"
4. Commit: `fix(data): clean up phantom duplicate + Benatar metadata`

## Act 2: Upload Date Backfill (20 min)

**Goal**: Every photo shows when it entered the archive. "Recently Uploaded" sort becomes meaningful.

1. **Option A (preferred)**: Add an admin endpoint `/api/admin/backfill-upload-dates` that runs the backfill logic directly on production data
2. **Option B**: Sync production data → run backfill locally → push back
3. Run it (dry-run first, then execute)
4. Verify "Recently Uploaded" sort shows community photos first
5. Commit: `feat(photos): backfill upload dates for all photos`

## Act 3: Railway Volume Backup Script (20 min)

**Goal**: Nightly backup of critical data files to R2 (or Supabase).

1. Create `scripts/backup_volume_to_r2.py`:
   - Backs up: identities.json, photo_index.json, embeddings.npy, date_labels.json, photo_locations.json
   - Uploads to R2 under `backups/YYYY-MM-DD/` prefix
   - Keeps last 7 days of backups
   - Can be called from Railway cron or startup
2. Add to Railway startup (run backup before app start)
3. Tests for the backup script
4. Commit: `feat(ops): automated volume backup to R2`

## Act 4: Test Suite Audit + Prune (30 min)

**Goal**: Reduce test count and runtime while keeping coverage.

### Analysis Phase
1. Categorize all test files into: contract tests, integration tests, implementation-detail tests
2. Identify tests that:
   - Check specific CSS classes or HTML attribute strings (brittle)
   - Use subprocess isolation (`_render_path`) — these mask real issues
   - Duplicate coverage (same route tested multiple ways)
   - Test historical behavior that no longer applies

### Prune Phase
3. Remove implementation-detail tests that add no value
4. Replace subprocess-isolated tests with proper monkeypatch isolation
5. Merge duplicate tests
6. Target: <2500 tests, <3 min runtime
7. Verify `make test-fast` still covers all critical paths
8. Commit: `refactor(tests): prune brittle tests, replace subprocess isolation`

## Act 5: Evaluate Data Migration Tradeoffs (15 min)

**Goal**: Decide whether to start Postgres migration now or defer.

### Write `docs/prds/027_data_migration.md` covering:
1. **Current state**: What's in JSON vs Postgres
2. **Risk analysis**: What happens if Railway volume is lost today?
3. **Migration options**:
   - A: Shadow writes (dual-write to JSON + Supabase) — low risk, incremental
   - B: Full migration (Supabase becomes source of truth) — high effort, high reward
   - C: Backup-only (nightly R2 backup) — minimal code change, still at risk during the day
4. **Recommendation** with estimated effort for each option
5. **Decision**: What to do in Session 91+

Commit: `docs(prd): data migration tradeoff analysis`

## Act 6: Assessment + Docs (10 min)

Standard session outputs.

## Acceptance Criteria

- [ ] Phantom duplicate cleaned from production
- [ ] Benatar photo metadata corrected
- [ ] All photos have upload_date
- [ ] "Recently Uploaded" sort works correctly
- [ ] Volume backup script exists and runs
- [ ] Test count reduced by at least 500
- [ ] Test runtime reduced by at least 2 minutes
- [ ] Data migration PRD written
- [ ] Assessment written
- [ ] All tests pass

## Tradeoff Guidance

**Should we do the test pruning now?**
- PRO: Every future session pays the 7-min tax. Pruning saves cumulative hours.
- PRO: Subprocess tests are active technical debt from Codex.
- CON: 30 min of pruning could be spent on user-facing features.
- RECOMMENDATION: Yes, do it. The ROI is positive within 5 sessions.

**Should we start data migration now?**
- PRO: Volume loss risk is real and existential.
- PRO: Shadow writes (Option A) are low risk and incremental.
- CON: Full migration is a multi-session effort.
- RECOMMENDATION: Start with backup script (Act 3) + shadow writes in Session 91. Full migration deferred to Session 92+.
