# PRD-052: Community Routing Safety — Sharing-Ready Hardening

**Author:** Nolan Fox + Claude
**Date:** 2026-03-18
**Status:** Ready for Review
**Session:** 115
**Blocks:** Wider external sharing of Rhodesli

## Problem Statement

Rhodesli's community middleware defaults all non-prefixed URLs to the Rhodes community. While Session 100 added a neutral root landing page and `is_community_explicit()` guards exist, there is no comprehensive verification that ALL data-modifying routes are protected. Community routing bugs have been the #1 recurring regression category (Sessions 96c, 96d, 100, 111, 111b — 80+ prefix fixes). Before sharing externally, we need confidence that:

1. No data-modification route silently assigns to Rhodes without explicit community context
2. All community-scoped pages filter correctly
3. Test coverage prevents future regressions

**Who is affected:** External users visiting the site for the first time, members of non-Rhodes communities (Fox Family), and future communities. An accidental upload to the wrong community is a data integrity issue that undermines trust.

## User Flows

### Flow 1: External Visitor Arrives at Root
1. User navigates to `rhodesli.nolanandrewfox.com`
2. Sees neutral platform landing with community cards
3. Clicks "Enter Archive" for a specific community
4. Enters `/c/{slug}/` scoped experience
5. **All subsequent navigation stays within `/c/{slug}/`**

### Flow 2: External User Uses Tools
1. User visits `/tools/estimate` (community-agnostic)
2. Uploads photo for date estimation
3. Gets result — NO community assignment happens
4. If they click "Explore Archive" → directed to community selector, not Rhodes

### Flow 3: Upload on Non-Explicit Route (THE BUG)
1. User bookmarks `/upload` (no `/c/` prefix)
2. Middleware defaults to `community_slug="rhodes"`
3. `is_community_explicit()` returns False
4. **Upload handler MUST check this and redirect or prompt for community**
5. Photo MUST NOT silently go to Rhodes

### Flow 4: Shared Link Without Prefix
1. Admin shares link `/person/abc123` (missing `/c/rhodes/` prefix)
2. Recipient sees Rhodes data (correct if it's a Rhodes person)
3. Recipient clicks around — navigation should add prefix or stay neutral
4. **No data modification should be possible without explicit community context**

## Acceptance Criteria

1. **Every POST/PUT/DELETE route that modifies data** calls `is_community_explicit()` or requires admin auth (admin is implicitly Rhodes-scoped today)
2. **Upload route** returns error or redirect when `is_community_explicit()` is False and user is not admin
3. **Annotation submission** requires explicit community context
4. **All internal navigation links** use community prefix (existing regression test `test_community_prefix_audit.py` catches these)
5. **New tests** cover: upload on non-explicit route, annotation on non-explicit route, platform root for anonymous, admin operations without prefix
6. **No regressions** in existing community-scoped pages (browse, people, person detail, proposals, cluster review)

## Data Model Changes

None — no schema changes. This is a routing/guard hardening.

## Technical Constraints

- `is_community_explicit()` is the canonical guard — all new checks must use it
- Admin operations are currently Rhodes-scoped by convention (single admin) — this is acceptable for now
- API endpoints (`/api/`) skip middleware by design — this is correct
- HTMX endpoints must include `/c/{slug}` prefix in `hx-post`/`hx-get` URLs

## Out of Scope

- Upload form community dropdown (WORKSPACE-001)
- Community discovery page (WORKSPACE-005)
- Personal archive auto-creation (WORKSPACE-001)
- Multi-admin community permissions (WORKSPACE-006)

## Priority Order

1. Upload route hardening (highest risk — data pollution)
2. Annotation submission hardening
3. Comprehensive test coverage
4. Audit of all POST routes
5. Documentation of community routing architecture

## Breadcrumbs

- BACKLOG: COMMUNITY-017
- Related: COMMUNITY-015 (link scoping, mostly fixed Session 111b)
- Related: WORKSPACE-001, WORKSPACE-005, WORKSPACE-006 (future)
- Lessons: 109, 112, 113 (community middleware recurring issues)
- Test: `tests/test_community_prefix_audit.py` (Session 111b regression test)
