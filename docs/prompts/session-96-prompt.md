# Session 96 Prompt — Community Data Scoping Hotfix

**Type:** Reactive hotfix (user-reported production bugs)
**Origin:** Nolan screenshots of Fox Family community pages showing Rhodes data
**Date:** 2026-03-09

---

## Problem
After switching to Fox Family community (`/c/fox-family/`), multiple pages show Rhodes community data instead of Fox Family's empty state:
1. Photos section: 297 Rhodes photos visible
2. Sidebar counts: "People 71, Photos 297" (Rhodes numbers)
3. Admin bar: links hardcoded to `/admin/section/...`
4. Merge conflict in sidebar docstring from Session 95b worktree merge
5. About page: Rhodes-specific content

## Task
Fix community data scoping so Fox Family pages show only Fox Family data. Fix admin bar to be community-aware. Resolve merge conflict.

## Acceptance Criteria
- [ ] Fox Family photos page shows 0 photos (not 297)
- [ ] Fox Family sidebar shows 0 people, 0 photos
- [ ] Admin bar links use community URL prefix
- [ ] No merge conflict markers in codebase
- [ ] All unit tests pass
- [ ] Committed and pushed

## Verification
- Deploy to production
- Browser-verify `/c/fox-family/?section=photos` shows empty state
- Browser-verify `/c/fox-family/upload` sidebar shows 0/0
