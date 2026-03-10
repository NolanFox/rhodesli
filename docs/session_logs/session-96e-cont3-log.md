# Session 96e-cont3 Log

Started: 2026-03-10
Prompt: docs/prompts/session-96e-cont3-prompt.md

## Phase Checklist
- [x] Act 1: Browser Verify All Fixes (partial — deploy pending for code fixes)
- [x] Act 2: Fix Remaining Issues (5 of 7 bugs fixed)
- [ ] Act 3: Session Wrap (assessment + log done, CHANGELOG/ROADMAP deferred to cont4)

## Work Completed

### Commit de6f3c2 — Community Scoping + Duplicate Filter
1. Proposals sidebar: `_compute_sidebar_counts(registry, community=community)` in admin_routes.py (2 locations)
2. Proposals API: `/api/proposed-matches?community_slug=X` filtering in engagement_routes.py
3. Discoveries Help Identify: `community_identity_ids` filter in `_build_help_identify_section()`
4. Duplicate face filter: Neighbors with dist < 0.1 AND co-occurrence filtered in identity_routes.py
5. Name consistency: "Person NNNN" in neighbor_card (main.py:8031)
6. Split script: `scripts/split_oversized_clusters.py`

### Commit a550687 — Upload 500 Fix
- Root cause: PostHog `capture()` on Railway crashes with TypeError
- Fix: try/except wrapper in `posthog_capture()` function

### Supabase Data Operations (not committed — direct DB operations)
- Upserted 3006 local identities to Supabase
- Deleted 1149 orphan identities from single-linkage era
- Verified 26 annotations unaffected

## User Feedback Captured
- Upload needs explicit "Upload" button with file list preview (not auto-upload)
- Discoveries on Rhodes shows 0 + Fox photos leaking (fixed)
- Proposals page community scoping broken (fixed)
- Upload silently fails (fixed — PostHog crash)
- All bugs are P0 severity per user
