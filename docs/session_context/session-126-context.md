# Session 126 Context — Polish Sprint + Codex Audit + Delight

**Predecessor:** [Session 125 Context](session-125-context.md)
**UX Review:** Session 125 UX review found 9 P2 items (5 fixed) and 16 P3 items

## Goal

Three tracks: (1) fix remaining issues from Session 125, (2) Codex audit cycle, (3) Antigravity delight pass. Ship a polished, delightful app.

## Outstanding from Session 125

### SQL Indexes (Codex #5)
- `idx_photo_communities_community_id` and `idx_identity_communities_community_id`
- Cannot create via PostgREST API or direct psycopg2 (DNS resolution fails from local)
- **Try from Railway**: The app has DATABASE_URL on Railway — could execute via a startup migration or admin endpoint
- Alternative: Create a `/api/admin/run-migrations` endpoint that executes DDL

### Flaky Tests (16 ordering-dependent failures)
- Tests pass individually but fail in full suite
- Known failing: test_share_download.py (3 tests), test_face_count_badge.py, others
- Root cause: module-level state not reset between test files
- Fix: Add proper teardown/fixtures or use pytest-randomly to surface ordering deps

### Speed-Run reviewed_ids (FB-161) — End-to-End Wiring
- Server-side implemented: `_speed_run_next_card(reviewed_ids=...)` and skip endpoint accepts parameter
- Client-side NOT wired: JS needs to accumulate reviewed_ids and pass through button hx-post URLs
- Location: `app/cluster_review_routes.py` speed-run JS block (~line 900-1000)

### P3 UX Items from Review (16 items)

**Landing Page:**
1. Sidebar zero-count items (Discoveries 0) should be dimmed or hidden
2. Top bar stat pills: "TO REVIEW" vs "PROPOSALS" labeling ambiguity
3. UUID fragments in "Unidentified Person efb4d153" display names
4. Focus/View All/Match button ordering — primary action should be leftmost
5. Raw ML metrics (distance, gap) shown without confidence tier labels
6. Compare/Merge/Not Same buttons below 44px mobile touch targets

**Person Page:**
7. Born/Died/From "Unknown" — no community contribution CTA for confirmed people
8. Merge search box shown for CONFIRMED people without friction gate

**Compare Tool:**
9. Tools subnav links have zero padding (tap targets ~20px)
10. "Compare against all archive" is muted secondary — should be primary CTA

**404 Page:**
11. Nav shows only "Rhodesli" — add Photos/People links
12. Add "Go back" secondary link

**People Grid:**
13. Subtitle shows only confirmed count — add "awaiting identification" count
14. Share link is too subtle for a growth vector
15. No fallback for low-quality face crops in grid cards

**Cross-cutting:**
16. `py-1.5 text-xs rounded-full` chip pattern still below 44px in some places

## Codex Audit Scope

Run Codex as READ-ONLY reviewer of final deployed state. Focus areas:
- Visual consistency across all route files
- Component patterns that differ between pages
- CSS class inconsistencies (mixed blue/indigo remnants)
- Missing hover states or transitions
- Accessibility gaps (contrast, aria labels, screen reader)

## Antigravity Delight Scope

Antigravity should create visually delightful, modern elements:
- **Loading states**: Skeleton loaders with subtle shimmer animations
- **Micro-interactions**: Smooth transitions on confirm/reject/skip actions
- **Photo gallery**: Masonry layout or lightbox improvements on person pages
- **Empty states**: Illustrated empty states instead of plain text
- **Onboarding**: First-visit welcome state for new users
- **Typography**: Serif headings for editorial feel (the app already uses font-serif in places)

Constraint: CSS/template ONLY. No logic, data, or auth changes. Own page_routes.py and person_routes.py only.

## Breadcrumbs
- Session 125 assessment: `docs/assessments/session-125-assessment.md`
- UX review findings: In Session 125 conversation (not persisted to file — TODO)
- P2 fixes already applied: avatar rounded-2xl, touch targets, contrast
- Antigravity constraints: `memory/feedback_antigravity_constraints.md`
