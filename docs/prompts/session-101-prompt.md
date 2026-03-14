# Session 101 — Fox Triage P1 Fixes + Performance + Triage Sprint

## Predecessor
- Context: `docs/session_context/session-101-context.md`
- Feedback: `docs/feedback/2026-03-14-fox-triage-feedback.md` (20 items, FB-100-119)
- Master status: `docs/session_context/session-100-master-status.md`
- Current: v0.99.3, 4276 tests, 3 Fox confirmed (Charles Fox 68, Esther Burd Fox 12, Roland Fox 31)

## Goal
Fix the 7 P1 friction points from Nolan's Fox triage session, improve performance, then do a triage sprint in the second half. No data regressions. No loss of functionality.

---

## Phase 0: Orient (5 min)
1. Set `.claude/current_session.txt` to `101`
2. Read `tasks/lessons.md` + `docs/session_context/session-101-context.md`
3. Verify deploy: `/health` check
4. Create `docs/session_logs/session-101-log.md` with phase checklist
5. Commit: `chore: session 101 orient`
6. **DO NOT /clear yet — Phase 1 is small**

---

## Phase 1: Parallel Track — FB-113 Under Review Badge (10 min)

**Launch as worktree subagent.** This is independent from all other fixes.

**Problem:** Public person page shows "Under Review" badge for CONFIRMED identities that have auto-generated names ("Unidentified Person 2986"). Also shows "This person hasn't been identified yet" CTA.

**Root cause:** `app/person_routes.py` line 256:
```python
is_confirmed = state == "CONFIRMED" and not display_name.startswith("Unidentified")
```

**Fix:**
- Decouple badge display from name presence
- CONFIRMED state → show "Confirmed" badge regardless of name
- Keep `is_confirmed` for name-dependent features (share CTA) — introduce `is_state_confirmed = state == "CONFIRMED"` for the badge
- Audit ALL usages of `is_confirmed` in person_routes.py (20+ locations) — only change badge-related ones

**Test:** CONFIRMED identity with "Unidentified Person" name shows "Confirmed" badge.
**Branch:** `session-101/fix-under-review-badge`
**Files:** `app/person_routes.py`, `tests/test_person_routes.py`

---

## Phase 2: Enrichment Panel Overhaul — FB-104 + FB-110 + FB-103 (40 min)

**After Phase 1 subagent launches, begin this immediately on main or separate worktree.**

### FB-104: Reorder enrichment panel
**File:** `app/cluster_review_routes.py`, function `_speed_run_enrichment_panel` (~line 1749)

Current order: Banner → Crop → Name input → Merge search → Suggestions → Skip
New order:
1. Banner + preview crop
2. **Merge search** — "Is this an existing person?" (move UP from position 4)
3. **Suggested matches** with merge buttons (move UP from position 5)
4. **Name input** — "Or name this new person:" (pre-fill from merge target if merged)
5. **GEDCOM link** (NEW — embed inline, see FB-110)
6. Done / Skip button

### FB-110: Add GEDCOM linking to enrichment panel
The GEDCOM panel already exists — `_main_mod._gedcom_link_panel(identity_id, name)` in `relationship_routes.py` line 943. Embed it in the enrichment panel after the name input section. Use the existing `_gedcom_link_panel` function.

**Watch out:** GEDCOM panel generates its own DOM IDs (`gedcom-results-{id}`). Must not conflict with speed-run card IDs. Test HTMX swap targets.

### FB-103: Merge confirmation — no silent fail
Current behavior: merge endpoint returns a card with `hx_trigger="load delay:1s"` that auto-advances. User sees nothing meaningful.

Fix:
- Show clear confirmation: "Merged N faces into [Name] (now M total faces)"
- **Remove auto-advance** — stay on enrichment panel
- Add explicit "Done — Next Cluster" button
- The enrichment panel should update to show the merged identity's info

**Tests for Phase 2:**
- `test_enrichment_panel_merge_before_name` — verify merge search appears before name input
- `test_enrichment_panel_includes_gedcom` — verify GEDCOM section present
- `test_merge_no_auto_advance` — verify no `hx_trigger="load delay"`, has explicit next button
- `test_merge_shows_face_count` — verify merged count in response

**Commit:** `feat(ux): enrichment panel overhaul — merge-first flow + GEDCOM + merge confirmation`
**/clear after commit**

---

## Phase 3: Cross-Community Badge + Admin Links — FB-100 + FB-106 (20 min)

**Re-read this phase from `docs/prompts/session-101-prompt.md` after /clear.**

### FB-100: Cross-community badge on suggestions
`_get_confirmed_identity_suggestions` returns suggested matches but has no community context. The `_cross_community_badge` function exists in `app/main.py` (~line 530).

Fix:
- Pass `request` to `_speed_run_enrichment_panel` (it has `request.state.community`)
- In suggestion rendering, add `_main_mod._cross_community_badge(identity_id, community)` to each card
- Also add to search results in the search-identities endpoint

