# Session 100c: Platform Reliability + Fox Family Cluster Review

**Context:** docs/session_context/session-100c-context.md
**Predecessor:** Session 100b-cont3

## Phase 0: Orient (3 min)

1. Set `.claude/current_session.txt` to `100c`
2. Read `tasks/lessons.md` + `tasks/todo.md`
3. Read `docs/session_context/session-100c-context.md`
4. `git log --oneline -10` to confirm clean state
5. Confirm tests pass: `source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ --timeout=120`

## Phase 1: Platform Reliability — Fix Supabase Production Connection (P0)

**Goal:** Production app must read from Supabase, not JSON fallback.

### Investigation
1. Check Railway deploy logs: `mcp__railway-mcp-server__get-logs` — filter for "supabase", "postgres", "DATA_SOURCE", "connection", "error"
2. Read app/main.py startup path for `DATA_SOURCE == "postgres"` — trace the exact code path
3. Check what "Supabase connection skipped" means in the health endpoint
4. Check Dockerfile for supabase-py installation
5. Check if `load_registry_from_postgres()` exists and what it does

### Fix
- If import error: add missing dependency to Dockerfile/requirements.txt
- If env var issue: fix the env var name/format
- If connection error: fix the connection string
- If logic bug: fix the conditional

### Verify
- Deploy to Railway
- `curl https://rhodesli.nolanandrewfox.com/health` — should NOT say "connection skipped"
- Verify Yaacov Jacob Franco shows correct face (inbox_b6d2995b52da, not inbox_65f110834b6e)
- Verify face cycling arrows visible on identity cards

### Fallback (if Supabase fix is complex)
- Push corrected identities.json to Railway volume via sync API
- Document Supabase fix needed in BACKLOG
- Continue to Phase 2

**Commit after Phase 1. /clear.**

## Phase 2: Cluster Review UX — Batch-First Design (PRD)

**Goal:** Write a focused PRD for the batch cluster review UX.

Create `docs/prds/039_batch_cluster_review.md`:

### User Flow (the "speed run")
1. Admin opens `/c/fox-family/admin/upload-review`
2. Page shows clusters sorted by size (biggest groups first)
3. Each cluster card shows: face thumbnails (up to 6), match confidence, suggested name
4. Admin can:
   - **Confirm cluster** → all faces merge into the suggested identity (or new identity)
   - **Split cluster** → separate wrongly grouped faces
   - **Dismiss cluster** → mark as noise/unresolvable (hides from queue)
   - **Skip** → move to next without action
5. After each action, next cluster auto-loads (no page reload)
6. Progress bar shows "47 of 312 clusters reviewed"
7. Keyboard shortcuts: Y=confirm, N=skip, D=dismiss, S=split

### Data Model
- No new tables needed — uses existing proposals.json + identities registry
- Add `reviewed_at` timestamp to proposals for progress tracking
- Add `cluster_action` field: confirmed|dismissed|split|skipped

### Acceptance Criteria
1. Cluster review page loads in <2s for Fox Family (1122 proposals)
2. Confirm action merges all cluster faces into target identity
3. Dismiss action hides cluster from review queue
4. Auto-advance works without page reload
5. Progress counter accurate
6. Community-scoped (Fox Family sees only Fox proposals)
7. Keyboard shortcuts work

**Commit PRD. /clear.**

## Phase 3: Implement Batch Cluster Review

**Goal:** Build the batch-first cluster review UX from the Phase 2 PRD.

### Implementation Plan
1. Modify `cluster_review_routes.py`:
   - Add batch confirm endpoint: `POST /admin/cluster/{cluster_id}/confirm-all`
   - Add dismiss endpoint: `POST /admin/cluster/{cluster_id}/dismiss`
   - Add progress endpoint: `GET /admin/cluster-review/progress`
2. Update the Upload Review page template:
   - Cluster cards with confirm/dismiss/skip buttons
   - HTMX auto-advance (hx-swap on action → loads next cluster)
   - Progress bar component
   - Keyboard shortcut JS
3. Add tests:
   - Batch confirm merges all faces correctly
   - Dismiss hides from future review
   - Progress counter accuracy
   - Community scoping preserved

### Test
```bash
source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ --timeout=120
```

**Commit after Phase 3. /clear.**

## Phase 4: Browser Verify + Production Deploy

1. Deploy: `git push origin main` (or `railway deploy` if GitHub deploys broken)
2. Wait for deploy completion
3. Open Chrome browser:
   - Navigate to `https://rhodesli.nolanandrewfox.com/c/fox-family/admin/upload-review`
   - Verify cluster review loads with Fox Family proposals
   - Test confirm/dismiss/skip actions
   - Verify auto-advance works
   - Check progress counter
   - Screenshot evidence
4. Also verify Rhodes platform:
   - Navigate to `https://rhodesli.nolanandrewfox.com/`
   - Verify landing page loads
   - Check a person page loads correctly
   - Verify Yaacov Franco face (if Supabase fixed)

**Commit screenshots + session log update. /clear.**

## Phase 5: Assessment + Docs

1. Write `docs/assessments/session-100c-assessment.md`
2. Update `docs/session_logs/session-100c-log.md`
3. Update ROADMAP.md:
   - Mark PRD037-004 as complete (if wired)
   - Add session 100c to Recently Completed
4. Update BACKLOG.md with any new items discovered
5. Update CHANGELOG.md
6. Final commit and push

## Verification Gate
- [ ] Supabase connection working OR fallback deployed with BACKLOG entry
- [ ] Cluster review page loads for Fox Family
- [ ] Batch confirm works (at least 1 cluster confirmed in production)
- [ ] Dismiss works
- [ ] Auto-advance works
- [ ] All tests pass (app + ML)
- [ ] Assessment file exists
- [ ] Session log exists
- [ ] ROADMAP updated
- [ ] Screenshots saved
