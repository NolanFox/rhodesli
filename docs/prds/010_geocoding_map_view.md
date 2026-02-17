# PRD 010: Geocoding & Map View

**Status:** Complete
**Session:** 36-38
**Priority:** P1

## Problem Statement

Many photos have location context from Gemini labels (e.g., "studio portrait, likely Rhodes Old Town") and identity metadata (birth_place, death_place). A map view lets users explore the diaspora geographically — seeing where photos were taken and where community members lived across Rhodes, New York, Miami, Tampa, Congo, and beyond.

## Feature 1: Curated Location Dictionary

File: `data/location_dictionary.json`

22 curated locations covering the Rhodes Jewish diaspora:
- Mediterranean: Rhodes, Istanbul, Italy
- United States: NYC, Lower East Side, Brooklyn, Miami, Tampa, Atlanta, LA, Seattle, Portland, Montgomery, Asheville
- Africa: Elisabethville/Lubumbashi (Congo), Bujumbura (Burundi)
- South America: Buenos Aires
- Caribbean: Havana
- Middle East: Jerusalem
- Europe: Auschwitz

Each entry has: name, lat/lng, aliases for fuzzy matching, region, historical notes.

## Feature 2: Geocoding Script

Script: `scripts/geocode_photos.py`

Matches Gemini `location_estimate` free-text against dictionary aliases.
- Specificity ranking (Lower East Side > NYC > United States)
- Word-boundary matching for short aliases
- Deduplication of overlapping matches
- 267/271 photos matched (98.5%)
- Outputs `data/photo_locations.json`

## Feature 3: Interactive Map View

Route: `/map`

- Leaflet.js + OpenStreetMap (CartoDB dark tiles)
- MarkerCluster for dense areas
- Custom styled markers with photo count
- Click popups with photo previews (up to 8)
- Filters: collection, person, decade
- Share button with current filter state
- OG meta tags for social sharing

## Acceptance Criteria

1. /map renders with Leaflet map and markers
2. Markers cluster when zoomed out
3. Click marker shows popup with photo thumbnails
4. Collection/person/decade filters work
5. Share button copies filtered URL
6. 98%+ photos geocoded from dictionary

## Out of Scope
- External geocoding API calls
- User-submitted location corrections (future)
- Timeline + map sync view (future session)
