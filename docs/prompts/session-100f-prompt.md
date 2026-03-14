# Session 100f — Cluster Validation & Enrichment Overhaul

## Context
Session 100e was the Fox Family triage sprint. Nolan triaged ~7 clusters in speed-run mode and logged 21 feedback items (FB-1 through FB-21). Two critical bugs were fixed and deployed: (1) blocking Supabase sync moved to background thread, (2) confirm-all now sets state=CONFIRMED (was silently doing nothing for INBOX clusters). Person 2986 (Charles Fox, 44 faces) was confirmed and verified persistent after refresh.

**Key insight from triage (FB-13):** The speed-run in its current form is a cluster validation tool, not a triage tool. For pure "is this a valid cluster?" validation, a batch-select approach (Google Photos style) is 10x faster. The speed-run becomes valuable only when it's an enrichment flow — name, merge, GEDCOM link, suggested matches.

**Critical UX problems (FB-14-20):** Counter goes DOWN (confusing), no visual feedback on actions, accidental double-Y possible, undo not discoverable, can't see previous actions, can't verify false positives without source photo, unknown persons have no clear workflow guidance. Performance still too slow — needs optimistic UI with pre-fetched next card.

**Design for real users (FB-21):** Must work for Claude Benatar (non-technical contributor) AND power users starting their own community archives. Self-evident workflows, not power-user-only keyboard shortcuts.

**Fox Family status:** ~215 INBOX clusters remaining, ~7 confirmed in 100e.

**IMPORTANT: Use PRD/SDD approach.** Write a PRD before implementing. Think deeply about UX — don't build for the sake of building. Build what's valuable and helps collect information efficiently. Every feature should be explainable to a non-technical user.

**Predecessor:** `docs/session_logs/session-100e-log.md`, `docs/session_context/session-100-master-status.md`

## CRITICAL: Context Management — Subagent Architecture
The orchestrator (you) MUST NOT write code directly. For every implementation phase:
1. Read only the phase section from this prompt
2. Delegate ALL implementation to a subagent (Agent tool) with a focused brief
3. The subagent does: code changes, tests, commit
4. Orchestrator verifies: reads the commit, checks test output, updates session log
5. /clear IMMEDIATELY after each phase before reading the next one

This keeps the orchestrator context lean. Each subagent gets fresh context with only what it needs. The orchestrator is a coordinator, not a builder.

**If you notice context is above 50%, STOP. Commit, log, /clear. No exceptions.**

## Rate Limit Safety
If you hit rate limits:
1. **DO NOT retry in a loop.** This has caused endless loops that lose all progress.
2. Commit whatever is done so far.
3. Write progress to `docs/session_logs/session-100f-log.md` with exactly where you stopped.
4. Wait 60 seconds, then try ONE more time. If still rate-limited, STOP and leave the log for Nolan.
5. Never let a hook or retry mechanism run more than 3 times without human input.

## Phase 0: Orient (5 min)
- Read `tasks/lessons.md`
- Read `docs/session_context/session-100-master-status.md`
- Verify deploy is healthy: `/health` check
- Set `.claude/current_session.txt` to `100f`
- Read `app/cluster_review_routes.py` — understand current speed-run implementation
- Read `app/identity_routes.py` — understand `log_user_action()` call pattern

## Phase 1: Data Safety — Audit Trail for Speed-Run Actions (P0, 20 min)
**Every admin action must be reconstructable: who, what, when, how (speed-run vs manual), identity_id, face count.**

Current state: `log_user_action()` is called in `identity_routes.py` and `page_routes.py` but NOT in `cluster_review_routes.py`. All speed-run actions (confirm-all, reject-all, skip, dismiss, undo) are unlogged.

Tasks:
1. Add `log_user_action()` calls to ALL speed-run action handlers in `app/cluster_review_routes.py`:
   - `/api/cluster-review/confirm-all` — log SPEED_RUN_CONFIRM with identity_id, face_count, state_before, state_after
   - `/api/cluster-review/reject-all` — log SPEED_RUN_REJECT with identity_id, face_count
   - Skip action — log SPEED_RUN_SKIP with identity_id
   - Dismiss action — log SPEED_RUN_DISMISS with identity_id
   - Undo action — log SPEED_RUN_UNDO with identity_id, original_action
