# Session 81 Context: Connected App + Location Intelligence
# Source: Nolan feedback conversation, Feb 28, 2026
# Breadcrumbs: Session 80 → this → Session 82+

---

## 1. THE ASHEVILLE CASE STUDY (Ground Truth Benchmark)

### The Photo
- **Photo ID**: 746dd11e5b4d86a1
- **Collection**: Vida Capeluto NYC Collection (Photo 84 of 108)
- **Current AI Analysis**: c. 1930s ± 4 years, high confidence
- **Current Date Estimate**: circa 1934, Range 1930-1938, 80% 1930s
- **People detected**: 4 (all identified)
  - Victoria Capuano Capeluto (~30, female)
  - Nace Capeluto (~2, male toddler)
  - Anita Capeluto Franco (~5, female)
  - Selma Capeluto (~6, female)
- **Subject Ages (Gemini)**: 5, 22, 1, 6
- **Scene**: Outdoor group portrait, young woman and three children,
  rustic wooden chair, brick apartment building, bare trees

### What Gemini Chat Achieved (That Our Prompt Didn't)
In an interactive conversation with Gemini, Nolan provided Victoria's
family tree context. Gemini was able to:

1. **Identify all children by name** using birth year + apparent age matching
2. **Determine the photo was taken before Betty's birth** (Jan 5, 1935)
   because only 3 of 4 children are present
3. **Identify Victoria as pregnant** (loose clothing, concealing pose)
4. **Pinpoint location as Asheville, NC** by cross-referencing:
   - GEDCOM residence data (Leon & Victoria at 33 Elizabeth St)
   - 1935 Asheville City Directory entries
   - Architectural style (brick building with sun porches = Asheville)
   - "Rustic twig furniture" as a Western NC regional marker
   - Extended family at same address (Annie Caponano at 33½ Elizabeth)
5. **Narrow date to Autumn 1934** using:
   - Betty's birth date (Jan 5, 1935) → Victoria ~5-7 months pregnant
   - Bare trees + short sleeves → mild weather, September/October
   - Children's apparent ages vs birth years

### Key GEDCOM Data That Enabled This
- Victoria's children: Selma (1926), Anita (1931), Nace (1933), Betty (1935)
- Family residence: 33 Elizabeth Street, Asheville, NC
- Leon's occupation: The Brass Rail (from city directory)
- Extended family: Annie Caponano at 33½ Elizabeth, Zebulon and Rachel
  Caponano also at 33 Elizabeth
- Victoria's maiden name: Capuano/Caponano

### What Our Current Prompt Likely Misses
Our Gemini extraction prompt probably does NOT include:
- Children's birth years (critical for "who's missing" reasoning)
- Known family addresses (critical for location identification)
- Family relationships (critical for "is this a nuclear family" reasoning)
- Historical records context (city directories, census data in GEDCOM notes)

**The test**: Run our enhanced prompt against this photo. If it identifies
Asheville, NC, the GEDCOM enrichment works. If it doesn't, iterate.

---

## 2. CONNECTED APP VISION

### Current State (Problems)
- Photo page has no link to Tree page
- Photo page has no link to Map page
- Person page has no link to Tree page
- Person page has no link to Map page
- Face Analysis shows "Face 0", "Face 1" — no names
- No embedded maps on photo pages
- No location estimates from Gemini
- Tree and Map feel like separate apps, not connected views

### Target State
Every entity page (Photo, Person) should have one-click access to:
- **Tree view** — showing relevant family relationships
- **Map view** — showing geographic context
- **Person view** — from face labels

Navigation should be **contextual**:
- Photo→Tree shows the specific family in this photo
- Photo→Map filters to people in this photo
- Person→Tree centers on that person
- Person→Map shows all their photos

This applies to BOTH admin pages AND sharing (public) pages.

---

## 3. LOCATION UX RESEARCH

### Google Photos
- Shows mini-map in photo info panel (right sidebar)
- Reverse geocoded address shown as text
- Clicking map opens full map view with nearby photos
- AI-estimated locations shown with lower confidence
- Users can manually set/correct location

### Apple Photos
- "Places" album groups photos by location
- Info panel shows map thumbnail
- Interactive map in Places view with photo clusters
- Location editing in info panel

### Mylio
- Dedicated "Map" view with all photos plotted
- Photo info shows GPS coordinates + location name
- Manual geolocation tool — drag pin on map
- Location categories (city, country) for organization

