# Session 127 Assessment — Accessibility + Polish + Codex Audit

## Shipped

### Phase 0: Orient + Test Fixes
- [x] `test_confidence_tier_styles` fixed — stale "blue" assertion → "indigo" (Session 126 sweep)
- [x] `test_confirmed_anchors_in_face_to_photo` fixed — inbox orphans warn, non-inbox fail
- [x] SQL indexes: DEFERRED — `exec_sql` RPC doesn't exist on Supabase. Needs manual SQL Editor.
- **Evidence**: 3397 passed, 0 failures

### Phase 1: Accessibility + Touch Targets (3 worktree subagents)
- [x] **Subagent A — Touch Targets**: 10 badges in cluster_review_routes.py upgraded from `py-0.5` → `py-1`. Engagement pagination `px-2 py-1` → `px-3 py-1.5`. 9 tests.
- [x] **Subagent B — SVG Aria Labels**: 33 aria attributes added across main.py, discoveries_routes.py, tools_routes.py. `aria-hidden="true"` on decorative SVGs, `aria-label` on icon-only buttons. 28 tests.
- [x] **Subagent C — UX Quick Wins**: Button order confirmed correct (Focus|View All|Match). `_confidence_tier_label()` added showing Strong/Good/Possible/Weak match badges next to distance numbers. 15 tests.
- **Evidence**: 3448 passed after merges

### Phase 2: Person Page Polish (2 worktree subagents)
- [x] **Subagent D — Person Page CTA**: "Can you help?" CTA for CONFIRMED people with unknown birth/death/place. Merge confirmation gate for CONFIRMED people (inline warning, not JS dialog). 14 tests.
- [x] **Subagent E — Face Crop Fallback**: Global JS error handler intercepts broken crop images, replaces with SVG silhouette placeholder. Zero-touch — covers ALL crop images without modifying individual Img() calls. 13 tests.
- **Evidence**: 3473 passed after merges

### Phase 3: Security + Accessibility Audit
- [-] Running as background subagent
- Audit prompt written to `docs/prompts/session-127-codex-audit-prompt.md`

### Phase 4: Deploy + Verify
- [x] Deploy SUCCESS — Dockerfile builder, commit 08b7fbe
- [x] Health: 200, all systems ready (1660 identities, 968 photos)
- [x] Key pages: landing 200, compare 200, estimate 200, 404 correct, discoveries 401 (auth)
- [x] Crop fallback global handler present in production HTML
- [x] Aria labels present on nav elements

## Deferred
- SQL indexes: `exec_sql` RPC function doesn't exist on Supabase. BACKLOG OPS-126-001 remains open.
- Antigravity branch: Not created yet — no session-127/antigravity-polish branch exists. BACKLOG.

## Red Flags
- [LOW] aria-hidden attributes only visible in admin view (public page shows aria-label on nav only) — this is expected since admin SVGs render conditionally
- [LOW] 2 flaky xdist tests remain (test_photo_cache_faces_are_filtered, test_admin_overlay_css_has_min_width) — pass in isolation, fail occasionally under parallel. Module-level state mutation.

## Test Summary
- Baseline: 3397 tests, 4 failures, 1 error
- Final: 3473 tests, 0 failures (76 new tests added)
- New test files: test_touch_targets.py, test_aria_labels.py, test_ux_quick_wins_127.py, test_person_page_cta.py, test_crop_fallback.py

## Next Session Should Verify
1. SQL indexes — create via Supabase SQL Editor manually
2. Antigravity visual polish on browse_routes.py and estimate_routes.py
3. Audit findings triage (if any P0/P1 security issues found)
4. Flaky xdist test root cause (module-level state in parallel workers)
