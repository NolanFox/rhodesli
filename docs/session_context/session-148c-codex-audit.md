**Auditor**: Codex CLI — UNAVAILABLE (model at capacity)
**Fallback**: Claude Code self-audit (same session)
**Phase**: Nellie Kubrin identification investigation
**Date**: 2026-04-14

## Self-Audit of Nellie Investigation

### P1: Methodology Bias — Sherry Distance as Primary Filter
The initial search used Sherry embedding distance to rank 20 candidate photos. This biased toward photos where Sherry's face was detected — which means we ONLY searched photos that contained young women similar to Sherry. An older woman like Nellie would have HIGH distance to Sherry, not low. The correction (searching ALL 328 faces and clustering by person) was the right fix, but the initial approach wasted Chrome screenshots on the wrong photos.

**Action:** Documented as methodology learning. Future searches should start with "all faces in collection" not "faces near known person."

### P1: Cross-Cluster Identification Unverified
The investigation claims the same woman spans Clusters 2, 3, and 11. But the embedding system gave these faces distances of 0.96-1.29 apart — well above the 1.0 clustering threshold. The visual identification is based on subjective assessment (glasses, dress), not embedding confirmation. This COULD be two different women who both wear glasses and similar dresses at the same wedding.

**Action:** Need user to confirm. Also need to compute the actual pairwise distances between the specific face IDs claimed to be Nellie. If the parents-portrait face (inbox_8702ce09b7f4) and the head-table face (inbox_bfe60ad388ab) have distance > 1.3, the embedding system is saying "different person" and we should weight that.

### P2: Missing Parents Portrait Embedding Distance
The parents portrait face (inbox_8702ce09b7f4) wasn't included in the distance analysis or clustering. It was only identified visually. Need to compute its distance to the Cluster 11 faces.

### P2: Abraham Fader vs David Josowitz Disambiguation
Two different older men appear in the wedding photos. The investigation noted this but didn't pursue it. Both men are potential identification targets.

### P2: Data Format Not API-Compatible
The investigation JSON doesn't match the gemini_api_calls table schema. Need a mapping plan for how this type of investigation would be stored.

### P3: Cluster 1 Dismissal Without Evidence
Cluster 1 (5 faces, avg sherry dist 0.89) was dismissed as "young women" without viewing all photos. At least one (40CACDE5) shows a short woman next to a taller woman — could be an older person.

### P3: No Ira Distance Signal Used
The analysis computed distance to Sherry centroid but never used Ira centroid. Nellie would have no particular similarity to Ira, but Anna Josowitz (groom's mother) WOULD be closer to Ira. This could disambiguate Nellie vs Anna.

## Summary
- P1: 2 (methodology bias, cross-cluster unverified)
- P2: 3 (missing embedding, disambiguation, data format)
- P3: 2 (cluster dismissal, Ira distance unused)
- Overall: The visual identification is strong but needs embedding confirmation and user review. The methodology learnings are valuable for future feature development.
