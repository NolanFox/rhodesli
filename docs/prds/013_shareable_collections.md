# PRD 013: Shareable Collection Pages

**Status:** In Progress
**Session:** 36-38
**Priority:** P1

## Problem Statement

Family members want to share "Aunt Vida's photos" with others who might help identify people. Currently, individual photos can be shared but there's no way to share a collection as a curated set with a single link.

## Feature 1: Collection Directory

Route: `/collections`

Lists all collections with:
- Name, photo count, date range (earliest to latest)
- Preview thumbnails (first 4 photos)
- Number of identified vs unidentified people

## Feature 2: Collection Detail Pages

Route: `/collection/{slug}`

Shows:
- Collection name as title
- Photo count and identified count
- All photos in the collection as a grid
- Identified people appearing in this collection
- "Help identify" CTA for unidentified faces
- Link to timeline filtered to this collection

## Feature 3: Share + Help Identify

- Share button copies collection URL
- Unidentified faces highlighted on collection photos
- Links to /compare for face identification

## Acceptance Criteria

1. /collections shows all collections with counts
2. /collection/{slug} shows photos in that collection
3. Share button copies URL
4. Cross-link to timeline works
5. Unidentified face count shown per photo

## Out of Scope
- Collection creation/editing UI
- Collection descriptions (derive from photo metadata)
