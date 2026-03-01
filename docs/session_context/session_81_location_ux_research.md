# Session 81 — Location UX Research

## Competitive Analysis

### Google Photos
- Mini-map in the info panel (right sidebar), showing pin on map tile
- Reverse geocoded address displayed as text label above map
- AI-estimated locations shown with lower confidence indicator
- Tapping map opens full Google Maps view
- Location editable: tap address to correct, drag pin to reposition

### Apple Photos
- "Places" album: world map with clustered photo pins
- Info panel: small map thumbnail with location label
- Location assigned via EXIF GPS or user manual entry
- No AI-based location estimation (relies on EXIF metadata)

### Mylio
- Dedicated "Map" view: full-screen map with photo clusters
- Manual geolocation: drag-pin interface for unlocated photos
- Batch location assignment for groups of photos
- No embedded AI for location guessing

## What We Adopted and Why

### Embedded Mini-Map (from Google Photos)
- Leaflet.js + OpenStreetMap (free, no API key required)
- Dark CARTO tiles match our slate/dark UI theme
- Map renders inline within the AI Analysis section (not a separate page)
- 300px height with rounded corners, consistent with other panels

### Location Label + Confidence Badge (from Google Photos + Date Estimate pattern)
- Location name in amber serif font (matches date estimate styling)
- Three-tier confidence badge (high/medium/low) with color coding:
  - High: emerald, Medium: amber, Low: red
- Follows the same visual language as our date estimate confidence

### Evidence Panel (original to Rhodesli)
- Gemini's reasoning text shown as italic evidence below the label
- Matches the "Photo Detective Evidence" pattern we already use for dates
- No other photo app shows *why* a location was estimated

### Admin Edit (from Mylio drag-pin + Google Photos edit)
- Admin sees location correction form (text input, placeholder for geocoding)
- Map marker is draggable for admins (future: save new coordinates)
- Non-admins see read-only map and label

## Key Design Decisions

| Pattern | Source | Implementation |
|---------|--------|----------------|
| Inline mini-map | Google Photos info panel | Leaflet.js in AI Analysis section |
| Location label | Google Photos reverse geocode | Font-serif amber text |
| Confidence badge | Internal (date estimate pattern) | Three-tier emerald/amber/red |
| Evidence text | Original (no competitor does this) | Italic slate text |
| Admin correction | Mylio + Google Photos | Text input + draggable marker |
| Tile provider | N/A | CARTO dark_all (free, matches theme) |
