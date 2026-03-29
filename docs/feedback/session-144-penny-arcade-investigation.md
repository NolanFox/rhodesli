# Session 144: Penny Arcade Photo Strip Investigation

**Date:** 2026-03-28
**Session:** 144 (interactive investigation)
**Photo:** `inbox_fox-charlie-001_391_02154_p_13akf5twbc3552_r`
**Collection:** Charles Fox Dayton Ohio Collection

---

## FB-004: Penny Arcade Photo Strip Not Detected by AI

**Severity:** P1
**Context:** User discovered that photo `inbox_fox-charlie-001_391_02154_p_13akf5twbc3552_r` is actually 3 photos stitched together — a "penny arcade" or "sticky-back" photo strip from the early 1900s. None of the automated AI analysis detected this.

### What happened
- The photo contains 3 sequential poses of 2 people (Albert Fox + an unidentified woman), arranged vertically as a photo strip
- 4 separate Gemini API runs all described it as a single group portrait of 6 people
- Every run got the face count wrong (6 instead of 2 people x 3 frames)
- Scene description, group composition, and face analysis are all incorrect for this photo

### What should have happened
- AI should detect visual boundaries between frames (vertical creases, repeated subjects)
- Each frame should be analyzed separately as an independent pose/moment
- Face count should reflect unique individuals (2), not total face detections across all frames (6)

### Gemini Chat confirmation
When explicitly asked, Gemini Chat correctly identified the photo as a penny arcade strip:
- Popular novelty photography of early 1900s
- Camera used sliding plate back or multiple lenses for rapid successive exposures
- Cheap, fun souvenirs — subjects changed poses between clicks
- Physical artifact shows vertical creases between frames (folded to fit in wallet)

### Dating and provenance (from Gemini Chat)
- High stiff detachable club collar, ruffled lapels, "spit curls" place this at 1910-1915
- Location: likely Coney Island boardwalk studio or Bowery penny arcade (New York amusement area)
- Pre-dates Albert Fox's 1920 marriage to Esther Burd by several years
- Body language progression across 3 frames suggests close relationship (romantic or familial)

### Feature idea: Multi-frame detection
Detect when a photo contains multiple frames, poses, collages, or photo strips, and analyze each frame separately. This would correct:
- Face count (unique individuals vs total detections)
- Scene description (sequential poses vs group portrait)
- Group composition analysis
- Face clustering (same person across frames should merge, not create 3 separate identities)

**Fix:** Feature idea logged below. Current Gemini batch analysis has no multi-frame awareness.
**BACKLOG:** Candidate for future PRD (multi-frame photo detection)

---

## FB-005: Identity Investigation Workflow

**Severity:** P2 (feature gap, not a bug)
**Context:** User conducted a multi-step identity investigation starting from the penny arcade photo, demonstrating both the power of the current tools and gaps in the investigation workflow.

### Investigation steps performed

1. **Merged faces:** Combined the 3 detections of the unidentified woman in the penny arcade strip into Person 3481
2. **Checked similar identities for Person 3481:**
   - Top match: Person 3652 — wrong era (Charles Fox date range), rejected
   - Next match: Person 3772 — almost certainly Albert Fox on wedding day (military uniform)
3. **Investigated Person 3772:**
   - Has 3 photos from "Charles Fox Dayton Ohio Collection"
   - Wedding/military photos
   - The woman WITH Person 3772 in those photos is Esther Burd
4. **Cross-person comparison:**
   - Person 3481 (penny arcade woman) does NOT closely match Esther Burd
   - Different person? Possibly a sister, cousin, or early courtship before Esther
5. **Facial recognition anomaly discovered:**
   - Albert Fox (identity `85546ebf-75b9-4971-a9d4-b2ce2271bc19`, 196 confirmed faces) shows 0% match / Distance 1.29 to Person 3772
   - Person 3772 is almost certainly Albert Fox himself (wedding photo)
   - 1.29 distance for the same person is a significant facial recognition failure

### Investigation questions (open)

| Question | Status | Notes |
|----------|--------|-------|
| Who is Person 3481? | OPEN | Woman in penny arcade photo. Not Esther Burd. Possibly sister, cousin, or early courtship. |
| Why does Albert Fox (196 faces) show 0% / dist 1.29 to Person 3772? | OPEN | Military uniform vs civilian, age difference, photo quality, face angle could all contribute. This is a facial recognition failure worth diagnosing. |
| Are Persons 2579 or 3503 other photos of Person 3481? | OPEN | Both are matches to Person 3772 — need cross-investigation. |
| Is Person 3772 confirmed as Albert Fox? | LIKELY | Military uniform, wedding context, Charles Fox collection provenance all point to Albert. |

### Key person IDs

