# Session 111c — Proposals Page Rebuild + Remaining Triage Fixes

## Context
@docs/session_context/session-111b-context.md
@docs/feedback/session-111-feedback.md

Session 111b fixed 80+ community prefix gaps and 3 UX items. But the Proposals page (422 items) is completely broken — no face thumbnails, no confirm/reject actions, raw ML distance numbers, wrong community header. This was missed during browser verification. Additionally, ~20 P0/P1/P2 feedback items from Session 111 triage remain unaddressed.

## Pre-Requisites
1. Read `tasks/lessons.md` + `tasks/todo.md`
2. Read `docs/feedback/session-111-feedback.md` — all FB items
3. Set `.claude/current_session.txt` to `111c`
4. Set `.claude/session_mode.txt` to `implementation`

---

## Phase 0: Orient (5 min)

1. `git log --oneline -5` — confirm Session 111b commits on main
2. `make test-fast` — confirm baseline passes
3. Browser-check Proposals page at `/c/fox-family/admin/proposals` — confirm current broken state
4. Read the proposals route code to understand current rendering

---

## Phase 1: Proposals Page Rebuild (P0 — 60 min)

### Current State (BROKEN)
- No face thumbnails — just text names
- No confirm/reject/merge action buttons
- Raw `Dist: 0.32` shown instead of human-readable confidence
- Header shows "Rhodesli" instead of community name
- Same person appears as duplicate entries
- No batch actions
- "View Source" / "View Target" are useless text links
- Overall UX is inconsistent with the rest of the app (New Matches, Discoveries)

### Target State
Match the quality of the New Matches page and Discoveries page. Each proposal card should show:
1. **Source face thumbnail** (left) — the unidentified person
2. **Target face thumbnail** (right) — the suggested match
3. **Confidence badge** — "67% match" (not "Dist: 0.32") using calibrated scores
4. **Source photo context** — collection name, "Also in photo: [other people]"
5. **Action buttons**: Confirm (merge source into target), Not Same (reject), Compare (side-by-side)
6. **Community header** — "Fox Family Archive" not "Rhodesli"
7. **Deduplication** — group proposals by source identity, don't show 4 copies

### Implementation Notes
- Look at how `_build_discovery_card()` in `discoveries_routes.py` renders cards — use the same pattern
- Look at how `_speed_run_cluster_card()` renders thumbnails — same crop resolution
- The proposals data comes from `proposals.json` AND `ml_proposals` Supabase table — read both
- Distance → confidence conversion: use `_calibrated_confidence()` or the pattern in `_confidence_tier()`
- Community scoping: filter proposals by community identity set (same as discoveries)
- Use `resolve_face_image_url()` for thumbnails
- The route is likely in `app/page_routes.py` or `app/admin_routes.py` — find `proposals` route

### Tests
- Proposals page returns 200 with face thumbnails present
- Proposals are community-scoped (Fox Family shows only Fox proposals)
- Confidence shown as percentage, not raw distance
- Action buttons present (Confirm, Not Same, Compare)

---

## Phase 2: Remaining P0 Fixes (30 min)

### FB-036/037: Speed Loop tagging doesn't persist (P0 — RECURRING)
- BUG-001 was marked fixed in Session 102 but user reports it's broken again
- Root cause: tag assignment endpoint silently fails
- Verify on production: go to Speed Loop, tag a face, refresh, check if tag persists
- If still broken: investigate the save path in identity_routes.py tag endpoints

### FB-054/058: Thumbnail mismatch in Similar Identities (P0 → P1)
- Clarified as crop selection inconsistency — different faces shown in list vs detail
- Fix: use `get_best_face_id()` consistently in both Similar Identities list AND person page hero
- File: `app/main.py` neighbor_card rendering

### FB-039/056/061/062: Multi-merge always shows failures (P0 UX)
- Co-occurrence blocker silently rejects merges without per-identity feedback
- Fix: return per-identity success/failure with reason in merge response
- Show: "Charles Fox — merged (3 faces)" / "Person 3124 — blocked: faces in same photo"
- File: `app/identity_routes.py` bulk-merge handler

---

## Phase 3: P1 Fixes (30 min)

### FB-025: Speed-run latency (P1 — performance)
- Root causes identified in memory:
  1. `save_registry()` writes ALL 3,433 identities to Supabase on every confirm
  2. `_get_confirmed_identity_suggestions()` iterates all identities
  3. `_get_speed_run_clusters()` recomputed on every request
- Quick win: lazy-load enrichment panel via HTMX (instant perceived confirm)
- File: `app/cluster_review_routes.py`

### FB-027: Auto-advance after merge in speed-run (P1)
- After clicking Merge on a suggestion, should auto-advance to next cluster
- Currently requires manual "Go to next cluster" click
- Fix: merge handler returns next cluster card via HTMX swap
- File: `app/cluster_review_routes.py` merge handler

### FB-030: Cluster count resets/doesn't increment (P1)
- Speed-run progress counter not persisting across page loads
- Fix: store count in server-side session or query param, not client-side only
- File: `app/cluster_review_routes.py`