### Key Patterns to Adopt
1. **Embedded mini-map** on photo page (Leaflet + OSM = free)
2. **Location label** above map (City, State, Country)
3. **Confidence badge** (AI Estimated / Confirmed)
4. **Evidence panel** showing reasoning (like our Date Estimate pattern)
5. **Admin: Edit/Correct** button (drag pin or type address)
6. **Link to full Map view** filtered to this photo's people

---

## 4. TECHNICAL NOTES

### Leaflet.js Setup (No API Key Needed)
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<div id="photo-map" style="height: 300px;"></div>
<script>
  var map = L.map('photo-map').setView([lat, lng], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  L.marker([lat, lng]).addTo(map).bindPopup('Estimated location');
</script>
```

### Tree Shortest Path Algorithm
For finding relationships between people in a photo:
- GEDCOM is a tree/graph structure
- BFS from person A to person B through parent/child/spouse edges
- Path length = "genealogical distance"
- Display only nodes on the path + their immediate context

### Gemini Location Prompt Enhancement
Current extraction probably asks about location from visual clues only.
Enhanced version should include GEDCOM biographical context.
This is analogous to how a human photo detective works — they don't
just look at the photo, they cross-reference what they KNOW about
the people in it.

---

## 5. FUTURE: CHATBOT INTERFACE (BACKLOG — NOT SESSION 81 SCOPE)

The Asheville case study demonstrates that interactive conversation
yields much better results than one-shot automated analysis. A chatbot
interface could allow:

- User tells chatbot: "I think this is Aunt Victoria in Asheville"
- Chatbot: "I see 4 people. Victoria had 4 children. Only 3 are here.
  Based on birth years, the missing child is Betty (born 1935).
  This narrows the date to before January 1935."
- User: "Yes! And she looks pregnant"
- Chatbot: "If Betty was born Jan 5, 1935, and Victoria appears 5-7
  months pregnant, this photo was likely taken September-October 1934."

Each piece of user input:
1. Gets documented as metadata on the photo
2. Feeds back to improve estimates (active learning)
3. Can trigger re-analysis with new context
4. Builds community knowledge collaboratively

This aligns with the "progressive refinement" architecture already
in the codebase and could be a powerful differentiator.

---

## 6. SESSION 80 DELIVERABLES TO BUILD ON

Session 80 addressed:
- Tree overhaul (BALKAN FamilyTreeJS with lazy loading)
- Face card redesign (Google Photos pattern)
- Compare CPU-based solution
- Face overlay UX improvements

Session 81 extends this by connecting the tree and map to individual
photos/people, adding location intelligence, and making the face
analysis section more useful with identity labels.

---

## 7. SESSION 80 DEFERRED ITEMS (Now in scope for Session 81)

These were identified in the Session 80 assessment as needing follow-up.
Each runs as its own subagent + worktree for maximum parallelism.

### D1: Supabase GEDCOM Face Link Fix for Matilda
- Matilda's GEDCOM record is not properly linked to her face identity
- Requires a Supabase API call to fix the link
- Read `docs/assessments/session-80-assessment.md` for full context
- The agent should investigate the `gedcom_face_links` or similar table,
  find Matilda's records, identify the mismatch, and fix it
- Add a regression test so this category of bug gets caught

### D2: Relationship Visualization Enhancements
Three specific improvements to the tree/relationship display:
1. **Thicker lines** for stronger relationships (more shared photos = thicker)
2. **Hover labels** on relationship lines showing type and strength
3. **Generation bands** — horizontal visual bands grouping by generation
These build on Session 80's BALKAN FamilyTreeJS work. Read existing tree
code and PRDs before implementing. Each enhancement should be independently
testable and screenshot-verified.

### D3: Browser Verification of Continuation Changes
Session 80 made changes that were committed but not browser-verified in
production. This track deploys current main, opens production in Claude Chrome,
and verifies every Session 80 change. Any broken features get fixed immediately.

---

## 8. RISK REGISTER

| Risk | Mitigation |
|------|-----------|
| Worktree merge conflicts | Tracks touch different files: tree-nav (tree routes), face-map (face analysis + map routes), location-ux (Gemini + Leaflet) |
| Gemini API costs for batch re-run | Dry-run first, batch in groups of 5, require explicit approval for full run |
| GEDCOM data gaps | Graceful fallback — if no GEDCOM context, use visual-only estimation |
| Leaflet CDN dependency | Fallback to static "View on Map" link if Leaflet fails to load |
| Session 80b conflicts | All session-81 work on `session-81/` prefixed branches |
| Context overflow | /clear enforced between every act, small phases, re-read from disk |
