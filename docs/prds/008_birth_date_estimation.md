# PRD: Birth Date Estimation

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Stub
**Session:** TBD (planned Session 32)

---

## Problem Statement

With photo dates estimated via CORAL model and Gemini labeling, and face identities confirmed, we can infer birth years by cross-referencing a person's apparent age in dated photos. This enables richer timeline overlays, age-at-event calculations, and validation against known genealogical records.

## Who This Is For

- **Family members**: See estimated birth years on person pages
- **Admin**: Validate date estimates by cross-referencing age appearance
- **Researchers**: Build demographic profiles of the Rhodes community

## Key Requirements

- Cross-reference photo dates with subject ages to infer birth years
- Validate against known birth years (from identity metadata)
- Display estimated birth year on person pages and timeline age overlays
- Confidence scoring based on number of corroborating photos

## Dependencies

- ML-050 (date UX integration) — DONE
- ML-040-047 (date estimation pipeline) — DONE
- Identity metadata system (birth_year field) — DONE
