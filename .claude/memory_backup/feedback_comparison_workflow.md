---
name: Comparison workflow should be in-app
description: The manual embedding comparison workflow (sync embeddings, compute distances, compare centroids) should become an in-app admin tool. Nolan explicitly asked for this.
type: feedback
---

When investigating identity matches (Person 2491 vs Harry Fox, Person 4063, etc.), we currently do this manually:
1. Sync production embeddings to local
2. Write Python scripts to compute L2 distances
3. Compare against centroids (Albert: 160 anchors) and individual faces
4. Cross-reference with co-occurrence, temporal context, family testimony

**Why:** This workflow is the core value proposition. Admin should be able to do this from the UI, not via CLI scripts. Every investigation requires a developer.

**How to apply:** This maps to several existing roadmap items:
- TOOLS-003 (Face Compare Real-Time) — needs ML service extraction first
- The "compare" page exists but only for uploaded photos, not for comparing identities against each other
- Missing: "Compare Person X to Person Y" with distance matrix, centroid comparison, co-occurrence analysis
- Missing: "Who could this be?" tool that ranks all confirmed identities by distance to a selected face
- The embeddings sync gap (local vs production) is STILL a friction point despite PRD-051 — embeddings.npy is the one file that stays on disk, not in Supabase
