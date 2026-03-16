# Session 107b — Community Middleware Audit + Approvals UX + Data Integrity

**Context:** docs/session_context/session-107b-context.md
**Priority:** P0 middleware audit, P1 approvals fixes, P2 approvals UX
**Predecessor:** Session 107 (data fix + sidebar count fix)

## Background

Session 107 fixed two James Henry Fields photos that were uploaded to Fox Family but ended up in Rhodes. The root cause: the upload route uses `request.state.community` from CommunityMiddleware, which defaults to `"rhodes"` when no `/c/{slug}/` prefix is in the URL. This is the **7th time** community scoping has caused a data issue. A systematic audit is overdue.

Additionally, the approvals system has multiple UX gaps reported by Nolan during triage.

**This session runs autonomously.** Every phase must:
- Plan before coding
- Write tests first (TDD)
- Commit atomically per phase
- Run `make test-fast` before every commit
- /clear between phases

**Safety rules:**
- No data loss. No registry mutations without save guards.
- No modifications to `core/neighbors.py` (FROZEN).
- All URL generation must use `community_url_prefix()`.
- Read existing code before modifying.

---

## Phase 0: Orient + Plan (10 min)

1. Set `.claude/current_session.txt` to `107b`
2. Read:
   - `docs/prompts/session-107-prompt.md` (predecessor findings)
   - `docs/session_context/session-107b-context.md` (detailed context)
   - `tasks/lessons.md`
3. Create session log + assessment stub
4. Commit scaffolding

/clear after committing.

---

## Phase 1: Community Middleware Audit (45 min)

**Problem:** CommunityMiddleware defaults to Rhodes when no `/c/{slug}/` prefix. Multiple routes that modify data use `request.state.community` without verifying it matches user intent. This has caused data in the wrong community 7+ times.

### Audit checklist
1. Grep ALL routes that write to Supabase with a community_id or community_slug parameter
2. For each, verify the community is either:
   - Explicitly passed by the user (form field, URL param)
   - Correctly derived from the URL prefix
   - NOT silently defaulting to Rhodes
3. Focus on:
   - `app/upload_routes.py` — photo upload community assignment
   - `app/match_facecompare_routes.py` — match decisions
   - `app/admin_routes.py` — admin actions
   - `app/identity_routes.py` — identity mutations
   - `app/page_routes.py` — annotation submissions
   - `app/engagement_routes.py` — community suggestions
4. Document every route that could silently default to wrong community
5. Fix: for data-modifying routes, require explicit community or validate against user context

### Tests
- Test: uploading from `/c/fox-family/upload` assigns to fox-family community
- Test: uploading from `/upload` (no community prefix) either fails or defaults correctly
- Test: annotation submission preserves community context

/clear after committing.

---

## Phase 2: Approvals Quick Fixes (30 min)

### Fix 1: Show submission timestamp
- Data already stored in annotation record as `submitted_at`
- Render it on each approval card using `_time_ago()` helper
- Test: approval card HTML contains timestamp

### Fix 2: Auto-confirm checkbox on approve
- Add "Also confirm this person?" checkbox to each approval card (default: checked)
- When checked + approve clicked, also call `registry.confirm_identity()`
- Test: approving with checkbox changes state to CONFIRMED

### Fix 3: Store annotation_id in rename history
- When `rename_identity()` is called from approval, pass the annotation_id
- Store it in the identity's history entry
- Test: identity history contains annotation reference after approval

### Fix 4: Person page shows suggestion provenance
- On person page, if the name came from an approved suggestion, show:
  "Name suggested by [email] on [date], approved by admin on [date]"
- If name was edited after approval, show edit history too
- Test: person page HTML contains provenance info for approved names

/clear after committing.

---

## Phase 3: Anonymous Pending Upload Cleanup (15 min)

**Problem:** Two anonymous Compare Upload entries (job IDs 8add8b91, b8de4b5f) from 2026-03-13 persist in `pending_uploads.json` on Railway after staging files were auto-cleaned.

### Fix
1. In startup cleanup code (~line 958 of app/main.py), after cleaning stale staging dirs:
2. Also mark pending_uploads.json entries as "expired" when:
   - Their staging directory no longer exists
   - They're older than 24 hours
3. Test: expired entries are marked and don't show on admin page

/clear after committing.

---

## Phase 4: BACKLOG Items for Approvals UX (10 min)

Log these to `docs/BACKLOG.md` with breadcrumbs:

| ID | Issue | Effort |
|----|-------|--------|
| APPROVAL-001 | Batch select checkboxes (port from pending uploads UX) | 1-2 hr |
| APPROVAL-002 | Email digest/batching for approval notifications | PRD needed |
| APPROVAL-003 | Person page full audit trail (all name changes with actor + timestamp) | 1 hr |
| APPROVAL-004 | Approvals page consistent UX with pending uploads (select, action bar) | 1-2 hr |

/clear after committing.

---

## Phase 5: Deploy + Browser Verify (15 min)

1. `make test-fast` — all pass
2. Deploy: `railway up`
3. Browser verify (Claude Chrome):
   - [ ] James Henry Fields photos show in Fox Family, not Rhodes
   - [ ] Sidebar shows correct approvals count (should be 12)
   - [ ] Approval cards show submission timestamps
   - [ ] Approving a suggestion confirms the person (if checkbox checked)
   - [ ] Anonymous pending uploads auto-expired or manually cleaned
4. Screenshots to `docs/screenshots/session-107b/`

---

## Phase 6: Assessment + Close (10 min)

1. Re-read this prompt
2. Write assessment with PASS/FAIL per phase
3. Update session log, ROADMAP, CHANGELOG, BACKLOG
4. Final commit

---

## Key Files
- `app/main.py` — CommunityMiddleware (~line 471), `_compute_sidebar_counts()` (~line 3231), startup cleanup (~line 958)
- `app/upload_routes.py` — upload community assignment (~line 554)
- `app/admin_routes.py` — /admin/approvals page, approval handlers
- `app/page_routes.py` — annotation submission
- `app/supabase_data.py` — Supabase data layer
- `docs/session_context/session-107b-context.md` — full investigation findings

## Non-Goals
- No ML pipeline changes
- No full approvals UX redesign (that's a PRD)
- No email batching implementation (that's a PRD)