### FB-031: Face grid layout distorted on gear click (P1)
- Face grid overflows when expanded on identity card
- Fix: remove `min-w-[150px]`, use responsive grid
- File: `app/main.py` face_card rendering

### FB-040: Stale card remains after merge (P1)
- After merge, the source identity card should be removed via OOB swap
- File: `app/identity_routes.py` merge handler

### FB-051: Photo filename search not working (P1 — RECURRING)
- Verify on production: search for a photo filename in sidebar
- If broken: check `/api/search` endpoint for photo search code path

### FB-055: Select All checkbox doesn't work (P1 — RECURRING)
- Master checkbox toggles but doesn't check individual boxes
- Fix: JS event delegation for select-all pattern
- File: `app/main.py` neighbors_sidebar

### FB-042: Help Identify section purpose unclear (P1)
- Overlaps with New Matches and Discoveries — unclear distinction
- Fix: add explanatory subtitle or merge into Discoveries. Minimum: clarify purpose text.
- File: `app/main.py` or `app/page_routes.py` Help Identify section

### FB-043: Help Identify face crops too small to compare (P1)
- "WHO IS THIS?" and "BEST MATCH" crops too zoomed — no surrounding context
- Fix: show larger face regions or include photo context inline
- File: Help Identify rendering

### FB-048: No direct path from face card to person page in tagging view (P1)
- In Speed Loop tagging, identity name shown but not linked
- Fix: add "View Person" link in face tag popup
- File: `app/page_routes.py` or `app/identity_routes.py` tag panel

### FB-049: Sentry circular import error (P1)
- `AttributeError: partially initialized module 'app.engagement_routes'`
- Fix: refactor circular import or use lazy import pattern
- File: `app/main.py` line ~10580 engagement_routes reference

### FB-060: No Compare button on Discovery cards (P1)
- From Discovery tab, no direct "Compare" button — user had to manually construct URL
- Fix: add Compare button to discovery cards linking to `/tools/compare?face_id=...&person_id=...`
- File: `app/discoveries_routes.py` `_build_discovery_card()`

---

## Phase 4: P2 Fixes (20 min — as time allows)

### FB-028: Merge toast doesn't persist to next screen (P2)
- Toast disappears on HTMX swap — add persistence via session or OOB

### FB-035: Bad cluster quality — threshold too loose (P2)
- Log to ML-102, no code fix this session — needs labeled data

### FB-038: "View More" resets checkboxes (P2)
- Use `hx-swap="beforeend"` instead of innerHTML for pagination

### FB-044: Best match duplicated in Similar Identities list (P2)
- Exclude the best match identity from the Similar Identities query

### FB-045: Help Identify Focus mode UX differs from other Focus modes (P2)
- Unify layout — use same card template as New Matches Focus

### FB-046: "More Matches" labeling unclear (P2)
- Rename to "Other Possible Matches" with clearer relationship text

### FB-053: Identity ID format inconsistent (numbers vs hex) (P2)
- Assign sequential display numbers to all unnamed identities

---

## Phase 5: Deploy + THOROUGH Browser Verify (20 min)

1. `git push origin main`
2. Wait for deploy, verify with `mcp__railway-mcp-server__list-deployments`
3. **MANDATORY: Check EVERY admin surface on production:**
   - [ ] `/c/fox-family/` — landing page loads, community header correct
   - [ ] `/c/fox-family/admin/proposals` — **MUST show face thumbnails, actions, confidence %**
   - [ ] New Matches → click a person → verify links
   - [ ] Discoveries → verify loading skeleton → content loads
   - [ ] Help Identify → verify it loads
   - [ ] People → verify community-scoped
   - [ ] Photos → verify loads
   - [ ] Compare → verify loads
   - [ ] Upload Review → verify loads
   - [ ] Approvals → verify loads
   - [ ] Speed-run → tag a face → verify persistence
4. Screenshots to `docs/screenshots/session-111c/`

---

## Phase 6: Harness Outputs (10 min)

1. **Assessment:** `docs/assessments/session-111c-assessment.md`
2. **Feedback file:** Update `docs/feedback/session-111-feedback.md` — mark FIXED items
3. **BACKLOG:** Update status for all resolved items
4. **ROADMAP:** Update version, session entry in Recently Completed
5. **CHANGELOG:** Session 111c entry
6. **Session log:** `docs/session_logs/session-111c-log.md`
7. **Verify:** `git log origin/main..HEAD` is empty (Lesson 148)

---

## Verification Checklist (before declaring done)

- [ ] Proposals page shows face thumbnails, confidence %, and action buttons
- [ ] Proposals are community-scoped
- [ ] No duplicate proposal entries for same source identity
- [ ] All tests pass
- [ ] EVERY admin sidebar section checked on production
- [ ] Speed Loop tagging verified persistent on production
- [ ] Multi-merge shows per-identity success/failure reasons
- [ ] Deployed and pushed
- [ ] Assessment written with screenshot evidence for EACH admin surface
- [ ] CHANGELOG, ROADMAP, BACKLOG all updated
- [ ] `git log origin/main..HEAD` is empty
