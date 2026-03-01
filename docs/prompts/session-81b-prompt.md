# Session 81B Prompt — Fix Real Issues Found in Browser Verification

## Context

Session 81 implemented many features that ARE working in production:
- Family Tree + See on Map buttons on photo page action bar (WORKING)
- Face overlay names on photos (Victoria, Nace, Anita, Selma — WORKING)
- Face identity links in Face Analysis section (clickable names — WORKING)
- Person page → Tree/Map navigation links (WORKING)
- Location Estimate section with confidence badges (WORKING)
- Photo→Tree smart navigation with subtree filtering (WORKING)

However, the user identified real issues that need fixing.

## Issues to Fix

### Issue 1: Face Analysis still says "Face N:" prefix
- **Location**: `app/main.py` line 1772
- **Current**: `Span(f"Face {i}: ", ...)` followed by identity name link
- **Goal**: When `has_real_name` is True, show ONLY the name (no "Face N:" prefix). Keep "Face N" for unidentified.

### Issue 2: Leaflet map not rendering (grey blank area)
- **Location**: `app/main.py` lines 1542-1575
- **Symptom**: Map div present, Leaflet CSS/JS loads, but tiles don't render
- **Root cause**: Initialization timing — script may run before Leaflet library loads from CDN, and container may not be sized

### Issue 3: Tree missing people without pictures
- **Investigation**: Check if GEDCOM relatives without photos are being filtered out of tree nodes

## Planning Findings

### Issue 1 Analysis
Code at line 1770-1777 shows:
```python
if has_real_name and identity_id:
    header_el = Div(
        Span(f"Face {i}: ", cls="text-white font-medium text-sm"),
        A(display_name, href=f"/person/{identity_id}", ...),
        cls="mb-1",
    )
```
The fix is simply removing the `Span(f"Face {i}: ", ...)` element.

### Issue 2 Analysis
The `_field()` wrapper uses `<Details>` with `open=expanded`. Since `expanded=True`, the container IS visible on page load. The real issue is:
1. The inline `<Script>` tag (the init code) may execute BEFORE the `<Script src="leaflet.js">` tag (the library) finishes loading from CDN
2. The `typeof L !== 'undefined'` check would fail → falls to DOMContentLoaded handler
3. But DOMContentLoaded may have already fired (especially on HTMX swaps)
4. Result: `initMap()` never gets called, or calls without `L` being ready

Fix: Use a reliable Leaflet load check with polling, plus `map.invalidateSize()` after creation.

### Issue 3 Analysis
The tree API at `/api/tree/data` (line 19200) builds nodes from:
1. `_build_tree_adjacency()` — builds parent-to-child, child-to-parent, person-to-spouse maps from relationships table
2. `_build_tree_person_lookup()` — builds a lookup of person metadata
3. BFS traversal from focal person adds relatives to `included` set
4. `_make_tree_node()` builds the visual node for each person

People without photos still appear IF they're in the adjacency maps (i.e., have relationship records). The tree JS handles silhouette avatars for people without crops. Need to verify `_build_tree_person_lookup()` doesn't filter out people without photos.

## Implementation Results

### Issue 1: FIXED
Removed `Span(f"Face {i}: ", ...)` from the confirmed identity header. Now shows only the clickable name link. Added test assertion confirming "Face 0: " prefix is absent.

### Issue 2: FIXED
Root cause confirmed: inline script could run before Leaflet CDN finishes loading. The `DOMContentLoaded` fallback doesn't fire on HTMX swaps. Fix: replaced with polling approach (check for `L` every 100ms, up to 50 attempts = 5s). Added `map.invalidateSize()` after creation to handle container sizing.

### Issue 3: NOT A BUG
Investigated: 708 unique people in relationships.json (673 GEDCOM xrefs, 35 UUIDs). `_build_tree_person_lookup()` includes ALL confirmed identities and ALL GEDCOM individuals. People without photos get empty avatar (rendered as silhouette in JS). The depth-limited BFS (depth=1 default) means not all relatives show at once — users expand nodes to see more. Working as designed.
