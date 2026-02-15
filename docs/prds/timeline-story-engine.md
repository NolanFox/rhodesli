# PRD: Timeline Story Engine

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Approved
**Session:** 30

---

## Problem Statement

Rhodesli has 271 photos with ML-estimated dates spanning 1900–2020, but users can only browse them in a flat grid. There's no way to see the visual arc of a family's history or understand how photos relate to the historical events that shaped the Rhodes Jewish community — the 1938 racial laws, the 1944 deportation, post-war immigration. Family members visiting the site can filter by decade but can't experience the story chronologically.

## Who This Is For

- **Family members** (primary): See their family's visual story across generations, with historical context
- **Researchers**: Understand the timeline of the Rhodes Jewish diaspora through photographs
- **Admin**: Verify date estimates by seeing photos in chronological context

## User Flows

### Flow 1: Browse Full Timeline
1. User clicks "Timeline" in sidebar navigation
2. User sees a vertical timeline with decade markers (1900s, 1910s, ...)
3. Photos are positioned by their estimated year, grouped into decade sections
4. Historical context events appear inline between photos (distinct visual style)
5. Each photo card shows: thumbnail, date badge, confidence interval bar, caption
6. User scrolls through the full chronological story

### Flow 2: Filter by Person
1. User selects a person from the dropdown filter at top of timeline
2. Timeline redraws showing only photos containing that person
3. If the person has a birth_year, each card shows an age badge ("Age ~25")
4. Story header updates: "Leon Capeluto's Life in Photos"
5. Historical context events remain visible for temporal anchoring

### Flow 3: Filter by Year Range
1. User arrives via /timeline?start=1920&end=1950
2. Timeline shows only that range with appropriate decade markers
3. Works as deep link from /photos decade pills

### Flow 4: Share a Filtered View
1. User clicks "Share This Story" button
2. Current URL (with all active filters) is copied to clipboard
3. Toast confirms "Link copied!"
4. Opening the URL in a new tab loads the same filtered view

## Acceptance Criteria (Playwright Tests)

```
TEST 1: /timeline route loads and shows timeline structure
  - GET /timeline returns 200
  - Page contains vertical timeline line element
  - Page contains at least one decade marker

TEST 2: Photo cards appear on timeline
  - GET /timeline shows photo cards with thumbnails
  - Cards have date badges

TEST 3: Historical context events appear
  - Timeline includes at least one context event card
  - Context events have distinct styling (different border/background)

TEST 4: Decade markers are present and ordered
  - Timeline has multiple decade markers
  - Markers are in chronological order

TEST 5: Person filter dropdown exists
  - Filter dropdown is present
  - Dropdown contains person names

TEST 6: Person filter works via HTMX
  - Selecting a person filters the timeline
  - Only photos containing that person appear

TEST 7: Year range filter works
  - /timeline?start=1920&end=1950 shows only that range
  - Photos outside range are excluded

TEST 8: Confidence interval bars on cards
  - Photo cards include a date range bar
  - Bar reflects the probable_range from date labels

TEST 9: Age overlay when person filtered
  - With person filter active and birth_year available
  - Cards show age badges

TEST 10: Share button copies URL
  - Share button exists
  - Clicking it triggers clipboard copy

TEST 11: Timeline in navigation
  - Sidebar contains Timeline link
  - Link navigates to /timeline
```

## Data Model Changes

**New file: data/rhodes_context_events.json**
```json
{
  "schema_version": 1,
  "events": [
    {
      "year": 1944,
      "month": 7,
      "day": 23,
      "title": "Deportation from Rhodes",
      "description": "1,673 Jews rounded up and deported...",
      "category": "holocaust",
      "source": "Yad Vashem, Jewish Community of Rhodes"
    }
  ]
}
```

No changes to existing data files. Timeline reads from:
- photo_search_index.json (photo dating)
- date_labels.json (confidence intervals)
- identities.json (person names, birth_year, face-to-photo mapping)
- rhodes_context_events.json (new, historical events)

## Technical Constraints

- Pure server-side rendering (FastHTML + HTMX), no JS frameworks
- Photos served from R2 (same URL pattern as /photos page)
- Person filter uses HTMX partial swap (hx-get + hx-target)
- URL state: all filters in query params for shareability
- Context events JSON is read-only, bundled in Docker

## Out of Scope

- Swimlane/parallel timelines (deferred — needs relationship data)
- Map integration (deferred — needs geocoding pipeline)
- Auto-narrative generation (deferred — needs LLM integration)
- Event clustering (premature at 271 photos)
- Horizontal/D3 visualizations (vertical scroll is simpler and mobile-friendly)

## Priority Order

1. Vertical timeline layout with decade markers + photo cards
2. Historical context events inline
3. Confidence interval bars
4. Person filter with HTMX
5. Age overlay when person filtered
6. Share button + URL state
7. Navigation links
