# Session 103 — ML Pipeline Execution + Triage Fixes

**Run with:** `./scripts/run_session.sh docs/prompts/session-103-prompt.md`

Each phase below runs as a SEPARATE `claude -p` invocation with fresh context.
Do NOT try to remember what happened in prior phases — read the checkpoint file instead.

- Context: `docs/session_context/session-103-context.md`
- Current: v0.99.5, ~4296 tests, 941 photos, 1922 active identities, 91 confirmed
- Goal: Run ML pipeline, fix P0 triage bugs, report actual numbers

---

## Phase 0: Orient

1. Set `.claude/current_session.txt` to `103`
2. Read `tasks/lessons.md` (index only — don't read sub-files unless needed)
3. Read `docs/session_context/session-103-context.md`
4. Verify deploy: `curl -s https://rhodesli.nolanandrewfox.com/health | head -5`
5. Create `docs/session_logs/session-103-log.md` with this checklist:
   ```
   # Session 103 Log
   Started: [timestamp]

   ## Phase Checklist
   - [ ] Phase 0: Orient
   - [ ] Phase 1: Create ML Supabase tables
   - [ ] Phase 2: Run baseline clustering with tracking
   - [ ] Phase 3: Run reranker comparison
   - [ ] Phase 4: Community-scoped suggestions
   - [ ] Phase 5: Test gaps (TEST-003, TEST-004, OBS-003)
   - [ ] Phase 6: P0 triage fixes (FB-168, FB-150)
   - [ ] Phase 7: P1 triage fixes
   - [ ] Phase 8: Deploy + browser verify
   - [ ] Phase 9: Session closeout
   ```
6. Commit: `chore: session 103 orient`

---

## Phase 1: Create PRD-046 Supabase Tables

**Goal:** `ml_runs` and `ml_proposals` tables exist in Supabase.

1. Write SQL migration: `scripts/migrations/create_ml_run_tables.sql`
   ```sql
   CREATE TABLE IF NOT EXISTS ml_runs (
     run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     created_at TIMESTAMPTZ DEFAULT now(),
     pipeline_type TEXT NOT NULL,
     config_json JSONB,
     status TEXT DEFAULT 'running',
     result_summary JSONB,
     duration_ms INT,
     triggered_by TEXT DEFAULT 'manual',
     parent_run_id UUID REFERENCES ml_runs(run_id)
   );

   CREATE TABLE IF NOT EXISTS ml_proposals (
     proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     run_id UUID REFERENCES ml_runs(run_id),
     source_identity_id UUID,
     target_identity_id UUID,
     score FLOAT,
     calibrated_score FLOAT,
     tier TEXT,
     status TEXT DEFAULT 'pending',
     decided_by TEXT,
     decided_at TIMESTAMPTZ
   );

   CREATE INDEX idx_ml_proposals_run ON ml_proposals(run_id);
   CREATE INDEX idx_ml_proposals_status ON ml_proposals(status);
   ```

2. Run migration against Supabase (read SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from `.env`)
3. Verify tables exist with a test insert + delete
4. Write test: `test_ml_runs_table_schema` — mock Supabase, verify insert/query shape

**Commit:** `feat(ml): create ml_runs + ml_proposals Supabase tables (PRD-046)`

---

## Phase 2: Run Baseline Clustering with Run Tracking

**Goal:** Run `cluster_new_faces.py` and record the run in `ml_runs` + `ml_proposals`.

**Key files:** `scripts/cluster_new_faces.py`, `data/proposals.json`

1. Modify `scripts/cluster_new_faces.py` to:
   - Create an `ml_runs` record at start (pipeline_type='cluster_new_faces', config includes threshold + scorer)
   - Write each proposal to `ml_proposals` with run_id
   - Update `ml_runs.status` to 'completed' and populate result_summary at end
   - Still write proposals.json for backward compat
   - Add `--run-id` output so the run can be referenced later

2. Run: `source venv/bin/activate && python scripts/cluster_new_faces.py --dry-run`
   - Record: how many proposals? What tier distribution? Which identities matched?

3. Save run output to `docs/ml/run_results/baseline_run_103.md` with:
   - Run ID, timestamp, config, proposal count, tier breakdown
   - Top 10 proposals by confidence
   - Any cross-community matches flagged

4. Tests:
   - `test_cluster_creates_ml_run_record` — mock Supabase, verify ml_runs row written
   - `test_cluster_writes_proposals_to_supabase` — verify ml_proposals rows

**Commit:** `feat(ml): run-tracked clustering pipeline (PRD-046 Phase 1)`

---

## Phase 3: Run Reranker in Shadow Mode + Compare

**Goal:** Run `cluster_new_faces.py --scorer longitudinal-shadow` and compare against baseline.

**Key files:** `scripts/cluster_new_faces.py`, `rhodesli_ml/longitudinal_reranker.py`

1. Run: `source venv/bin/activate && python scripts/cluster_new_faces.py --scorer longitudinal-shadow --dry-run`
   - Record: how many proposals? How do they differ from baseline?

2. Write `scripts/compare_ml_runs.py`:
   - Input: two run_ids (or two proposals files)
   - Output: markdown table showing:
     - New proposals in run B not in A
     - Removed proposals (in A not B)
     - Score changes for same pairs
     - Tier changes (e.g., LOW → HIGH)
   - Summary: net positive, negative, or neutral

3. Run comparison: `source venv/bin/activate && python scripts/compare_ml_runs.py --run-a {baseline_id} --run-b {reranker_id}`

4. Save results to `docs/ml/run_results/reranker_comparison_103.md` with:
   - Side-by-side score table
   - Which proposals improved? Which degraded?
   - Recommendation: should reranker be activated?

5. **Key question to answer:** Does the reranker reduce false positives like Big Leon appearing for Fox family clusters (FB-147)?

6. Tests:
   - `test_compare_ml_runs_outputs_diff` — verify diff format

**Commit:** `feat(ml): reranker shadow comparison + compare_ml_runs.py`

---

## Phase 4: Community-Scoped Suggestions

**Goal:** Fix FB-147 (Big Leon recurring) and PERF-007 (similar panel not community-scoped).

**Key files:** `app/browse_routes.py`, `app/cluster_review_routes.py`

1. In `app/browse_routes.py` `/api/find-similar/{identity_id}` endpoint:
   - After `find_nearest_neighbors()` returns, filter results by community
   - Same-community results first, cross-community only if < 5 same-community results
   - Use `identity_communities` table or community membership set

2. In `app/cluster_review_routes.py` suggested matches section:
   - Rank same-community confirmed identities first
   - Cross-community matches shown below with badge

3. Fix cross-community badge text (FB-148):
   - Change "From Jewish Community of Rhodes" → "Jewish Community of Rhodes"
   - `grep -r '"From "' app/` to find all instances
   - Remove the "From " prefix

4. Tests:
   - `test_similar_results_community_scoped` — verify same-community results appear first
   - `test_suggested_matches_community_ordered` — verify speed-run suggestions prioritize same community
   - `test_cross_community_badge_no_from_prefix` — verify badge text

**Commit:** `fix(ux): community-scoped suggestions + badge text (FB-147, FB-148, PERF-007)`

---

## Phase 5: Session 102 Test Gaps

**Goal:** Close TEST-003, TEST-004, OBS-003.

1. **TEST-003**: Write `test_data_019_rhodes_photos_not_in_fox_family`
   - Verify no photo with collection "Jews of Rhodes" appears in Fox Family identity set

2. **TEST-004**: Write `test_postgres_name_protection_guard`
   - Mock Supabase with a real name, local registry with "Unidentified Person NNN"
   - Verify name field skipped during sync

3. **OBS-003**: Add `input_method` to `log_user_action()` calls in speed-run
   - Keyboard handlers pass `input_method="keyboard"`
   - Button click handlers pass `input_method="button"`
   - Test: verify log entry includes input_method field

**Commit:** `test: close Session 102 test gaps (TEST-003, TEST-004, OBS-003)`

---

## Phase 6: P0 Triage Fixes

**Goal:** Fix the two P0 bugs that block manual face tagging.

Read `docs/session_context/session-103-context.md` for full details on FB-168 and FB-169.

### FB-168: Tag search click doesn't assign identity to face (BROKEN)
- On photo page, clicking a face bbox, searching a name, clicking the search result — nothing happens
- Tag assignment endpoint: `app/identity_routes.py` `/api/face/tag` (line ~908)
- Search dropdown: `app/identity_routes.py` `/api/face/tag-search` (line ~736)
- Investigate: URL encoding of face_id with special chars (colons, spaces), HTMX swap target, POST handler
- **Must verify fix works in browser before committing**

### FB-150: Speed Loop lost face card navigation (REGRESSION)
- Suggestion thumbnails in Speed Loop are not clickable
- Previously could click through to inspect all faces of a suggested match
- Check: `app/cluster_review_routes.py` — suggestion card rendering, click handlers
- This was a regression from Session 102 Track C navigation changes

### FB-169: Esther Burd Fox label shows "Unidentified"
- May be caused by FB-168 (tag never actually assigned)
- If FB-168 fix resolves this, note it. Otherwise investigate `app/page_routes.py` line ~3734

Tests for each fix. **Do not lose existing functionality** — before modifying any component, verify the existing behavior first.

**Commit:** `fix(ux): P0 tag assignment + speed loop navigation (FB-168, FB-150, FB-169)`

---

## Phase 7: P1 Triage Fixes

**Goal:** Fix P1 items from triage, BACKLOG the rest.

Read `docs/session_context/session-103-context.md` Parts 2 and 4 for full FB item details.

P1 items to fix (if <15 min each, otherwise BACKLOG):
- FB-153: /identify/ shows wrong community for Fox Family identity
- FB-159/160: Confirmed identity ranks below unnamed fragments in similar panel
- FB-162: Tag search doesn't prioritize confirmed/same-community identities
- FB-161: Dismissed identities re-appear in speed-run queue

P2 items — create BACKLOG entries with specifics for ALL of these:
- FB-149, FB-151/152, FB-154/156, FB-155, FB-157/158, FB-163/164, FB-165, FB-166/167

Each BACKLOG entry needs: FB number, one-line description, file to modify, estimated effort.

**Commit:** `fix(ux): P1 triage fixes + BACKLOG entries (FB-153, FB-159-162)`

---

## Phase 8: Deploy + Browser Verify

**Goal:** Deploy and verify fixes in production browser.

1. Push: `git push origin main` (or `railway deploy` if git push fails)
2. Wait for deploy: check with Railway MCP or `curl https://rhodesli.nolanandrewfox.com/health`
3. Browser verify (use Claude Chrome — admin is logged in):
   - [ ] Tag a face on a Fox Family photo page — click bbox, search name, click result → tag is assigned
   - [ ] Speed-run suggested matches show Fox Family identities first (not Big Leon)
   - [ ] Cross-community badge says community name without "From"
   - [ ] Speed Loop suggestion thumbnails are clickable
   - [ ] Similar panel on person page shows same-community results first
4. Save screenshots to `docs/screenshots/session-103/`
5. Log results in session log

**Commit:** `docs: session 103 browser verification`

---

## Phase 9: Session Closeout

**Goal:** Write assessment, update all harness docs.

1. Re-read the original prompt: `docs/prompts/session-103-prompt.md`
2. Re-read the session log: `docs/session_logs/session-103-log.md`
3. Read checkpoint: `.claude/session_checkpoint.md`

4. Write `docs/assessments/session-103-assessment.md`:
   - For each phase: PASS/FAIL with evidence (file paths, test counts, screenshot refs)
   - ML comparison results: did the reranker improve? Include actual numbers
   - Deferred items with BACKLOG references
   - Red flags with severity

5. Update CHANGELOG.md — add v0.99.6 entry
6. Update ROADMAP.md — move completed items, add date
7. Update BACKLOG.md — all P2 FB items with entries
8. Update `docs/roadmap/SESSION_HISTORY.md` — add Session 103 entry

**Commit:** `docs: session 103 closeout`
