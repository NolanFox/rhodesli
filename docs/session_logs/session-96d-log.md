# Session 96d Log — Fix Fox Family to Usable State
Started: 2026-03-10
Prompt: docs/prompts/session-96d-prompt.md

## Phase Checklist
- [x] Act 0: Orient — read context, set current_session.txt
- [x] Act 1: Sidebar Counts + Proposals (COMMUNITY-007, COMMUNITY-010) — proposals.json read + community filter
- [ ] Act 2: Bottom Nav + Admin Headers (COMMUNITY-008, COMMUNITY-013)
- [ ] Act 3: Upload Review + GEDCOM in Sidebar (COMMUNITY-009)
- [ ] Act 4: Cluster Review Community Scoping (COMMUNITY-011)
- [ ] Act 5: To Review Proposal Match Info (COMMUNITY-012)
- [ ] Act 6: Cross-Community Content Indicator (COMMUNITY-014)
- [ ] Act 7: Browser Verification
- [ ] Act 8: Session Wrap

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

### Process Note
- User requested harness compliance: logging, breadcrumbing, feedback collection
- All feedback captured in this log with breadcrumbs to BACKLOG items

## Verification Gate
- [ ] All 12 browser checks PASS
- [ ] ALL tests pass (excluding xdist race conditions)
- [ ] Git clean, all changes committed and pushed
- [ ] Assessment file exists with evidence
- [ ] BACKLOG updated
