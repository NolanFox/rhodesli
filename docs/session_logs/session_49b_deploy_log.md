# Session 49B-Deploy Log

## Date: 2026-02-20

## Phase 0: COMPLETE
- Git status: clean, up to date with origin/main
- Commits already pushed (0 ahead of origin)
- Session log created

## Phase 1: COMPLETE — Production Verification
Audit commits were already pushed to origin/main. All fixes verified on production:

| Fix | Test | Result |
|-----|------|--------|
| Health check | curl /health | 200 OK |
| H1 (mobile nav) | MCP Playwright 375px viewport | PASS — hamburger button visible, opens slide-out menu with all 9 nav links |
| M1 (styled 404) | Navigate to /nonexistent-test-page | PASS — "Page Not Found - Rhodesli" title, styled page with "Explore the Archive" link |
| M3 (DEVNULL fix) | Code deployed — requires interactive session to verify approve handler | Deployed, not testable without admin auth |
| M4 (favicon) | Inline SVG data URI in HTML head | PASS — browser no longer requests /favicon.ico |
| Sort routing | curl /?section=to_review&sort_by=faces&view=browse | PASS — 200 |

### Compare Deep Check
- File upload: 6.5KB photo selected, no preview feedback (M2, deferred)
- Search Archive: 3 faces detected, 20 matches, 93% top match (Strong Match)
- Results in viewport: YES, no scrolling needed
- Processing feedback: Results appeared fast for small file. For large files (10-28s), no loading indicator was visible between click and results. This is the SSE epic use case (AD-121).
- Compare UX: fully functional on production

## Phase 2: COMPLETE — Admin Routes
Admin routes tested (unauthenticated):
- /admin/pending: 401 (correct — requires admin)
- /admin/review/birth-years: 401 (correct)
- /upload: 401 (correct — requires login)

Cannot test admin content rendering without session credentials.
Admin route functionality requires the interactive session with Nolan logged in.

60 admin-protected routes identified, all returning 401 for unauthenticated access.

## Phase 3: COMPLETE — Harness Documentation
- Post-deploy hook updated: `.claude/hooks/post-deploy-log-check.sh` (Playwright reminder added)
- HD-014 added: Every deploy MUST include production Playwright verification
- AD-122 added: Silent failures are bugs — general principle (3 instances: AD-120, triage Bug 1, audit M3)
- CLAUDE.md updated: Session Operations #3 (Playwright after deploy), ML loading line (DEVNULL ban)
- BACKLOG already had deferred items (M2, L1-L3, test ordering bug) from audit session
- No remaining DEVNULL instances in app/ (only comments about NOT using it)
- CLAUDE.md: 78 lines (under 80 limit)
- HARNESS_DECISIONS.md: 278 lines (under 300 limit)

## Phase 4: [pending]
