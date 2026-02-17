# PRD 012: Social Graph + Six Degrees Connection Finder

**Status:** In Progress
**Session:** 36-38
**Priority:** P1

## Problem Statement

We have two graphs: relationship graph (GEDCOM: parent-child, spouse) and co-occurrence graph (photos: people photographed together). No tool combines these into a unified social graph that lets users ask "how are these two people connected?" through both familial AND photographic connections.

## User Stories

| Role | Value |
|------|-------|
| Family member | "How is Big Leon related to Rachel Capuano?" |
| Community researcher | Understand community social structure |
| Portfolio viewer | Novel graph algorithm on real heritage data |

## Feature 1: Unified Social Graph

Merge relationship_graph + co_occurrence_graph into a single queryable graph.

**Edge types:**
- `parent_of` / `child_of` (GEDCOM)
- `spouse_of` (GEDCOM)
- `sibling_of` (derived: shared parents)
- `photographed_with` (co-occurrence, with count + photo IDs)

**Nodes:** Confirmed identities (46 people)

## Feature 2: Six Degrees Connection Finder

**Route:** `/connect`

- Two person selectors (dropdowns with search)
- "Find Connection" button
- Results: shortest path with relationship labels
- Each step shows relationship type + evidence (which photos, etc.)
- Multiple paths if available (familial vs photographic)
- URL state: `/connect?person_a=uuid1&person_b=uuid2`

**Algorithm:** BFS on unified graph. Return shortest path, plus family-only and photo-only variants.

## Feature 3: Proximity Scores

`proximity = (1 / path_length) * relationship_weight`

Weights: parent/child/spouse/sibling=1.0, photo 5+=0.8, photo 2-4=0.5, photo 1=0.3

Display on person pages: "Closest connections" section.

## Feature 4: Network Visualization

D3.js force-directed graph on /connect (default view before selection).
- Nodes sized by photo count, colored by generation
- Edges colored by type (family=amber, photo=blue)
- Click node to select, click two to find connection
- 46 nodes — small enough for any approach

## Acceptance Criteria

1. Social graph merges both GEDCOM and photo sources
2. BFS finds connection between two people
3. Path shows mixed edge types (family + photo)
4. URL state: /connect?person_a=X&person_b=Y works
5. Proximity scores computed and displayed on person pages
6. "No known connection" for unconnected people
7. D3.js network visualization renders on /connect

## Out of Scope
- Real-time graph updates (rebuild on data change)
- GEDCOM re-import
- Migration pattern analysis (deferred to Session 38)
