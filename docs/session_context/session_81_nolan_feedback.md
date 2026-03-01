# Session 81 Nolan Feedback Log
Date: 2026-02-28 | Source: conversation after Session 80

## 1. Asheville Photo Case Study
- **Photo**: 746dd11e5b4d86a1 (Vida Capeluto NYC Collection, Photo 84 of 108)
- **Ground truth**: 33 Elizabeth Street, Asheville, NC — Autumn 1934
- **Manual Gemini chat identified**: exact address, children by name, Victoria pregnant, date narrowed to Sept/Oct 1934
- **Our automated prompt did NOT**: no location, no missing-child reasoning
- **Benchmark**: Enhanced GEDCOM prompt MUST identify Asheville or NC
- **Key GEDCOM data that enabled**: children's birth years, 33 Elizabeth St address, Leon's occupation, extended family addresses, maiden name variants

## 2. Connected App Vision
- Photo → Tree → Map → Person: one-click navigation everywhere
- Every entity page should link to every other relevant view
- Admin AND sharing pages — not admin-only
- Tree shows specific family in photo, Map filters to people in photo
- Currently feels like separate apps, not connected views

## 3. Face Analysis Labels
- Replace "Face N" with person name if identified
- Clickable links to person pages (/person/{id})
- Unidentified faces: "Face N (Unidentified)"

## 4. Location Intelligence
- Embedded maps on photo pages (Leaflet.js + OpenStreetMap = free)
- Gemini reasoning display matching Date Estimate pattern
- Research Google/Apple/Mylio patterns for best practices
- Admin: draggable pin for correction
- Confidence badges (AI Estimated / Confirmed)

## 5. GEDCOM-Enriched Prompts
- Current prompt likely visual-only for location
- Need to inject: birth/death places, known addresses, children's birth dates, family migration
- Test against Asheville ground truth as benchmark

## 6. Chatbot Interface (BACKLOG only)
- Interactive conversation yields better results than one-shot
- User provides context + chatbot cross-references GEDCOM
- Progressive refinement, each input documented as metadata
- NOT session 81 scope — log to BACKLOG

## 7. Session 80 Deferred
- D1: Matilda GEDCOM face link — a2889099 linked to wrong xref (@I132423679471@ instead of @I132127360994@)
- D2: Relationship viz — thicker lines, hover labels, generation bands
- D3: Browser verification of Session 80 continuation changes
