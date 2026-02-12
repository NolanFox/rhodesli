# UX Audit — Session 18

**Date:** 2026-02-11
**Method:** Code-level trace of 7 user stories through routes, templates, HTMX targets
**Data:** 370 identities (46 confirmed, 223 skipped, 73 inbox, 26 proposed)

---

## Story 1: "I just arrived and want to help identify people"

**Path:** Landing → Needs Help → pick face → see suggestions → compare → decide

**What works:**
- Landing page has "View All Photos" and progress dashboard
- Needs Help section (to_review) has Focus mode with 6-tier actionability sort
- Proposal banners show ML match confidence with human-readable labels
- Neighbors auto-load via HTMX when proposals exist (line 1891)

**Issues:**
- **P1: Focus mode only shows items with proposals.** Items without proposals (tier 5) appear last. No "cold start" guidance for items without ML matches.
- **P2: No "Needs Help" direct entry from landing page.** User must understand sidebar navigation.

---

## Story 2: "I think I recognize someone — let me find them"

**Path:** Search → find card → view photos → full photo context

**What works:**
- Search endpoint with surname variant expansion (13 groups in surname_variants.json)
- Client-side fuzzy search with Levenshtein distance
- Search results link to identity cards via hash fragment scroll

**Issues:**
- **P2: Search → Photo has no direct path.** Search results link to identity cards only, not photo context. User must go card → face → photo.
- **P1: Sidebar search may break layout.** HTMX target for sidebar search returns content that could displace right-side rendering if target mismatches.

---

## Story 3: "I'm comparing two faces and need context"

**Path:** Compare modal (from AI suggestions AND Find Similar) → toggle → zoom → context

**What works:**
- Both entry points hit same endpoint: `/api/identity/{id}/compare/{neighbor_id}` (line 3317)
- Face/Photo toggle with `?view=faces` and `?view=photos` params
- Identity names are clickable links that navigate to cards (lines 8200-8210)
- Compare modal closes via hyperscript before navigation

**Issues:**
- **P1: Compare modal → Photo context is missing.** No "View Photo" button in Compare modal. User sees crops/photos but can't open full photo with all face overlays, collection info, etc.
- **P2: Compare modal doesn't preserve triage_filter.** Identity name links use `/?section={section}&current={id}` without filter param. Closing Compare and clicking a name loses filter context.
- **P2: Compare modal size.** Currently max-w-5xl. Could benefit from 90vw x 90vh for better photo comparison.

---

## Story 4: "I merged faces but don't know the name yet"

**Path:** Merge → see result → find later

**What works:**
- Merge endpoint works, updates identity state
- Post-merge suggestions render inline (ML-005)

**Issues:**
- **P1: No post-merge guidance.** After merge, card updates but no banner says "These are now grouped. Add a name?" User may not realize merging without naming is encouraged.
- **P2: Merged-unnamed identities not visually distinct.** "Unidentified Person 123" with 3 faces looks the same as single-face inbox items.

---

## Story 5: "I want to see all photos of this person"

**Path:** Identity card → View Photos → lightbox → navigation

**What works:**
- Lightbox with keyboard (left/right), mouse arrows, touch swipe (line 5783-5803)
- Identity-based photo navigation auto-computes prev/next from face list (line 6133-6153)
- Event delegation pattern (data-action) stable across HTMX swaps
- All entry points: identity card, expanded card, face grid all open lightbox

**Issues:**
- **P2: Compare modal has no "View Photo" link to lightbox.** From Compare, user cannot jump to full photo context.

---

## Story 6: "I uploaded new photos and want to process them"

**Path:** Pending Uploads → approve → new faces in Inbox

**What works:**
- Upload endpoint exists with admin auth
- Staged upload lifecycle (STAGED → APPROVED → PROCESSED)

**Issues:**
- **P2: Upload processing is script-based.** No in-app Approve/Process buttons. Admin must run scripts locally.

---

## Story 7: "I need to fix a mistake — wrong face attached"

**Path:** Find identity → detach → see move → re-assign

**What works:**
- Detach endpoint exists with HTMX response
- Face moves to inbox on detach

**Issues:**
- **P2: Detach confirmation message may not be clear.** Should say "Face moved to Inbox for re-review."

---

## Cross-Story: Navigation Matrix

| From → To | Identity Card | Photo Context | Compare Modal | Find Similar |
|-----------|:---:|:---:|:---:|:---:|
| Identity Card | — | OK (face click) | OK (Compare btn) | OK (Find Similar) |
| Photo Context | OK (overlay click) | — | — | — |
| Compare Modal | OK (name link) | **MISSING** | — | — |
| Find Similar | OK (name link) | OK (View Photo) | OK (Compare btn) | — |
| Search Results | OK (name link) | **MISSING** | OK (Compare btn) | OK (Find Similar) |
| Focus Mode | OK | OK (face click) | OK (inline) | OK |

**Missing paths (P1):** Compare Modal → Photo Context, Search → Photo Context

---

## Priority Summary

| ID | Severity | Description |
|----|----------|-------------|
| UX-001 | P1 | Compare modal → Photo context link missing |
| UX-002 | P1 | Post-merge guidance banner missing |
| UX-003 | P1 | Sidebar search may break right-side rendering |
| UX-004 | P2 | Search → Photo has no direct path |
| UX-005 | P2 | Compare modal doesn't preserve triage_filter |
| UX-006 | P2 | Compare modal could be larger (90vw x 90vh) |
| UX-007 | P2 | Merged-unnamed identities not visually distinct |
| UX-008 | P2 | Upload processing is script-only |
| UX-009 | P2 | Detach confirmation messaging |
| UX-010 | P2 | No "Needs Help" direct CTA from landing |
