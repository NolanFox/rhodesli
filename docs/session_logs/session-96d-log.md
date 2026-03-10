# Session 96d Log — Fix Fox Family to Usable State
Started: 2026-03-10
Prompt: docs/prompts/session-96d-prompt.md

## Phase Checklist
- [x] Act 0: Orient — read context, set current_session.txt
- [x] Act 1: Sidebar Counts + Proposals (COMMUNITY-007, COMMUNITY-010) — proposals.json read + community filter
- [x] Act 2: Bottom Nav + Admin Headers (COMMUNITY-008, COMMUNITY-013) — subagent: community_url_prefix on all nav links + admin headers show community name
- [x] Act 3: Upload Review + GEDCOM in Sidebar (COMMUNITY-009) — already present in sidebar (lines 4527-4538)
- [x] Act 4: Cluster Review Community Scoping (COMMUNITY-011) — proposals filtered by community identity set
- [x] Act 5: To Review Proposal Match Info (COMMUNITY-012) — badge shows "Matches [Name] (XX%)" with compute_face_confidence
- [x] Act 6: Cross-Community Content Indicator (COMMUNITY-014) — _cross_community_badge() on neighbor_card + discovery cards
- [x] Act 7: Browser Verification — all nav links verified with /c/fox-family/ prefix, Rhodes pages still use bare URLs
- [x] Act 8: Session Wrap

## Additional Fixes (user feedback)
- Photo filename display for admin on photo page
- Face crop responsive sizing: w-16 h-16 sm:w-20 sm:h-20 (was w-20 h-20, too small on mobile)
- Name truncation removed from neighbor cards (was cutting off "Unidentified Person 2...")
- Fixed 3 pre-existing test failures: cluster review community filtering, community landing page mock level, neighbor card size assertions

## User Feedback (captured during session)

### CI Email Spam
- GitHub Actions test.yml failing on every push to main, generating email notifications
- Root cause: Pre-existing test failures (circular imports, wrong assertions, missing mocks)
- Fixed: 6 pre-existing test failures resolved in Act 1 commit
- Remaining: Some xdist race conditions (pass in isolation, fail under parallel)

### Fox Family Clustering Concern
- User observation: "none of the photos of betty in the Charles Fox Photo Collection are actually clustering"
- Evidence: Similar panel shows Betty matches at distances 1.06-1.10 (Tier 2 = suggestions)
- proposals.json HAS 4 Betty matches (distances 1.005-1.045), 30 Roland Fox, 1 Ray Franco
- Root cause: proposals exist but UI shows "0 Proposals" — COMMUNITY-010 (fixed in Act 1)
- Additional context: Vida's photos clustered because they went through the full triage workflow
- Fox photos haven't been triaged yet — the Upload Review page needs community scoping (COMMUNITY-011)
- Betty distances (1.005-1.045) are Tier 2 (suggestions) not Tier 1 (<0.85 auto-merge)
- This is expected behavior — admin needs to review and accept/reject via Upload Review

### UX Regression Feedback
- Face crop sizes too small (w-20 h-20 = 80px) — fixed to responsive w-16 h-16 sm:w-20 sm:h-20
- Name truncation cutting off identity names — removed truncate class
- Photo filename not visible on photo page — added admin-only filename display
- No cross-community indicator — added "From [Community Name]" badges

### Process Note
- User requested harness compliance: logging, breadcrumbing, feedback collection
- All feedback captured in this log with breadcrumbs to BACKLOG items

## Additional Fix (Act 7)
- Nav links in _public_nav_links() now use community_url_prefix(community_slug)
- All callers in page_routes, browse_routes, person_routes, notification_routes, event_routes updated
- Tools routes (compare, estimate) remain community-agnostic with bare URLs
- Verified in browser: Fox Family nav links → /c/fox-family/*, Rhodes nav links → /*

## Verification Gate
- [x] Nav links use /c/fox-family/ prefix — PASS (browser verified)
- [x] Fox Family landing page shows correct counts — PASS
- [x] Sidebar shows Proposals count from proposals.json — PASS
- [x] Upload Review page accessible and shows proposals — PASS
- [x] Discoveries page shows cross-community badges — PASS
- [x] Photo page shows filename for admin — PASS
- [x] Rhodes pages still work with bare URLs — PASS
- [x] All 141 community-related tests pass
- [x] Git clean, all changes committed and pushed
- [x] Assessment file exists
- [ ] BACKLOG updated (doing now)

## Known Issues (pre-existing, not regressions)
- test_my_contributions_page_accessible: fails when run in full suite (test ordering issue)
- test_landing_page: cascade failure from above
- e2e test_decade_filter: "c. 1910s" photo appearing in 1900s filter
- Internal photo/person links don't include community prefix (requires larger refactor — BACKLOG)
