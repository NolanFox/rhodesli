# Session 80 Context: Fix Everything — Tree, Face Cards, UX

## Source: Claude research + session 79 review, Feb 28, 2026
## Breadcrumbs: Session 78 audit → Session 79 fixes → Session 79 review → this

---

## 1. SESSION 79 RED FLAGS (from Nolan's review)

### RF-1: Tree is a workaround, not a fix
- Swapped CardHtml→CardSvg without understanding WHY CardHtml fails
- Only 13 of 718 people visible — not a working tree
- 114 disconnected clusters — architectural (GEDCOM data structure) issue
- "Focus on" dropdown navigating 57 families is decent but not sufficient
- **Fix required:** Complete tree overhaul with lazy loading, search, expand/collapse

### RF-2: Compare deferred 7+ sessions
- InsightFace needs GPU on Railway — known blocker for months
- No concrete plan — just "research lightweight CPU options"
- Erodes portfolio credibility if someone tries to use the app
- **Fix required:** Ship CPU solution OR create time-bound plan with "Coming Soon" page

### RF-3: Session 78 honesty gap
- Session 78 claimed "0 red flags" when 6+ existed
- Session 79 fixed 3 but didn't enumerate what was left unfixed
- **Fix required:** Audit remaining 78 issues, create BACKLOG entries

### RF-4: Uncommitted data files
- annotations.json, identities.json, relationships.json, gedcom_matches.json
- "Benign" JSON reordering from backfill — but creates noisy git diffs
- **Fix required:** Commit cleanly or normalize JSON output

### RF-5: Tree design failures (from Nolan's detailed feedback)
- Zoom is way off
- Can't click anyone to get to their person page
- Can't expand tree (parents, siblings, etc.) like Ancestry
- Should only load data for specific tree view, expand on demand
- Need action to focus tree on a different person
- Need search — dropdown doesn't work at this scale
- **Fix required:** Full ancestry-style interaction model

### RF-6: Face Card UX failures (from Nolan's feedback)
- Find Similar renders as badly-formatted vertical column
- Should be: large hero face + responsive comparison grid below
- Lost functionality: click photo → go to picture, multi-photo gallery, sharing
- People section cards are broken mix of old and new styles
- Multi-face identities handled poorly
- **Fix required:** Consistent face card component, Find Similar redesign

---

## 2. RESEARCH: Family Tree Libraries

### BALKAN FamilyTreeJS (recommended if licensing permits)
- Built-in: lazy loading, expand/collapse, zoom/pan, minimap, search
- Family-specific semantics: `pids` (partner IDs), `fid`/`mid` (father/mother)
- Custom node templates with photos
- Ancestor expansion upward from selected individual
- CDN available: `https://balkan.app/js/FamilyTree.js`
- **Licensing:** Free for evaluation. Commercial license needed for production.
  Check current pricing and terms.

### donatso/family-chart (MIT, fallback option)
- D3.js-based, MIT license (free for any use)
- Zoom, pan, click to expand
- Supports photos on nodes
- JSON data format — easy server-side generation
- **Limitation:** No built-in lazy loading — must implement manually

### Custom D3 (current approach, not recommended)
- Current CardSvg approach renders only 13 nodes
- Would need significant work to add lazy loading, search, etc.

### Decision: Try BALKAN first (superior features), fall back to donatso if licensing blocks

---

## 3. RESEARCH: Face Card UX Patterns

### Google Photos approach
- People album: grid of face thumbnails, each leads to full gallery
- "Similar faces" shown in a horizontal row at top
- Face crop is dominant (80%+ of thumbnail area)
- Name, count underneath
- Click → all photos of that person

### Apple Photos approach
- Large face crop as album cover
- Photo count prominent
- "Confirm Additional Photos" flow for uncertain matches
- Clean, minimal — face is everything

### Excire Foto approach
- Find People: face grid with star ratings
- Find Faces: search by characteristics
- Side-by-side comparison for verification
- Fast — searches take <2 seconds after initial analysis

### Key UX principles for Rhodesli:
1. **Face is hero.** 60%+ of card area should be the face image.
2. **Actions visible, not buried.** View Photos, Find Similar, Tree, Share — all one click.
3. **Multi-face → mini gallery.** Show 2-3 overlapping thumbnails with "+N more" badge.
4. **Find Similar = full-page layout.** Hero face (large) + responsive grid of results.
5. **Consistent everywhere.** Same card component in People, Review, and inline views.

---

## 4. TREE API DESIGN

### Endpoint: GET /api/tree/data?person_id={uuid}&depth=1

Returns the focal person + all connections within `depth` hops:

```json
{
  "focal_person": "uuid-123",
  "nodes": [
    {
      "id": "uuid-123",
      "name": "Big Leon Capeluto",
      "birth_year": 1902,
      "death_year": 1983,
      "photo_url": "/face/crop/uuid-123",
      "gender": "M",
      "has_parents": true,
      "has_children": true,
      "has_siblings": true,
      "partner_ids": ["uuid-456"],
      "father_id": "uuid-789",
      "mother_id": "uuid-012"
    }
  ]
}
```

### Endpoint: GET /api/tree/expand?person_id={uuid}&direction=parents

Returns ONLY the new nodes to merge into the existing tree.

### Why this design:
- 718 people would be 100KB+ of JSON — too much for initial load
- Most users care about ONE family lineage at a time
- Expand-on-demand mirrors Ancestry's proven UX
- Reduces server load and page render time

---

## 5. COMPARE CPU OPTIONS

### Option 1: ONNX Runtime with InsightFace model
- Export InsightFace to ONNX format
- Use `onnxruntime` (CPU) for inference
- Slower than GPU but works on Railway
- **Best option if model export is clean**

### Option 2: Pre-computed embeddings only
- All archive faces already have embeddings in embeddings.npy
- Only need to compute embedding for the NEW uploaded photo
- Use `dlib` or `mediapipe` for the single new face
- Compare with cosine distance against cached archive embeddings
- **Fastest to implement — only 1 face needs processing**

### Option 3: Proxy to external service
- Send uploaded face to a GPU-enabled service for embedding
- Compare against cached embeddings locally
- Adds dependency but solves the problem

### Recommendation: Option 2 — minimal new code, uses existing data

---

## 6. APP THESIS (for UX evaluation)

### Core uses (from Nolan):
1. **Identify:** Community member recognizes someone in a photo
2. **Share:** They share what they found (share button, OG tags, link)
3. **Contribute:** They add knowledge (annotation, name suggestion)
4. **Discover:** They find connections they didn't know about
5. **Grow:** The archive grows through contributions and uploads

### Every page should support at least one of these use cases.

---

## 7. HARNESS REQUIREMENTS

- Session prompt: `docs/prompts/session-80-prompt.md`
- Session context: `docs/session_context/session_80_context.md`
- Session log: `docs/session_logs/session_80_interactive_log.md`
- Assessment: `docs/assessments/session-80-assessment.md`
- ALGORITHMIC_DECISIONS.md: Updated for every non-trivial decision
- SESSION_HISTORY.md: Updated at session end
- ROADMAP.md: Under 150 lines, updated at session end
- All commits: conventional commit format
- `/clear` between every Act — MANDATORY, not optional
