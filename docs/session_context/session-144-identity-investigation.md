# Session 144: Identity Investigation — Persons 3481 and 3772

**Photo**: Penny arcade strip `02154_p_13akf5twbc3552_r.jpg` (3 sequential poses)
**URL**: https://rhodesli.nolanandrewfox.com/c/fox-family/photo/inbox_fox-charlie-001_391_02154_p_13akf5twbc3552_r

---

## Investigation 1: Who is Person 3481? (Unidentified Woman)

### Summary
The woman appears in all 3 frames of a penny arcade photo strip with Albert Fox, dated ~1912-1918 in New York. Gemini estimates her age at 20-24.

### Candidate Ranking (Claude Code Agent)

| Rank | Candidate | Born | Age in ~1915 | Evidence | Confidence |
|------|-----------|------|-------------|----------|------------|
| 1 | **Rachel (Ray Ronya) Fox** | Oct 1891 | 24 | Perfect age fit, closest sister to Albert (5 yr gap), in Brooklyn by 1910, no photos to compare | **55%** |
| 2 | Sadie Fox Levine | ~1888 | 27 | Closest female embedding match (1.137), in Manhattan by 1910, slightly old for estimate | 30% |
| 3 | Esther Burd | ~1900 | 15 | Too young (12-18 in photo era), didn't marry Albert until 1920 | Unlikely |
| 4 | Bessie / Sarah Fox | ~1884 | 31 | Too old for 20-24 estimate | Unlikely |

### Key Evidence
- Rachel Fox is the closest Fox sister in age to Albert — natural companions for a day out
- Rachel married Aaron Harry Newman in Brooklyn, Apr 1910 — confirmed in NYC during photo era
- NO confirmed face photos of Rachel exist in the archive — can't compare embeddings
- Esther Burd (born ~1900) would be only 12-18 — too young for Gemini's 20-24 age estimate
- Body language across 3 frames (progressively more relaxed) suggests close relationship — sibling or romantic

### What Would Confirm
1. Find other photos of Rachel Fox/Newman for embedding comparison
2. Check if Albert had known courtships before Esther (1920 marriage)
3. Visual comparison with Fox family photos from the 1910s era

### Data Issue
Person 3481's faces are multi-claimed across Persons 3485 and 3486 — the 3 faces from the strip should all belong to 3481.

---

## Investigation 2: Why Does Albert Fox (196 faces) Score 0% to Person 3772?

### Summary
Person 3772 has 3 photos — ALL are couple photos paired exclusively with Esther Burd Fox. Despite this strong co-occurrence evidence, face recognition gives only 27% match (distance 1.29).

### Distance Analysis (Claude Code Agent)

| Metric | Value |
|--------|-------|
| Centroid-to-centroid L2 | 1.026 |
| Best face-to-face L2 | 1.290 |
| Albert intra-cluster max pairwise | 1.424 |
| Proposal threshold | 1.05 |
| UI display at 1.29 | ~27% (shown as 0%) |

### Why It Fails: The Fox Family Resemblance Problem

Person 3772's closest confirmed identities by centroid distance:

| Rank | Person | Distance |
|------|--------|----------|
| 1 | Roland Fox | 0.971 |
| 2 | Leona Fox Smilg | 0.980 |
| 3 | Charles Fox | 0.982 |
| 4 | Esther Burd Fox | 0.997 |
| 9 | **Albert Fox** | **1.026** |

**Person 3772 is equidistant from the ENTIRE Fox family.** The embeddings can tell it's a Fox/Burd family member but cannot distinguish which one.

### Root Causes
1. **Cluster heterogeneity**: Albert's 196-face cluster spans teens to elderly. The centroid is a blurry average.
2. **Family resemblance**: Fox siblings' embeddings are closer to each other than to non-family. ~1.2-1.3 distances between family members are at the recognition boundary.
3. **Era-specific appearance**: Wedding/military photos show Albert in a context not represented in his 196-face cluster.
4. **Albert/Harry confusion**: Documented case (CLUSTER-QUALITY-001) — Albert and Harry are nearly indistinguishable by embeddings.

### Recommendation
**Manual merge is warranted.** Co-occurrence evidence (always paired with Esther, same collection) is stronger than face recognition for this case. After merge, the 3 new faces will expand Albert's cluster to cover the wedding era.

### Persons 2579 and 3503
Both appear in group photos WITH Esther. Small face crops (86-154px). Equidistant from all Fox family members — need visual inspection, not automated matching.

---

## Synthesized Insights for Product Development

### The Core Problem
Face recognition works well for distinguishing strangers but struggles with **intra-family disambiguation**. The Fox family demonstrates this clearly:
- All Fox siblings cluster near each other (~1.0-1.3 L2 distance)
- The system can identify "this is a Fox" but not "this is Albert vs Harry vs Charles"
- The proposal threshold (1.05) excludes family members from automated matching

### What Works Instead of Face Recognition
1. **Co-occurrence**: Person 3772 ALWAYS appears with Esther → almost certainly Albert
2. **Temporal context**: Photo dating (Gemini) + GEDCOM birth dates → age-appropriate candidates
3. **GEDCOM relationships**: Sister/brother/spouse connections narrow the candidate pool
4. **Visual detail analysis**: Clothing, uniforms, rings, posture (Gemini Chat excels here)

### Feature Implications (PRD Candidates)

| Feature | Problem It Solves | Priority |
|---------|------------------|----------|
| **Co-occurrence identity inference** | 3772 → paired with Esther = Albert | P0 |
| **Multi-frame photo detection** | Penny arcade strip misidentified as 6-person group | P1 |
| **Family disambiguation tool** | Fox family members equidistant in embedding space | P1 |
| **Investigation notebook** | Log hypothesis + evidence chain (3481 investigation) | P2 |
| **Recognition failure analysis** | Admin: "why does X not match Y?" with distances | P2 |
| **GEDCOM candidate ranking** | Filter identities by age/location/relationship | P2 |

---

## Codex Assessment
*Pending — will be appended when complete.*
