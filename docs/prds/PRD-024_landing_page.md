# PRD-024: Landing Page Refresh

**Status:** In Progress (Session 56)
**Priority:** P1
**Owner:** Session 56

## Problem
The landing page is the first thing anyone sees when the Rhodesli URL is shared. It needs to immediately communicate what the archive is, show live data proving it's real, and provide clear paths to explore.

## User Flows
1. **First-time visitor** lands on `/` → sees hero with live stats → scrolls to feature cards → clicks into Browse Photos or People
2. **Returning visitor** lands on `/` → clicks "Continue Reviewing" (if logged in) or explores via feature cards
3. **Interviewer** lands on `/` → sees professional archive with ML-powered features → clicks Compare to try face matching

## Acceptance Criteria
- [ ] Hero section with live stats (photo count, identity count from data files)
- [x] Feature entry point cards (2x3 grid: Photos, People, Map, Timeline, Tree, Compare)
- [x] Identification progress bar (confirmed vs. awaiting)
- [x] Mystery faces section with "Help Identify" CTA
- [x] How It Works section (3-step explanation)
- [ ] Mobile-first responsive layout (works at 375px)
- [ ] All numbers computed dynamically from data files (never hardcoded)
- [ ] Browser verification at desktop + mobile widths

## Out of Scope
- Admin dashboard redesign
- SSE upload UX
- Face Compare standalone app

## Design Reference
See `docs/session_context/session_56_planning_context.md` for full design direction.