### FB-106: Speed-run person links go to public page
Lines in cluster_review_routes.py use `href=f"{nav_prefix}/person/{identity_id}"` which is the public view. Admin needs admin controls visible.

Fix: Add `?from=admin` query param to person links from cluster review. On the person page, auto-expand admin section when `from=admin` is present. This is the simplest fix that doesn't require a new route.

**Tests:**
- `test_suggestions_have_community_badge` — mock cross-community identity, verify badge
- `test_person_links_admin_context` — verify links include admin param

**Commit:** `feat(ux): cross-community badges + admin-context links in speed-run`
**/clear after commit**

---

## Phase 4: Performance — FB-105 (20 min)

**Re-read this phase from `docs/prompts/session-101-prompt.md` after /clear.**

### Quick wins (implement)
1. **Cache repopulation after save:** In `save_registry()` (main.py ~line 1104), after saving, set `_registry_cache = registry` and `_registry_cache_time = time.time()` so the next load hits cache instead of re-parsing
2. **Pass registry to enrichment:** `_speed_run_enrichment_panel` and `_get_confirmed_identity_suggestions` both call `load_registry()` independently. Pass the already-loaded registry as a parameter.
3. **Merge endpoint reuse:** The merge endpoint loads registry, does the merge, saves. The confirmation message should use the in-memory data, not re-load.

### Profiling (investigate)
- Add `time.time()` measurements around: registry load, save, suggestion computation, merge execution
- Log to structlog so we can see in Railway logs
- Report findings in session log

**Tests:**
- `test_save_registry_repopulates_cache` — after save, next load should be instant (cache hit)

**Commit:** `perf: cache repopulation + registry pass-through to avoid redundant loads`
**/clear after commit**

---

## Phase 5: Merge + Deploy + Browser Verify (15 min)

**Re-read this phase from `docs/prompts/session-101-prompt.md` after /clear.**

1. Merge FB-113 worktree branch: `./scripts/merge.sh session-101/fix-under-review-badge`
2. Run full test suite: `make test-fast`
3. Push + deploy: `git push origin main` then `railway up -d`
4. Browser verify with Claude Chrome — 7 specific checks:
   - [ ] CONFIRMED unnamed person page shows "Confirmed" badge (not "Under Review")
   - [ ] Enrichment panel: merge search appears BEFORE name input
   - [ ] GEDCOM search works in enrichment panel
   - [ ] Merge shows confirmation with face count, no auto-advance
   - [ ] Cross-community suggestion has "From Rhodes" badge
   - [ ] Person links from speed-run include admin context
   - [ ] Merge/similar feels faster (subjective)
5. Screenshots to `docs/screenshots/session-101/`
6. Run `/ux-review` skill on screenshots

**Commit:** `docs: session 101 browser verification — N/7 PASS`
**/clear after commit**

---

## Phase 6: Triage Sprint with Nolan (30 min)

**Re-read this phase from `docs/prompts/session-101-prompt.md` after /clear.**

Return to Fox Family speed-run: `/c/fox-family/admin/upload-review?mode=speed`

Nolan drives. Claude fixes issues in real-time. For each piece of feedback:
1. Can it be fixed in <10 min? → Fix, commit, push, deploy
2. Cannot be fixed quickly? → Create BACKLOG entry with specifics

Also try the batch cluster validation page: `/c/fox-family/admin/upload-review` (dashboard mode)
- Is it useful? Does it complement speed-run?
- Any issues with the grid view?

Document all feedback in `docs/feedback/2026-03-14-fox-triage-round2.md`

---

## Phase 7: Session Closeout (15 min)

**Re-read this phase from `docs/prompts/session-101-prompt.md` after /clear.**

1. Run `/session-review` skill — catch any gaps
2. Assessment: `docs/assessments/session-101-assessment.md`
3. Update CHANGELOG (v0.99.4 or v1.0.0?), ROADMAP, BACKLOG
4. Update `docs/session_context/session-100-master-status.md` with Session 101 results
5. Update `tasks/lessons.md` with any new lessons
6. Final commit with all harness docs

---

## Critical Rules

- **/clear between phases** — MANDATORY after every phase commit. This is the #1 repeated failure.
- **No data regressions** — every merge must go through `save_registry()`. Test merge paths.
- **Test before every commit** — targeted tests during dev, `make test-fast` before push.
- **Browser verify before declaring done** — Lesson 131.
- **Re-read phase from prompt file after /clear** — don't rely on memory.
- **Monitor test speed** — if tests start taking >3 min, investigate. Log timing.
- **Document subagent state before /clear** — branch names + commit hashes in session log.

## Acceptance Criteria

Session 101 is done when:
1. All 7 P1 feedback items (FB-100, 103, 104, 105, 106, 110, 113) are fixed and browser-verified
2. Performance measurably improved (log before/after timing for merge + suggestion)
3. Nolan completes at least one triage round with the improved UX
4. All tests pass (app + ML)
5. Session assessment filed with evidence
6. CHANGELOG, ROADMAP, BACKLOG updated
