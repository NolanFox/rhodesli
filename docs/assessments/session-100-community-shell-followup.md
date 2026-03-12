# Session 100 Community Shell Follow-Up

**Date:** 2026-03-12  
**Author:** Codex

## Purpose
Document the Session 100 continuation slice that fixed community-context leaks
across public/admin shells and repaired collection sharing so live archive links
feel coherent and preview correctly in messaging apps.

## Trigger
Live user feedback after the earlier Session 100 merge showed that:
- Fox Family public flows could still drop back into Rhodes/root routes.
- Collection links were poor share objects in Messages because the collection
  page had no `og:image`.
- Community-scoped workstation cards still had root-linked actions.
- Upload Review / proposal clustering remained too hard to find from the real
  Roland/Fox workflow.

## Implemented
1. Shared public shell is now community-aware.
   - `_public_page_nav()` now preserves the active community for the brand link
     and admin bar.
   - Notifications and Events now pass `community_slug` into the shared public
     nav so they no longer silently snap back to Rhodes.

2. Public People and Collections surfaces stay inside the active archive.
   - People index, collection index, and collection detail pages now use
     community-prefixed internal links and share URLs.
   - Collection breadcrumbs, photo links, person links, timeline links, and
     upload links stay in the current archive.

3. Collection sharing now has a real social preview.
   - Collection detail pages now emit `og:image` using the first collection
     photo.
   - Share URLs are canonicalized with the active community prefix.

4. Shared workstation identity cards now preserve community context.
   - `identity_card()` accepts `nav_prefix`.
   - Profile, Tree, Similar, photo modal HTMX loads, face pagination, triage
     actions, and review-action buttons now stay archive-scoped when rendered
     in a community workstation.

5. Proposal review is easier to discover from the real admin path.
   - `identity_card()` now surfaces `Proposals (N)` when the identity is a
     clustering target.
   - This gives admins a direct bridge from the confirmed/workstation card to
     `admin/upload-review`.

6. HTMX re-render paths preserve community context after actions.
   - Identity mutation routes now pass `nav_prefix` back into re-rendered cards
     so confirm/reject/skip/merge/detach/force-state flows do not regress to
     root links after the first click.

## Verification
- `ruff check app/main.py app/page_routes.py app/browse_routes.py app/person_routes.py app/identity_routes.py app/notification_routes.py app/event_routes.py tests/test_sidebar_community.py tests/test_collections.py tests/test_find_similar_page.py tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_admin_dashboard.py tests/test_cluster_review_routes.py`
- `pytest tests/test_sidebar_community.py tests/test_collections.py tests/test_find_similar_page.py tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_admin_dashboard.py tests/test_cluster_review_routes.py tests/test_photo_navigation.py tests/test_internal_photo_links.py -x -q`
  - `176 passed, 2 skipped`
- Additional targeted gates already green in this continuation:
  - `pytest tests/test_notifications.py tests/test_life_events.py tests/test_ux_fixes_session92.py -x -q`
    - `95 passed`
- Clean-worktree full-suite verification on commit `02af23f` caught one real
  regression:
  - `/identity/{id}/reset` referenced `request` without accepting it
  - fixed before deploy by threading `request` into the handler

## What This Does Not Claim
This slice does **not** complete all of PRD-040.

Still open:
- neutral root / platform entry
- fuller multi-community bootstrap flows
- true batch cluster-confirmation queue
- deeper “ignore noise” cluster tooling
- final face-card harmonization across every surface

## Attribution
- User: live Fox Family screenshots, Wayne share-preview feedback, and the
  insistence that community/admin/public context stay coherent.
- Antigravity: earlier workflow critique and mockup direction that made proposal
  discoverability and batch-review gaps explicit.
- Codex: implementation, shared-helper fixes, regression tests, and this audit.
