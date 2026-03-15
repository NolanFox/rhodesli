# Session 103 — ML Pipeline Execution + Triage Fixes

## Predecessor
- Context: `docs/session_context/session-103-context.md`
- Prior: `docs/session_context/session-102-context.md`
- Feedback: FB-147, FB-148 (from Session 102 triage sprint)
- Current: v0.99.5, ~4296 tests, 941 photos, 1922 active identities, 91 confirmed

## Goal

**Execute the ML pipeline work that Session 102 deferred.** Actually run the reranker, actually compare scores, actually create Supabase tables, actually give a real answer on whether constrained clustering improves results. Also fix triage UX feedback.

No more PRDs. No more planning docs. Run code, measure results, report numbers.

---

## Phase 0: Orient (5 min)

1. Set `.claude/current_session.txt` to `103`
2. Read `tasks/lessons.md` + `docs/session_context/session-103-context.md`
3. Verify deploy: `/health` check
4. Create `docs/session_logs/session-103-log.md` with phase checklist
5. Commit: `chore: session 103 orient`
6. **DO NOT /clear yet — Phase 1 needs full context**

---

## Phase 1: Create PRD-046 Supabase Tables (15 min)

**Goal:** ml_runs and ml_proposals tables exist in Supabase.

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

2. Run migration against Supabase (via `supabase.rpc()` or SQL editor)
3. Verify tables exist with a test insert + delete
4. Write test: `test_ml_runs_table_schema` — verify table exists via Supabase client

**Commit:** `feat(ml): create ml_runs + ml_proposals Supabase tables (PRD-046)`
**/clear after commit**

---

## Phase 2: Run Baseline Clustering with Run Tracking (20 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

**Goal:** Run `cluster_new_faces.py` and record the run in ml_runs + ml_proposals.

1. Modify `scripts/cluster_new_faces.py` to:
   - Create an `ml_runs` record at start (pipeline_type='cluster_new_faces', config includes threshold + scorer)
   - Write each proposal to `ml_proposals` with run_id
   - Update `ml_runs.status` to 'completed' and populate result_summary at end
   - Still write proposals.json for backward compat
   - Add `--run-id` output so the run can be referenced later

2. Run: `python scripts/cluster_new_faces.py --dry-run`
   - Record: how many proposals? What tier distribution? Which identities matched?

3. Save run output to `docs/ml/run_results/baseline_run_103.md` with:
   - Run ID, timestamp, config, proposal count, tier breakdown
   - Top 10 proposals by confidence
   - Any cross-community matches flagged

4. Tests:
   - `test_cluster_creates_ml_run_record` — mock Supabase, verify ml_runs row written
   - `test_cluster_writes_proposals_to_supabase` — verify ml_proposals rows

**Commit:** `feat(ml): run-tracked clustering pipeline (PRD-046 Phase 1)`
**/clear after commit**

---

## Phase 3: Run Reranker in Shadow Mode + Compare (30 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

**Goal:** Run `cluster_new_faces.py --scorer longitudinal-shadow` and compare against baseline.

1. Run: `python scripts/cluster_new_faces.py --scorer longitudinal-shadow --dry-run`
   - Record: how many proposals? How do they differ from baseline?

2. Write `scripts/compare_ml_runs.py`:
   - Input: two run_ids (or two proposals files)
   - Output: markdown table showing:
     - New proposals in run B not in A
     - Removed proposals (in A not B)
     - Score changes for same pairs
     - Tier changes (e.g., LOW → HIGH)
   - Summary: net positive, negative, or neutral

3. Run comparison: `python scripts/compare_ml_runs.py --run-a {baseline_id} --run-b {reranker_id}`

4. Save results to `docs/ml/run_results/reranker_comparison_103.md` with:
   - Side-by-side score table
   - Which proposals improved? Which degraded?
   - Recommendation: should reranker be activated?

5. **Key question to answer:** Does the reranker reduce false positives like Big Leon appearing for Fox family clusters (FB-147)?

6. Tests:
   - `test_compare_ml_runs_outputs_diff` — verify diff format

**Commit:** `feat(ml): reranker shadow comparison + compare_ml_runs.py`
**/clear after commit**

---