2. Include `mode=speed-run` in all log entries so manual vs speed-run actions are distinguishable
3. Include the admin email from the session
4. Write tests: verify each action type produces a log entry with correct fields
5. Commit, push, deploy

## Phase 2: Batch Cluster Validation UX (P1, 60 min)
**Google Photos-style batch select on INBOX identities — the fastest path for pure cluster validation.**

This is the primary new feature. It replaces speed-run as the default validation flow for large backlogs.

**BEFORE IMPLEMENTING:** Write a PRD at `docs/prds/040_batch_cluster_validation.md` with user flows, acceptance criteria, and out-of-scope. Think about the UX deeply — this should be self-evident to a non-technical user like Claude Benatar. Commit the PRD before writing code.

### Route: `/c/{slug}/admin/cluster-batch` (or similar)

### UX Flow:
1. Page loads showing a grid of INBOX identity cards, sorted by face count descending
2. Each card shows: representative face crop, face count badge, identity ID
3. "Select All" button at top selects all visible cards
4. Admin deselects any bad clusters (mixed faces, garbage detections)
5. "Confirm Selected (N)" button mass-confirms all selected identities
6. Filter controls: face count threshold (2+, 5+, 10+), community filter

### Implementation:
1. New route in `cluster_review_routes.py` — GET handler renders the batch grid
2. POST handler for `/api/cluster-review/batch-confirm` — accepts list of identity_ids
3. Each confirmation: move all candidate_ids to anchor_ids, set state=CONFIRMED, log via `log_user_action()`
4. Client-side: checkbox state via vanilla JS or hyperscript, Select All toggle, count badge on confirm button
5. After batch confirm: show summary (N confirmed, face counts) with link to continue or go to naming flow
6. Sorting: face count descending by default, with option for alphabetical
7. Pagination or infinite scroll for large sets (222 clusters)

### Cards should show:
- Top face crop (largest/best quality), sized generously (not tiny thumbnails — FB-12)
- Face count badge
- Checkbox overlay (top-left corner)
- Identity ID (small text)

### Tests:
- Test batch confirm route accepts identity_id list and confirms all
- Test state persistence (INBOX → CONFIRMED with anchor_ids populated)
- Test log_user_action called for each confirmed identity
- Test face count filter works
- Test community scoping

## Phase 3: Enriched Speed-Run (P1, 45 min)
**Enhance the existing speed-run to be an enrichment flow, not just cluster validation.**

This phase transforms speed-run from "confirm/reject" into "confirm + name + merge + link". Only do this AFTER Phase 2 is complete and committed.

### 3A: Show ALL faces (FB-1, 15 min)
- Remove the "+36 more" overflow — show all faces in a scrollable grid
- Face crops should be larger (FB-12) — at least 80x80px, ideally 100x100px
- Grid should fill the card width, wrapping naturally
- Each face crop is clickable → opens source photo in new tab (FB-2)

