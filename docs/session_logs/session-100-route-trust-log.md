# Session 100 Route Trust Log

## Summary
- **Slice:** community/public route trust follow-up
- **Goal:** stop public/share flows from leaking out of the active archive when
  the user is already operating in a community-scoped context.

## Triggered By
- Fox Family and Rhodes live dogfooding
- user reports that public/community pages still dropped into global Rhodes
  routes in ways that felt confusing and low-trust

## Files
- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [app/browse_routes.py](/Users/nolanfox/rhodesli/app/browse_routes.py)
- [tests/test_identify.py](/Users/nolanfox/rhodesli/tests/test_identify.py)
- [tests/test_inline_find_similar.py](/Users/nolanfox/rhodesli/tests/test_inline_find_similar.py)
- [tests/test_session_82e_features.py](/Users/nolanfox/rhodesli/tests/test_session_82e_features.py)
- [session-100-community-route-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-community-route-followup.md)

## What Changed
- community-scoped `/help` cards now link to community-scoped identify/profile pages
- match-confirmation “Explore the Archive” links now stay inside the current
  community
- public photo-card helpers now accept `nav_prefix`
- legacy inline similar panel now preserves community-scoped person/API links

## Verification
- `ruff check app/page_routes.py app/browse_routes.py tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py`
- `pytest tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py tests/test_find_similar_page.py tests/test_collections.py tests/test_public_photo_viewer.py -x -q`
  - `124 passed`

## Notes
- `data/identities.json` remains dirty from live app usage and stays out of this
  slice.
- This log is a bounded follow-up artifact because
  [session-100-fox-family-hotfix-log.md](/Users/nolanfox/rhodesli/docs/session_logs/session-100-fox-family-hotfix-log.md)
  is already at the harness line limit.

## Person Page Similar Follow-Up
- admin `Find Similar` on public person pages now opens the inline neighbors
  review panel instead of forcing a separate page transition
- community-scoped person pages keep the inline similar target inside the
  active archive
- verification:
  - `ruff check app/person_routes.py tests/test_public_person_page.py`
  - `pytest tests/test_public_person_page.py tests/test_find_similar_page.py tests/test_inline_find_similar.py -x -q`
    - `77 passed, 2 skipped`

## Photo Conflict Follow-Up
- public photo pages now flag overlapping face assignments as `Conflict`
  instead of presenting them as clean truths
- overlapping boxes now render `Needs review` overlays
- a photo-level conflict banner appears when the rendered boxes collide
- verification:
  - `ruff check app/page_routes.py tests/test_public_photo_viewer.py`
  - `pytest tests/test_public_photo_viewer.py tests/test_public_person_page.py tests/test_identify.py -x -q`
    - `99 passed, 2 skipped`

## Community HTMX Follow-Up
- shared workstation/admin helpers were still leaking to root Rhodes after HTMX
  re-renders because they emitted bare `/?section=...`, `/photo/...`,
  `/person/...`, and `/api/...` paths
- `app/main.py` now threads `nav_prefix` through section headers, triage bars,
  mini/expanded cards, skipped focus, neighbors/search panels, rename displays,
  and workstation photos
- `app/identity_routes.py` now preserves `nav_prefix` across focus/skip/merge,
  rename, notes, metadata, rejected, skip-hints, and photo-lightbox re-renders
- workstation photo filter controls and modal navigation now stay inside the
  active archive instead of snapping back to Rhodes