## Phase 4: Community-Scoped Suggestions (20 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

**Goal:** Fix FB-147 (Big Leon recurring) and PERF-007 (similar panel not community-scoped).

1. In `app/browse_routes.py` `/api/find-similar/{identity_id}` endpoint:
   - After `find_nearest_neighbors()` returns, filter results by community
   - Same-community results first, cross-community only if < 5 same-community results
   - Use `identity_communities` table or community membership set

2. In `app/cluster_review_routes.py` suggested matches section:
   - Rank same-community confirmed identities first
   - Cross-community matches shown below with badge

3. Fix cross-community badge text (FB-148):
   - Change "From Jewish Community of Rhodes" → "Jewish Community of Rhodes"
   - Find all instances of `"From "` prefix in cross-community badge rendering
   - Remove the "From " prefix

4. Tests:
   - `test_similar_results_community_scoped` — verify same-community results appear first
   - `test_suggested_matches_community_ordered` — verify speed-run suggestions prioritize same community
   - `test_cross_community_badge_no_from_prefix` — verify badge text

**Commit:** `fix(ux): community-scoped suggestions + badge text (FB-147, FB-148, PERF-007)`
**/clear after commit**

---

## Phase 5: Session 102 Test Gaps (15 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

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
**/clear after commit**

---

## Phase 6: Fold in Triage Feedback (15 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

**Goal:** Fix any remaining triage feedback from Nolan's Session 102 Phase 8.

Check `docs/feedback/2026-03-15-fox-triage-round3.md` for additional items beyond FB-147/148.

For each item:
1. Can it be fixed in <10 min? → Fix immediately, commit
2. Cannot be fixed quickly? → Create BACKLOG entry with specifics

**Commit:** `fix(ux): triage feedback fixes (FB-NNN)`
**/clear after commit**

---

## Phase 7: Browser Verify + Deploy (15 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

1. Deploy: `git push origin main` or `railway deploy`
2. Browser verify:
   - [ ] Speed-run suggested matches show Fox Family identities first (not Big Leon)
   - [ ] Cross-community badge says community name without "From"
   - [ ] Similar panel on person page shows same-community results first
   - [ ] ML run visible in Supabase ml_runs table
3. Save screenshots to `docs/screenshots/session-103/`

**Commit:** `docs: session 103 browser verification`
**/clear after commit**

---

## Phase 8: Session Closeout (10 min)

**Re-read this phase from `docs/prompts/session-103-prompt.md` after /clear.**

1. Write `docs/assessments/session-103-assessment.md`
2. Update CHANGELOG.md, ROADMAP.md, BACKLOG.md
3. Update SESSION_HISTORY.md
4. Key deliverable in assessment: **ML comparison results** — did the reranker improve things? Include actual numbers.

**Commit:** `docs: session 103 closeout`

---

## Critical Rules

- **/clear between phases** — MANDATORY
- **Sequential, not parallel** — Session 102 parallel tracks executed but orchestrator cut corners on verification. Run each phase fully, verify, commit, then move to next.
- **Run code, don't write docs** — Phase 7 of Session 102 wrote PRDs instead of executing. This session RUNS the pipeline.
- **Report actual numbers** — "AUC improved from X to Y" or "no improvement, here's why"
- **Test before every commit** — `make test-fast`
- **Browser verify** — Lesson 131
- **Monitor context** — at 30% remaining, stop and write handoff
- **Overnight execution** — Nolan will check results in the morning. Every phase must produce verifiable artifacts. No "PASS without evidence."
- **Do not lose functionality** — FB-150 was a regression. Before modifying any UI component, verify existing functionality still works after the change.

---

## Acceptance Criteria

Session 103 is done when:
1. `ml_runs` and `ml_proposals` tables exist in Supabase with at least 2 runs recorded
2. Baseline vs reranker comparison exists with actual score data
3. `compare_ml_runs.py` produces a readable diff between runs
4. Community-scoped suggestions deployed and verified (Big Leon not appearing for Fox clusters)
5. Cross-community badge text fixed
6. Session 102 test gaps closed (TEST-003, TEST-004, OBS-003)
7. All tests pass
8. Assessment includes ML comparison numbers