### 3B: Post-confirm enrichment panel (FB-3, FB-5, 20 min)
After pressing Y (confirm), instead of immediately advancing:
1. Show inline name input field with cursor focused
2. Below name field: "Search & Merge" typeahead — search existing confirmed identities
3. Below that: "Link to GEDCOM" button with search
4. Below that: suggested matches from existing confirmed identities ("Looks like Person X, 87%") — use the existing neighbors/similarity infrastructure
5. "Done" button (or Enter) saves name and advances to next cluster
6. If user presses Y again without entering a name, advance anyway (don't block)

### 3C: Recent actions sidebar (FB-10, 10 min)
- Collapsible sidebar or panel showing last 10 actions
- Each entry: action type (confirmed/rejected/skipped), identity snippet (face crop + ID), timestamp
- Undo button on each entry (reuses existing undo infrastructure)

### Tests:
- Test that all faces render (no overflow cap)
- Test post-confirm enrichment panel renders with name input
- Test name save persists
- Test merge search returns results
- Test recent actions list populates

## Phase 4: UX Polish (P2, 15 min)

### 4A: Face crop sizing (FB-12)
- Audit all face crop sizes in cluster review pages
- Minimum 80x80px for grid views, 100x100px for speed-run
- Remove excessive padding/margin around crops

### 4B: Progress counter fix (FB-14)
- Replace "X of N reviewed" with cumulative stats: "5 confirmed · 2 skipped · 1 rejected · 214 remaining"
- N should never change during a session — snapshot the total on page load

### 4C: Undo visibility (FB-19)
- Show undo with context: "Undo: Confirmed Person 2986 — 44 faces (Z)"
- Make undo visually prominent, not just a small button at the bottom

### 4D: Workflow guide (FB-4, FB-7, FB-16)
- Add brief instructional text at top of speed-run page:
  > "Review each cluster. Press Y to confirm (same person), N to reject (mixed faces), S to skip, D to dismiss. After confirming, you can name the person and link to GEDCOM records."
- Add similar text at top of batch validation page:
  > "Select valid clusters and confirm them in bulk. Deselect any clusters with mixed faces. Use face count filters to focus on high-confidence clusters first."

### 4C: Optimistic UI + Debounce (FB-9, FB-17, FB-18, FB-20)
- Debounce Y key to prevent double-fire (300ms cooldown)
- **Optimistic UI pattern:** On Y press, IMMEDIATELY: (1) show "Confirmed!" flash animation, (2) slide current card out, (3) show pre-fetched next card. Server processes the confirm in background. If server fails, show error and revert.
- Pre-fetch: When a card renders, also fetch the NEXT card via hidden HTMX request so it's ready instantly
- Visual lock during processing: disable keyboard for 300ms after any action to prevent double-fire

## Phase 5: Session Review — MANDATORY (20 min)
**Run `/session-review` skill.** This is non-negotiable. It:
1. Re-reads THIS prompt file
2. Verifies every phase was completed with evidence
3. Flags gaps, superficial work, silent deferrals
4. Spawns an auto-fix subagent for anything fixable
5. Writes `docs/assessments/session-100f-assessment.md`

The stop hook blocks session end until the assessment exists. Do NOT skip this.

## Phase 6: Testing & Session Closeout (15 min)

### Tests:
- All new routes have tests (batch confirm, enriched speed-run panels)
- `log_user_action` called for every speed-run action type
- Confirm-all state persistence (INBOX → CONFIRMED, anchor_ids populated)
- Batch confirm with multiple identity_ids
- Community scoping on batch page

### Harness:
- Update BACKLOG.md with all new items from FB-1 through FB-13
- Update ROADMAP.md with session 100f status
- Update `docs/session_context/session-100-master-status.md`
- Write assessment: `docs/assessments/session-100f-assessment.md`
- Lessons learned from 100e triage feedback

### Merge:
- If egress fix branch `worktree-agent-a93855ab` was not merged in 100e, merge it now:
  `./scripts/merge.sh worktree-agent-a93855ab`

## Known Issues Going In
- UX-063: Progress counter instability (count changes during triage) — P2, existing BACKLOG
- CROP-001: Some Fox crops show "?" (missing from R2) — P2, cosmetic fallback works
- COMMUNITY-015: Internal links missing community prefix — P2, not blocking
- proposals.json stale (March 10, only 17 proposals) — operational, regen after batch confirm
- PRD-038 longitudinal reranker built but rollout gate closed (AD-220) — not wired into speed-run, blocked on more Fox-family labels + slice gate data
- FB-6: Age-based cluster splitting — ML problem, PRD-038 Phase 5 scope, not this session
- FB-11: PRD-038 not active — rollout gates need more labeled data to graduate, not this session

## Success Criteria
1. **Data safety:** Every speed-run action (confirm-all, reject-all, skip, dismiss, undo) produces a `log_user_action()` entry with identity_id, face_count, mode=speed-run, admin email
2. **Batch validation ships:** `/c/fox-family/admin/cluster-batch` renders INBOX grid, Select All works, batch confirm persists state=CONFIRMED with anchor_ids
3. **Enriched speed-run:** All faces visible (no overflow cap), post-confirm name input renders, merge search returns results
4. **Y key debounce:** No double-fire on rapid Y presses
5. **Tests pass:** `make test-fast` green, new tests cover all new routes and actions
6. **Deploy verified:** Production health check passes, batch validation page loads in browser
7. **BACKLOG updated:** All 13 FB items from 100e have BACKLOG entries or are marked fixed
