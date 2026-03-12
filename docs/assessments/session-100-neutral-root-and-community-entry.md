# Session 100 Neutral Root And Community Entry

**Date:** 2026-03-12  
**Author:** Codex

## Purpose
Close the biggest still-open PRD-040 gap after the Fox/performance recovery:
`/` must become a neutral platform entry, and archive landing pages must guide
first-time visitors toward real contribution paths instead of dead ends.

## Implemented
1. Root `/` is now a neutral platform entry for anonymous visitors.
   - No more silent Rhodes default at the platform root.
   - Root now lists explicit archive choices with archive-scoped entry links.
   - Rhodes remains available as an explicit public demo path via `/c/rhodes/`.

2. Explicit archive entry remains concrete.
   - `/c/rhodes/` still renders the Rhodes archive landing.
   - `/c/{slug}/` for non-Rhodes archives still renders archive-specific landing
     pages for anonymous visitors.

3. Community landing pages now have an active contribution surface.
   - Added a visible contribution widget with:
     - `Help Identify Faces`
     - `Browse Photos`
     - `People`
     - `Share or Upload Photos`
   - The widget uses community-prefixed routes, so archive context survives the
     handoff.

4. Community middleware now records whether the request used an explicit
   `/c/{slug}` prefix.
   - This lets the app distinguish neutral `/` from explicit `/c/rhodes/`.

5. Community-aware Help page cleanup.
   - Empty-state browse links and canonical tags now preserve the active
     community prefix.

## Why This Matters
- It directly addresses `COMMUNITY-017`.
- It makes archive choice explicit for adoption and trust.
- It improves `COMMUNITY-001` / `UX-121` style discoverability without
  requiring a full self-serve onboarding system.

## Verification
- `ruff check app/main.py app/page_routes.py tests/test_landing.py tests/test_community_infra.py tests/test_empty_states.py tests/test_og_meta_tags.py`
- `pytest tests/test_landing.py tests/test_community_infra.py tests/test_empty_states.py tests/test_og_meta_tags.py -x -q`
  - `77 passed`
- `pytest tests/test_smoke.py tests/test_design_audit.py tests/test_collections.py tests/test_sidebar_community.py -x -q`
  - `81 passed`

## Not Claimed
- This does not complete the whole community bootstrap story.
- It does not solve the Fox clustering-quality problem.
- It does not make mobile swipe ergonomics best-in-class yet.

## Attribution
- User: pushed the explicit requirement that `/` stop defaulting to Rhodes and
  that community/public/admin boundaries stay sensible.
- Antigravity: earlier critique that a neutral root must not become a dead-end
  lobby.
- Codex: route implementation, contribution-shell implementation, tests, and
  this assessment.
