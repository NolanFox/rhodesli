---
name: Fox sibling resemblance case study
description: Albert and Harry Fox look nearly identical to ML — disambiguation requires temporal context and co-occurrence, not embeddings. Key case study for family archive ML limitations.
type: project
---

Albert Fox and Harry Fox (brothers) are so visually similar that:
- ML embeddings cannot distinguish them (3/4 Dayton Harry faces score closer to Albert centroid)
- David Fox (Albert's grandson) said Harry's naturalization form photo "Resembles Poppy [Albert]"
- At certain life stages they were nearly identical in photos

**Why:** This is biological reality, not an ML bug. The embedding model measures geometric face similarity which genuinely cannot distinguish these siblings.

**How to apply:**
- When ML proposes a match between Fox family members, co-occurrence and temporal context are the disambiguation tools, not distance
- Charlie Fox's age in photos serves as a temporal anchor for dating photos
- Co-occurrence (Albert + unknown in same photo) is strong evidence the unknown is NOT Albert
- Community testimony (David Fox) is irreplaceable but has limits — David knows Albert (his grandfather) but wouldn't know Harry (uncle) well
- Person 4063 cluster is contaminated: P2 = Albert (beach with Esther), P1+P3 = likely Harry. See `docs/session_context/investigation-4063-harry-fox.md`
- CLUSTER-QUALITY-001 resolved: Dayton photos ARE Harry, ML distances are expected sibling confusion
