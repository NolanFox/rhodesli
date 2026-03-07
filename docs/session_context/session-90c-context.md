# Session 90c Planning Context

**Predecessor**: Session 90b (v0.93.1, commit 49f3755)
**Prompt**: `docs/prompts/session-90c-prompt.md`
**Date**: 2026-03-07

---

## Origin: Nolan's Feedback After Session 90b Completion Pass

Nolan wants to fully close out all 90b deferred items before moving to Session 91.

### 1. Leon's Restaurant Photo — Multiple Issues (P0)

**Photo**: `3192877a90a174e9` on production (NOT in local photo_index.json — production data diverged)
**URL**: https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9

**Issues:**
1. **Gemini says "San Francisco/NYC"** for location — WRONG, should be Tampa, FL
2. **Face analysis says "No face descriptions available yet"** — Detect Faces not run
3. **Location badge says Tampa** (manually corrected in 90b) but Gemini evidence text still wrong

**Root Cause Analysis (from research):**

The photo has two identified faces: Victor Capelluto + Victoria Capuano Capeluto.
- Victor GEDCOM: born Rhodes 1906, died 2002. **NO residence events, NO immigration events.**
- Victoria GEDCOM: born Rhodes. **NO events.**
- Victor's brother is Big Leon Capeluto (GEDCOM @I132126987005@, died 1983, born Milas Turkey). **NO occupation/residence events.**

So Gemini receives: Victor born Rhodes 1906, Victoria born Rhodes. That's it. The GEDCOM has no Tampa connection for anyone in the photo.

**Why Gemini says SF:** The Gemini response says "Victor's timeline places him in San Francisco in 1938 and 1940" — but this is Gemini hallucinating/inferring from general knowledge, not from GEDCOM data we provided.

**Nolan's explanation:** Victor passed through San Francisco on a passenger ship from Asia on his way to North Carolina. A passenger list record shows SF as the port of entry, but that was a transit point, not a destination. The GEDCOM tree doesn't include this passenger list event.

**What should tell the correct story:**
- The sign literally says "LEON'S RESTAURANT"
- The collection is "Nace Capeluto Tampa Collection"
- Victor's brother Big Leon Capeluto had a restaurant in Tampa
- The photo shows two people standing on a sidewalk in front of the restaurant
- Art Deco architectural style matches Tampa 1940s

**Fix plan:**
1. **Improve Gemini prompt** — Add instructions about:
   - Using collection metadata and photo filenames as location signals
   - Passenger list cities being transit points, not destinations
   - Visible signage (especially business names) as very strong location evidence
   - Cross-referencing signage with known family members' businesses
2. **Ensure collection name + source is passed to Gemini** as part of context (verify this)
3. **Re-run Gemini analysis** with improved prompt + first_order GEDCOM context

### 2. Face Analysis / "Detect Faces" Not Running (P0)

**Finding:** "Detect Faces" and "Re-analyze Photo" are TWO SEPARATE PIPELINES:
- **"Re-analyze Photo"** = Gemini date/location/scene analysis (one API call, uses "quick" preset)
- **"Detect Faces"** = Gemini face alignment / coordinate bridging (separate API call)

**"Detect Faces" does NOT require InsightFace on Railway.** It uses pre-existing bounding box coordinates from embeddings.npy and sends them to Gemini for per-face descriptions. This is pure Gemini API — no ML model needed.

The previous assessment incorrectly said "Requires InsightFace locally (AD-110 blocks ML on Railway)." This is WRONG for the coordinate bridging approach (AD-146, PRD-015). The InsightFace detections already exist in embeddings.npy.

**Fix:** Run "Detect Faces" on Leon's Restaurant photo via the admin endpoint or script. Should produce per-face descriptions like "young man in light suit, 30s" etc.

**Nolan's question:** "Is it doing this as one or two API calls? Why is there a separate Detect Faces button?"
**Answer:** Two separate API calls. Re-analyze = date/location/scene. Detect Faces = per-face descriptions from bbox coordinates. They serve different purposes.

### 3. Back-of-Photo Upload Flow (P1 — Verify)

**Status:** 43 tests pass. Chrome verified in 90b. Feature works.
**Gap:** No real back images on production yet (only test artifacts).
**Nolan asks:** Does upload work there?
**Answer:** Yes — verified via Chrome in 90b (screenshots exist). David Franco photo was used for testing.