- files:
  - [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
  - [app/identity_routes.py](/Users/nolanfox/rhodesli/app/identity_routes.py)
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [tests/test_sidebar_community.py](/Users/nolanfox/rhodesli/tests/test_sidebar_community.py)
  - [session-100-community-htmx-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-community-htmx-followup.md)
- verification:
  - `python3 -m py_compile app/main.py app/identity_routes.py app/page_routes.py`
  - `pytest tests/test_sidebar_community.py tests/test_public_person_page.py tests/test_inline_find_similar.py tests/test_find_similar_page.py tests/test_skipped_focus.py -x -q`
    - `131 passed, 2 skipped`
  - `pytest tests/test_admin_dashboard.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_sequential_identify.py tests/test_collections.py -x -q`
    - `132 passed`

## Person/Photo Conflict Context Follow-Up
- full `/person/{id}` pages and the HTMX gallery partial now agree on disputed
  context instead of hiding it on one surface and showing it on another
- overlapping or disputed person-photo assignments now render `Needs review`
  plus a `Conflicting face assignment` hint on the person gallery item
- context-linked photo pages now show a photo-level warning banner when the
  selected person assignment overlaps another face or is already disputed
- files:
  - [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py)
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [tests/test_public_person_page.py](/Users/nolanfox/rhodesli/tests/test_public_person_page.py)
  - [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)
  - [session-100-person-photo-conflict-context-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-person-photo-conflict-context-followup.md)
- verification:
  - `python3 -m py_compile app/person_routes.py app/page_routes.py`
  - `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py -x -q`
    - `60 passed, 2 skipped`
  - `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_collections.py tests/test_inline_find_similar.py tests/test_find_similar_page.py -x -q`
    - `180 passed, 2 skipped`

## Photo Registry Alias Follow-Up
- photo provenance edits were failing on some live pages because the visible
  photo ID could load through the viewer/cache path while the editable
  `PhotoRegistry` did not recognize that same ID directly
- `resolve_photo_registry_photo_id()` now bridges cache/view IDs back to the
  canonical editable registry ID before collection/source/source-url updates
- the duplicate editable routes in both
  [page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py) and
  [photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py) were updated
  together so the live path and the legacy duplicate stay consistent
- files:
  - [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [app/photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py)
  - [tests/test_photo_provenance.py](/Users/nolanfox/rhodesli/tests/test_photo_provenance.py)
  - [session-100-photo-registry-alias-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-photo-registry-alias-followup.md)
- verification:
  - `python3 -m py_compile app/main.py app/page_routes.py`
  - `pytest tests/test_photo_provenance.py tests/test_public_photo_viewer.py tests/test_collections.py -x -q`
    - `61 passed`

## Root Landing E2E Alignment
- the critical-path browser test was still asserting the retired Rhodes-only
  landing CTA even though PRD-040 moved `/` to the neutral platform entry shell
- updated the e2e contract to assert the platform-root archive entry actions
  instead of the old `Start Exploring` expectation on `/`
- updated a timeline browser test that was also checking archive navigation on
  `/`; it now verifies the timeline link from the Rhodes archive surface where
  that navigation actually lives
- updated the legacy `tests/test_landing_about.py` expectations so Rhodes
  historical-copy assertions run against `/c/rhodes/` for anonymous users
  rather than the neutral platform root
- the e2e app-server fixture now sets `NO_ALBUMENTATIONS_UPDATE=1` so browser
  startup time is not inflated by Albumentations' external version check
- the same fixture now waits up to 30 seconds for a cold app start, matching
  the real startup envelope we observed during clean-worktree browser gates
- files:
  - [tests/e2e/test_critical_paths.py](/Users/nolanfox/rhodesli/tests/e2e/test_critical_paths.py)
  - [tests/e2e/test_timeline.py](/Users/nolanfox/rhodesli/tests/e2e/test_timeline.py)
  - [tests/e2e/conftest.py](/Users/nolanfox/rhodesli/tests/e2e/conftest.py)
  - [tests/test_landing_about.py](/Users/nolanfox/rhodesli/tests/test_landing_about.py)
- verification:
  - `pytest tests/e2e/test_critical_paths.py::test_landing_page_hero tests/e2e/test_critical_paths.py::test_landing_page_stats tests/e2e/test_critical_paths.py::test_landing_page_navigation tests/e2e/test_timeline.py::test_timeline_in_navigation -x -q`
    - re-run after fixture update pending

## Public Photos Route Prefix Follow-Up
- `/photos` was still trying to use `nav_prefix` without defining it, which
  made the discovery-layer browser suite fail and left archive-scoped photo
  browsing brittle
- the route now computes `nav_prefix` from `community_url_prefix()` and uses it
  consistently for:
  - photo-card detail links
  - lazy-load sentinel API URLs
  - filter-pill/search URLs
  - the page brand link
  - share/canonical URLs
- files:
  - [app/browse_routes.py](/Users/nolanfox/rhodesli/app/browse_routes.py)
  - [tests/test_public_browsing.py](/Users/nolanfox/rhodesli/tests/test_public_browsing.py)
- verification:
  - `pytest tests/test_public_browsing.py tests/e2e/test_discovery_layer.py::test_photo_card_shows_date_badge tests/e2e/test_discovery_layer.py::test_date_badge_confidence_styling -x -q`
    - `24 passed`
- the paired infinite-scroll endpoint `/api/photos/more` now mirrors the same
  community/nav-prefix logic, so lazy loading no longer falls back to bare
  photo links or bare `/api/...` continuation URLs
- additional files:
  - [tests/test_lazy_loading.py](/Users/nolanfox/rhodesli/tests/test_lazy_loading.py)

## Photo Modal Browser-Helper Stability
- the critical-path browser helper was timing out on the workstation photo modal
  path even though the page still emitted the expected HTMX + modal markup
- hardened the helper to scroll the first photo card into view, click it
  forcefully, and allow more time for the HTMX swap/unhide sequence
- files:
  - [tests/e2e/test_critical_paths.py](/Users/nolanfox/rhodesli/tests/e2e/test_critical_paths.py)
- verification:
  - targeted re-run pending after helper update

## Full-Suite Cache Isolation Cleanup
- the clean app-suite gate exposed a latent fixture-isolation bug in
  [tests/test_face_count_badge.py](/Users/nolanfox/rhodesli/tests/test_face_count_badge.py):
  the synthetic cache fixture reset `_photo_cache` and `_face_to_photo_cache`
  but not `_photo_registry_cache`
- when broader suites had already loaded the real registry, the synthetic test
  accidentally pulled real face-to-photo entries and failed with archive-sized
  counts instead of the expected 10 synthetic faces
- the fixture now clears and restores `_photo_registry_cache` alongside the
  other cache globals
- verification:
  - `pytest tests/test_public_browsing.py tests/test_face_count_badge.py -x -q`
    - `30 passed`

## Discovery-Layer Browser Timeout Alignment
- the provenance-style browser check timed out on cold photo-detail navigation
  even though the route itself returned quickly under direct request timing
- raised the discovery-layer Playwright `goto` timeout to 30 seconds so the
  test validates provenance styling instead of failing on cold subprocess
  navigation overhead
- files:
  - [tests/e2e/test_discovery_layer.py](/Users/nolanfox/rhodesli/tests/e2e/test_discovery_layer.py)
- verification:
  - targeted re-run pending after timeout alignment

## Clean-Suite Gate Follow-Through
- the clean worktree regression gate uncovered three remaining stale/isolated
  contracts after the Session 100 route work:
  - synthetic photo-source tests were leaking `_photo_registry_cache`
  - a timeline unit test still expected archive navigation on the neutral `/`
    platform root
  - the suggestion-lifecycle browser suite still used a 15 second admin-page
    `goto` timeout even after the broader browser hardening
- fixes:
  - [tests/test_photo_id_consistency.py](/Users/nolanfox/rhodesli/tests/test_photo_id_consistency.py)
    now clears/restores `_photo_registry_cache` in its synthetic cache fixture
  - [tests/test_photo_sort_controls.py](/Users/nolanfox/rhodesli/tests/test_photo_sort_controls.py)
    now resets `_photo_registry_cache` in the inbox-metadata fallback tests
  - [tests/test_timeline.py](/Users/nolanfox/rhodesli/tests/test_timeline.py)
    now asserts that `/` omits archive-only Timeline nav, matching PRD-040
  - [tests/e2e/test_suggestion_lifecycle.py](/Users/nolanfox/rhodesli/tests/e2e/test_suggestion_lifecycle.py)
    now uses a 30 second Playwright navigation timeout
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
    now gives the neutral platform root the same overflow-safe CSS baseline as
    the archive landing shell (`overflow-x: hidden`, `max-width: 100vw`,
    `box-sizing: border-box`, responsive images)
- verification:
  - clean worktree app suite:
    - `pytest tests/ -x -q`
    - `4167 passed, 21 skipped`
  - clean worktree ML suite:
    - `pytest rhodesli_ml/tests/ -x -q`
    - `588 passed, 2 skipped`

## Confirmed-People GEDCOM Sweep Pass
- the confirmed-people GEDCOM workflow already had a `tree_unlinked` filter, but
  the controls were easy to miss and did not explain the sweep well enough for
  real admin use
- improvements:
  - the confirmed filter pills now show counts:
    - `All (N)`
    - `Needs Tree (N)`
    - `Linked (N)`
  - the confirmed section subtitle now surfaces how many identified people still
    need family-tree links
  - admins now see a helper line explaining that `Needs Tree` is the fast GEDCOM
    sweep mode
  - confirmed person pages now expose a top-of-page shortcut to the GEDCOM
    section:
    - `Needs Tree Link` when unlinked
    - `Tree Linked` when already linked
- files:
  - [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
  - [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py)
  - [tests/test_ui_clarity.py](/Users/nolanfox/rhodesli/tests/test_ui_clarity.py)
  - [tests/test_public_person_page.py](/Users/nolanfox/rhodesli/tests/test_public_person_page.py)
- verification:
  - `pytest tests/test_ui_clarity.py tests/test_public_person_page.py -x -q`
    - `50 passed, 2 skipped`

## Person-to-Photo Trust Pass
- the Rhodes dogfooding examples showed that the photo page could technically be
  correct while still feeling wrong: users arriving from a person gallery had to
  infer whether the selected person was actually present, disputed, or missing
  by scanning overlays and face cards
- improvements:
  - context-linked photo pages now render an explicit person-context banner for
    all `identity_id` flows, not only conflict cases
  - the banner now distinguishes between:
    - person present and trusted
    - person present but disputed
    - person missing from the current face assignments
  - the current person's face card is promoted to the front of the people strip
    / grid and receives a dedicated `photo-current-person-card` marker
  - the banner includes a jump link back to the current person's face card when
    the person is present on the photo
- files:
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)
- verification:
  - `pytest tests/test_public_photo_viewer.py -x -q`
    - `23 passed`
  - `pytest tests/test_public_person_page.py tests/test_photo_navigation.py tests/test_identify.py -x -q`
    - `104 passed, 2 skipped`
  - `pytest tests/test_gedcom_routes.py tests/test_public_person_page.py::TestAdminControlsOnPersonPage -x -q`
    - `54 passed`
