# PRD: Geocoding & Map View

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Stub
**Session:** TBD (planned Session 34)

---

## Problem Statement

Many photos have location context from Gemini labels (e.g., "studio portrait, likely Rhodes Old Town") and identity metadata (birth_place, death_place). A map view would let users explore the diaspora geographically — seeing where photos were taken and where community members lived across Rhodes, Seattle, New York, Havana, and beyond.

## Who This Is For

- **Family members**: Visualize the geographic spread of their family
- **Researchers**: Map the Rhodes Jewish diaspora patterns
- **Admin**: Verify location estimates and add corrections

## Key Requirements

- Batch geocode Gemini location estimates to lat/lng coordinates
- Map view route (/map) with photo markers clustered by location
- Click marker to see photos from that location
- Timeline + map sync view (scrub timeline, map updates)
- Location filter on /photos page

## Dependencies

- ML-046 (search metadata export) — DONE
- ML-050 (date UX integration) — DONE
- Geocoding API (Google Maps, Mapbox, or Nominatim)
