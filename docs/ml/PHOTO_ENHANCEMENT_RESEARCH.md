# Photo Enhancement Research

**Last updated:** 2026-02-12

## Summary

Photo enhancement (super-resolution, face restoration) is **UX-only** and must NEVER be used for ML/face matching. Enhanced images are only for human viewing comfort.

**Decision:** AD-037 — Rejected face restoration as preprocessing.

---

## Research Papers

### 1. CodeFormer + Face Recognition (ScienceDirect, 2024)

**Finding:** CodeFormer face restoration increased Cllr (log-likelihood cost) in forensic face comparison, meaning restored faces were HARDER to match, not easier. The hallucinated details diverge from the original identity embedding.

**Implication:** Restoration introduces identity-altering artifacts. Embeddings extracted from restored vs original faces produce different distances, degrading match accuracy.

### 2. Effective Adapter for Face Recognition (2024)

**Finding:** Domain gap between clean training data and degraded real-world photos is a real problem. The proposed "dual-branch adapter" processes both original and restored images through separate branches, combining them for recognition.

**Implication:** A dual-branch approach could theoretically work, but requires fine-tuning a new adapter network on domain-specific data. Too complex for Rhodesli's current scale (550 faces).

**Revisit condition:** When implementing LoRA fine-tuning (Phase D), consider dual-branch as an experiment.

### 3. Face Quality vs Recognition (Springer, 2021)

**Finding:** Fewer than half of enhancement techniques improve face recognition accuracy. Many techniques that improve visual quality (human perception) degrade recognition accuracy (machine perception).

**Key insight:** Human and machine "quality" are different metrics. A photo that looks better to a person may contain hallucinated features that confuse a face recognition model.

---

## Rhodesli Approach

### For ML Pipeline
- Use PFE (Probabilistic Face Embeddings) which mathematically handles quality uncertainty
- Low-quality faces get high sigma_sq (uncertainty), reducing their influence on matching
- No preprocessing, no restoration, no enhancement before embedding extraction
- Face quality scoring (AD-038) prioritizes display, never filters from ML

### For UX Display (Future)
If implementing an "Enhance" toggle for viewing comfort:
1. Default OFF — always show original
2. Enhancement computed lazily on first toggle, cached
3. Show "Enhanced" badge when viewing enhanced version
4. Primary: GFPGAN (lighter weight than CodeFormer)
5. Fallback: bilateral filter + CLAHE + unsharp mask (no heavy deps)
6. Enhanced crops stored alongside originals (non-destructive)
7. NEVER use enhanced images for embedding extraction

---

## Related Decisions

| Decision | Summary |
|----------|---------|
| AD-037 | Face restoration rejected as preprocessing |
| AD-010 | No hard quality filter — PFE handles quality |
| AD-038 | Face quality scoring for display prioritization |
| AD-002 | Embeddings generated once, never regenerated |