| Person | Description | Notes |
|--------|-------------|-------|
| Person 3481 | Unidentified woman in penny arcade photo | 3 merged faces from photo strip |
| Person 3772 | Unidentified person in wedding/military photos | Almost certainly Albert Fox |
| Person 3652 | Wrong era match | Charles Fox date — false positive from similar identities |
| Person 2579 | Top match to 3772 (80%, dist 0.62) | Needs investigation |
| Person 3503 | Strong match to 3772 (77%, dist 0.66) | Needs investigation |
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` (196 faces) | Shows 0% match to 3772 — anomalous |

---

## Facial Recognition Failure Analysis

### Albert Fox 0% match to his own wedding photo

This is a concrete, reproducible facial recognition failure:

- **Known identity:** Albert Fox, 196 confirmed anchor faces
- **Target:** Person 3772, almost certainly Albert Fox in military uniform (wedding photo)
- **Score:** 0% match, distance 1.29
- **Expected:** High match (>70%, distance <0.90)

### Possible causes

1. **Clothing/uniform effect:** Military uniform with high collar may alter face detection bounding box or confuse embedding model
2. **Age gap:** Penny arcade strip dated 1910-1915; Albert's confirmed faces may cluster around different decades
3. **Photo quality:** Early 1900s photo quality vs later photos in the confirmed set
4. **Face angle:** Different pose angles across frames
5. **Embedding model limitation:** InsightFace PFE embeddings may struggle with dramatic appearance changes (uniform, age, photo era)

### Diagnostic value

This case is valuable for understanding embedding model limitations:
- Same person, verified by provenance and context
- Large embedding distance (1.29) despite identity certainty
- Could inform threshold tuning, multi-prototype approaches, or temporal modeling (PRD-038)

---

## Feature Ideas for Future PRDs

### 1. Multi-frame photo detection
- Detect penny arcade strips, collages, photo montages, contact sheets
- Segment into individual frames before face detection and AI analysis
- Correct face counts and scene descriptions per-frame
- Related: existing collage override feature (PRD for same-photo co-occurrence blocks)

### 2. Cross-person identity investigation workflow
- "Who is the person WITH this person?" query
- Given Person X in Photo Y, show all other faces in that photo with their identity status
- Enable relationship-based identity inference

### 3. Face recognition failure analysis (admin tool)
- Show WHY a known match scores low
- Visualize: bounding box quality, embedding distance breakdown, quality scores
- Compare face crops side-by-side with distance metrics
- Help admin understand when to trust vs override ML scores

### 4. Investigation notebook
- Log of identity research steps, hypotheses, evidence
- Per-person or per-investigation timeline
- "I think Person 3481 is X because of Y" — structured hypothesis tracking
- Links to photos, similar identities, GEDCOM records used as evidence

### 5. Co-occurrence identity inference
- "Person X appears in photos from era Y in location Z with Person A"
- Combine temporal, geographic, and social context to narrow candidates
- Related: PRD-059 (temporal co-occurrence analysis) — extend with identity inference

### 6. GEDCOM-aided disambiguation
- Use family tree to generate candidate identities for unknown persons
- "Albert Fox had sisters: [list]. Person 3481 could be one of them."
- Cross-reference GEDCOM birth/death dates with photo dating estimates
- Surface GEDCOM relationships as investigation hints

---

## Gemini Chat Analysis (Full Findings)

User conducted a separate Gemini Chat session with the penny arcade photo. Key findings:

### Physical artifact
- Penny arcade / sticky-back photo strip
- 3 sequential poses of the same 2 people
- Vertical creases between frames from being folded to fit in a wallet
- Common souvenir format from early 1900s amusement areas

### Photography technology
- Camera used sliding plate back or multiple lenses for rapid successive exposures
- Automated or semi-automated process — operator triggered multiple exposures in quick succession
- Cheap novelty format — pennies per strip
- Popular at Coney Island, boardwalks, and amusement arcades

### Dating evidence
- Man's high stiff detachable club collar
- Ruffled lapels on jacket
- Woman's "spit curls" hairstyle
- Collectively date the photo to approximately 1910-1915

### Identity analysis
- Man: consistent with young Albert Fox (pre-marriage)
- Woman: NOT identified as Esther Burd — different facial features
- Body language across 3 frames shows increasing familiarity/comfort
- Suggests close relationship — romantic courtship or close family member

### Historical context
- Pre-dates Albert Fox's 1920 marriage to Esther Burd by 5-10 years
- Albert would have been in his late teens or early 20s
- Location likely New York City area (Coney Island or Bowery)
- Fox family was in New York during this period (confirmed by GEDCOM)

---

## Session Notes

- This investigation was conducted interactively by the user (Nolan) during Session 144
- No code changes were made — this is a documentation-only capture of findings
- The penny arcade photo represents a class of archival photos that current AI analysis handles poorly
- The Albert Fox 0%/1.29 match failure is a concrete test case for embedding model evaluation
- Person 3772 should be investigated further and likely confirmed as Albert Fox
- Person 3481 remains an open identity question requiring GEDCOM research