### 4. main.py Target 15K (P2)

Currently 25,941 lines. Target was 15K. Further extraction requires refactoring shared helpers into a shared.py module, which is a significant architectural change. This is lower priority than the Gemini fixes.

### 5. 7 Flaky Order-Dependent Tests (P3)

Pre-existing. Pass individually, fail intermittently in full suite. Test isolation issue with route module loading order.

---

## Key Architecture Findings

### Two Photo Analysis Pipelines

| Pipeline | Button | Route | What It Does | Requires |
|----------|--------|-------|-------------|----------|
| Date/Location | "Re-analyze Photo" | POST /api/photo/{id}/reanalyze | Single Gemini call: date, location, scene, text | Gemini API key |
| Face Descriptions | "Detect Faces" | POST /api/face-alignment/{id} | Gemini coordinate bridging: per-face descriptions | Gemini API key + embeddings bbox |

Both use Gemini. Neither requires InsightFace on Railway.

### GEDCOM Context Flow

1. Photo has identified faces (Victor, Victoria)
2. Faces linked to GEDCOM via `gedcom_matches.json` + Supabase `identity_gedcom_links`
3. GEDCOM context builder loads: birth/death, residence, occupation, children, siblings, parents
4. "first_order" variant includes immediate family events
5. Context injected into Gemini prompt as text block

### What's Missing from GEDCOM

For the Leon's Restaurant fix, the GEDCOM data is sparse:
- Victor: only birth + death, no events
- Victoria: only birth, no events
- Big Leon (Victor's brother): birth + death, no events, no occupation/Tampa

The GEDCOM tree file doesn't include passenger lists or detailed residence events.

### Collection Metadata as Signal

The collection name "Nace Capeluto Tampa Collection" is a STRONG location signal that Gemini should use. Need to verify this metadata is actually passed to Gemini in the prompt.

### Production Data Divergence

Leon's Restaurant photo (3192877a90a174e9) exists on production but NOT in local photo_index.json. Must sync from production before running local scripts.

---

## Research: Gemini Prompt Improvements

### Current Prompt Gaps

1. **No collection/source context** — The prompt may not include the collection name or photo source
2. **No signage→family cross-reference** — Prompt doesn't tell Gemini to match business names in signage against known family members
3. **No passenger list disambiguation** — Prompt doesn't distinguish transit cities from residence cities
4. **No photo filename** — Filename "Image 960_compress.jpg" isn't helpful, but collection name is

### Proposed Prompt Additions

Add to Location section of gemini_extraction.py:

```
**Step 2b: Collection & Source Context** (if provided)
- The collection name often indicates geographic origin (e.g., "Tampa Collection" = Tampa)
- Cross-reference visible business names (signs, storefronts) with known family members
  (e.g., "LEON'S RESTAURANT" sign + "Big Leon Capeluto" in family = Leon's business)
- This is STRONG evidence, often more reliable than biographical inference alone

**Step 2c: Immigration & Transit Disambiguation**
- Passenger list and immigration records show ports of entry, which may be TRANSIT points
- A person listed as arriving in San Francisco may have been en route to another city
- Residence events, occupation events, and children's birth places are more reliable
  location indicators than immigration ports of entry
- When visual evidence (signage, architecture) conflicts with immigration records,
  prefer the visual evidence for photo location
```

---

## Predecessor Context

- Session 90b context: `docs/session_context/session-90b-context.md`
- Session 89 context: `docs/session_context/session-89-context.md` (Gemini enrichment)
- AD-201: Unified Gemini prompt (Session 89)
- AD-202: Admin re-analyze button (Session 89)
- AD-146: Face alignment via coordinate bridging (Session 62, PRD-015)
- AD-110: Serving path contract — web requests never run heavy ML (but Gemini API is fine)

## Scripts Available

- `scripts/reprocess_with_gedcom.py --photo-id <ID>` — Re-run Gemini on specific photo
- `scripts/batch_analyze.py` — Batch Gemini analysis
- `/api/photo/{id}/reanalyze` — Admin re-analyze button
- `/api/face-alignment/{id}` — Admin face descriptions button
