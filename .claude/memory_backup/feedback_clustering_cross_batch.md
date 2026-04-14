---
name: Clustering must work across batches, not just initial upload
description: Fundamental gap — clustering only groups within a single upload batch. New uploads never compared against existing faces. Human-in-loop for cross-batch, no auto-merge. Google Photos false positives were a bad experience.
type: feedback
---

Clustering only running at initial upload is fundamentally broken. Key requirements:

1. **Within-batch grouping** (0.95 threshold, auto-merge) — works, keep it
2. **Cross-batch matching** (proposals only, NO auto-merge) — MISSING, PRD-049
3. **Notify uploader** when matches found — the value moment
4. **Re-match after confirming** an identity — surfaces existing faces that match
5. **Non-destructive, reversible** — every merge must have undo + full audit trail
6. **Resilient to family resemblance** — Charles Fox ↔ Roland Fox at distance 0.50 means no threshold is safe for auto-merge

**Why:** Session 108. James Fields uploaded (2 photos, 9 faces) but never compared against 1652 existing Fox Family faces. Person 3474 at distance 0.87 was an obvious match but invisible. Google Photos false positives (auto-merging family members) were a frustrating experience Nolan wants to avoid.

**How to apply:** Every clustering/ML feature must check PRD-049 for the cross-batch design. Never auto-merge across batches. Always proposals + human review.
