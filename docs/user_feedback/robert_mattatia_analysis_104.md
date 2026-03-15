# Robert Mattatia — Face Analysis Report (Session 104)

**Requested by:** Claude Benatar (poisson1957@hotmail.com)
**Date:** 2026-03-15
**Question:** "Are these the same person?" (Robert Mattatia)

## Photos Analyzed

### Photo 1: Congo Group (`robert_mattatia_congo_group.jpeg`)
- **Dimensions:** 1600x1200
- **Content:** Group of men in colonial Africa setting (likely Congo/Bukavu, 1950s-60s)
- **Faces detected:** 9
- **Notable:** 3 European men + 6 African men in front of a brick building

### Photo 2: Family Group (`robert_mattatia_family_group.jpeg`)
- **Dimensions:** 557x399
- **Content:** Multi-generational family gathering, outdoor setting
- **Faces detected:** 11
- **Notable:** Mix of adults and children, one man in center wearing glasses and suit jacket

## Robert Mattatia Identification

Based on the historical context (Robert Mattatia lived in Congo/Bukavu and was murdered there in 1967):

- **Congo photo:** The tall man in the center with the pith helmet (colonial sun hat) and white dress shirt is most likely Robert Mattatia — **Congo Face 8** (`inbox_e8b9205ffaa7`)
- **Family photo:** The man in the center wearing glasses and a dark suit jacket — **Family Face 4** (`inbox_97287f9a8014`)

## Cross-Photo Similarity Score

| Pair | Distance | Interpretation |
|------|----------|----------------|
| Congo Face 8 ↔ Family Face 4 | **1.2727** | Below match threshold |
| Congo Face 8 ↔ Family Face 3 | 1.3603 | No match |
| Congo Face 6 ↔ Family Face 4 | 1.4064 | No match |

**Match threshold:** Tier 1 auto-match < 0.85, Tier 2 suggestion < 1.10

**Conclusion:** The ML system **cannot confirm** these are the same person based on face embeddings alone. The distance of 1.2727 is well above the match threshold. However, this is expected given:
1. Different photo eras and quality levels
2. Significantly different lighting/context (colonial Africa vs. family gathering)
3. Glasses in one photo, hat covering face in the other
4. Likely different ages between photos
5. Low resolution in the family photo (557x399)

**Human assessment:** Given the historical context (Robert Mattatia in Congo/Bukavu), the Congo photo center figure wearing the pith helmet is a strong candidate. Visual similarities exist (facial structure, build) but the ML distance doesn't support a confident match.

## Archive Matches

No faces in either photo matched CONFIRMED identities in the archive (closest were 1.17+ to unidentified persons). Two family photo faces showed weak proximity to:
- **Family Face 6:** 1.2061 to David Capeloto (CONFIRMED) — too far for match
- **Family Face 11:** 1.1917 to Moise Capeluto (CONFIRMED) — too far for match

## All Cross-Photo Matches (top 5)

| Congo Face | Family Face | Distance |
|-----------|------------|----------|
| 7 | 4 | 1.1791 |
| 8 | 4 | 1.2727 |
| 1 | 4 | 1.2917 |
| 5 | 4 | 1.3111 |
| 2 | 8 | 1.3167 |

Family Face 4 (the man with glasses) appears as the closest match for multiple Congo faces, suggesting it's the face most "average" or most similar to the group — not necessarily the same person.

## Summary for Claude Benatar

The face comparison tool detected 9 faces in the Congo group photo and 11 in the family photo. The closest cross-photo match (distance 1.27) is between the man with the pith helmet in the Congo photo and the man with glasses in the family photo — however, this is above the confidence threshold for the AI to confirm a match. The photos are from very different contexts and quality levels, which makes AI face matching unreliable. A definitive identification would need additional photos or historical documentation.

Both photos have been permanently saved to the Rhodesli archive with attribution to Claude Benatar.
