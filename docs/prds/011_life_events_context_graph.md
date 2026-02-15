# PRD: Life Events & Context Graph

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Stub
**Session:** TBD (planned Session 35)

---

## Problem Statement

Photos capture moments but don't tell you what the moment was. An event tagging system would let users annotate photos with life events ("Moise's wedding in Havana, 1952") that connect photos, people, places, and dates into a structured knowledge graph. This enables richer timelines and relationship inference.

## Who This Is For

- **Family members**: Tag photos with events they recognize
- **Admin**: Build structured event history of the community
- **Researchers**: Analyze patterns in life events across the diaspora

## Key Requirements

- Event model: type (wedding, funeral, holiday, reunion), participants, location, date
- Tag photos with events (one photo can have multiple events)
- Events connect photos, people, places, dates
- Timeline integration: life events interspersed with photos
- Relationship inference from shared events (co-attendees)

## Dependencies

- AN-001 (annotation system) — DONE
- Timeline Story Engine (FE-100) — DONE
- Geocoding pipeline (PRD 010) — prerequisite for location linking
- GEDCOM import (PRD 009) — provides marriage/birth/death dates
