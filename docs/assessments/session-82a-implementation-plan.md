# Implementation Plan: Rhodesli UX Overhaul (Session 82a -> 83)

This document outlines the architectural and engineering steps required to implement the Top 5 UX proposals identified in Session 82a. This serves as the roadmap for Session 83.

## 1. Click-to-Target AI Bounding Boxes

**Architecture:**
*   Currently, FastHTML uses simple mouse events for drawing freehand boxes (`start_x`, `start_y`, `end_x`, `end_y`).
*   **Backend/ML change**: The `insightface` bounding box coordinates mapping to each `face_id` are already calculated but need to be serialized and passed directly to the frontend during the `/photo/{id}` page load.
*   **API Change**: Update `load_photo_metadata()` to include a JSON payload of pre-computed `box` dictionaries (`[x1, y1, width, height]`) mapped to each face.

**Frontend Implementation:**
*   Inject the face coordinates into a hidden `data-boxes` HTML attribute on the `photo-container` element.
*   Use lightweight Hyperscript or Vanilla JS attached to the photo: On click, detect if the mapped `(x, y)` coordinate falls within any pre-computed bounding box. If yes, snap an interactive SVG/HTML `<div>` bounding box to those exact dimensions instead of requiring a manual drag.
*   Replace freehand JS logic with a "Click to Select" UX pattern.

## 2. Masonry Adaptive Grids

**Architecture:**
*   **CSS Refactor**: The existing Tailwind CSS uses rigid `aspect-square` classes on the `/photos` view. We will shift to an explicit CSS Column-based or Grid-based Masonry layout.
*   **Backend change**: To prevent layout shifting, the backend MUST know the aspect ratio (width/height) of every photo beforehand.
*   Update the photo ingestion pipeline to cache `width` and `height` dimensions in `photo_metadata.json` if not already present.

**Frontend Implementation:**
*   On the `/photos` endpoint, pass the dimensions to the template.
*   Use inline styling to set `--aspect-ratio`, and utilize modern CSS `break-inside: avoid` with CSS columns, or adopt a lightweight Masonry JS library integrating cleanly with FastHTML components.

## 3. "Missing Info" Tabular List View

**Architecture:**
*   **Routing**: Introduce a new route parameter or toggle (e.g., `?view=table` vs `?view=grid`) on the `/photos` endpoint.
*   **Data Aggregation**: The backend `get_photos_for_view()` must efficiently join data from `relationships.json`, `identities.json`, and `photo_metadata.json` to flag which fields (Date, Location, Names) are missing to render the "Add Info" CTAs.

**Frontend Implementation:**
*   Build a new FastHTML `Table` component variant. 
*   Empty columns should render standardized HTMX `hx-get` buttons that immediately pop open the inline edit modals.

## 4. Integrated "LifeStory" Vertical Timelines

**Architecture:**
*   **Data Model**: Currently, `person_dashboard` reads from `identities.json` and basic photo references. We need a unified "Timeline Event" class that normalizes both static biographical events (Birth, Death, Marriage) and Photos (timestamped via ML estimation) into a single chronological array.
*   **Sorting**: Sort this unified array before rendering.

**Frontend Implementation:**
*   Create a reusable FastHTML `TimelineEvent` component.
*   Anchor the UI with a central border line (`border-l-2 border-slate-700`). Use alternating `flex-row` and `flex-row-reverse` Tailwind classes to zigzag the photos and text events down the page.

## 5. Interactive Radial Family Tree

**Architecture:**
*   **Graph Extraction**: Add a new backend utility `get_ego_graph(person_id, max_depth=3)` that parses `relationships.json` and returns a flat node/link JSON structure tailored for D3.js consumption.
*   This structure must include nodes (ID, name, avatar crop URL) and links (source, target, relationship type).

**Frontend Implementation:**
*   Add a new endpoint `/person/{id}/tree_data` returning the JSON graph.
*   On the `/person/{id}` view, include a D3.js script block. Use D3's Force-Directed Graph or Radial Tidy Tree layout algorithm to render the SVG interactively. 
*   Attach click listeners to the SVG nodes to `hx-get` modal previews or navigate to other relatives.

---

### Verification & Testing
Before merging Session 83:
1.  **Unit Tests**: Verify the `get_ego_graph` JSON generation accurately matches `relationships.json` rules.
2.  **Visual Regression**: Ensure the newly added Masonry styles do not break Safari/Firefox rendering engines.
3.  **End-to-End Test**: Simulate clicking on a face and confirm the ML-bounded coordinates are successfully captured by the tagging API endpoint.
