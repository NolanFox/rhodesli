# Date Estimation Decisions & Research

This document captures the research, rationale, and decision provenance for the date estimation pipeline. Developed during Session 23 planning through extensive analysis including web research on current model pricing, capability benchmarks, and expert review.

---

## Decision 1: Model Selection — Gemini 3 Pro Preview

### What we chose
`gemini-3-pro-preview` for production silver labeling, `gemini-3-flash-preview` for free-tier testing.

### What we considered
| Model | Input $/1M tokens | Output $/1M tokens | Vision quality | Cost for 155 photos | Status |
|-------|-------------------|--------------------|----|---------------------|--------|
| Gemini 2.0 Flash | $0.10 | $0.40 | Adequate | ~$0.15 | **Deprecated March 31, 2026** |
| Gemini 2.5 Flash | $0.30 | $2.50 | Good | ~$0.47 | Stable, good price/performance |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Lower | ~$0.15 | Cheapest, but weakest vision |
| Gemini 3 Flash Preview | $0.50 | ~$3.00 | Very good + agentic vision | ~$0.70 | Free tier available |
| Gemini 3 Pro Preview | $2.00 | $12.00 | **SOTA — "frontier of vision AI"** | ~$4.27 | Best multimodal reasoning |

### Why Gemini 3 Pro
- Google describes Gemini 3 Pro as "a generational leap from simple recognition to true visual and spatial reasoning" and "the frontier of vision AI" (Source: blog.google, Dec 2025)
- SOTA performance on MMMU Pro (complex visual reasoning) benchmarks
- New `media_resolution` parameter allows granular control over tokens per image for higher fidelity on ambiguous photos
- Preserves native aspect ratio of images (quality improvement for varied photo sizes)
- Dynamic thinking with `thinking_level` parameter — can use "high" for complex forensic analysis

### Why NOT cheaper models
- Cost difference between cheapest ($0.15) and best ($4.27) is $4.12 for the entire dataset — false economy to optimize cost over quality at this scale
- Silver labels are the foundation for ALL downstream ML. Bad labels propagate through the entire pipeline.
- Gemini 2.0 Flash is deprecated March 31, 2026 — building on it guarantees breakage within 6 weeks

### Why NOT Claude or GPT-4o
- Gemini models show strongest performance on vision understanding benchmarks specifically
- Free tier for testing (3 Flash) lets us validate pipeline at $0 before committing spend
- GPT-4o would be ~$30+ for 155 photos at comparable quality; Claude vision similar. Gemini 3 Pro is 7x cheaper.

### Cost math
Per photo: ~1,790 input tokens (image + prompt) + ~2,000 output tokens (structured JSON)
- Input: 1,790 x $2.00/1M = $0.00358; Output: 2,000 x $12.00/1M = $0.024
- Per photo: ~$0.028; 155 photos: ~$4.27

---

## Decision 2: Year vs Decade Estimation — Two-Layer Architecture

### What we chose
Gemini outputs year-level estimates (`best_year_estimate`, `probable_range`). PyTorch model trains on decade classes (10 classes, CORAL ordinal regression).

### Context
MyHeritage's PhotoDater achieves estimates within 5 years ~60% of the time (Source: blog.myheritage.com, Aug 2023). Trained on tens of thousands of definitively dated historical photos from Library of Congress.

### Why two layers
**Layer 1 — Gemini (one-time, paid):** Year-level, evidence-backed estimates for existing photos. Displays as "circa 1937 (+-5 years)" in app UX.
**Layer 2 — PyTorch (trains locally, free):** Decade-level classification for new photos without API calls. When someone uploads 50 photos, the local model handles it.

### Why PyTorch trains on decades, not years
- 155 photos / ~10 decades = ~15 per class (viable). 155 / 100+ years = 1-2 per class (not viable).
- MyHeritage needed tens of thousands for year-level. We have zero ground truth — labels are themselves Gemini estimates.
- CORAL on 10 classes is robust. CORAL on 100+ sparse classes would overfit.
- Sub-decade signal still available: P(1930s)=0.6 + P(1940s)=0.3 -> expected year ~ 1937

### Future: Revisit year-level training at 500+ confirmed-date photos. Infrastructure supports it — change `num_decades` in config.

---

## Decision 3: Evidence-First Prompt Architecture

### What we chose
Decomposed analysis: 4 independent evidence categories, per-cue strength ratings, structured JSON output.

### What we rejected
1. **Original prompt (narrative):** Single prose "reasoning" field. Not queryable, not auditable, encourages overconfident guessing.
2. **Assistant's revision (forensic checklist):** Better layered analysis but encourages hallucinated specifics ("1955 Chevy Bel Air"), collapses to narrative, no capture vs print distinction.
3. **Expert's Version 3 (adopted):** Forces decomposition, per-cue strength weighting, range thinking, anti-hallucination instructions, capture/print separation.

### Why structured evidence matters for Rhodesli
- Cross-query: "All photos with scalloped borders" -> date range clustering
- Contradiction detection: print format says 1960s but fashion says 1930s -> flag as reprint
- Retroactive updates: new heuristics discovered -> re-score existing evidence without re-running Gemini
- Audit trail: every estimate traceable to specific cues with rated strength

---

## Decision 4: Cultural Lag Adjustment

### What we chose
Explicit prompt instruction: fashion in Rhodes and immigrant communities lagged 5-15 years behind Paris/London mainstream.

### Why
- Standard fashion-dating calibrated to Western mainstream
- Rhodes was isolated Sephardic community; immigrants adopted American fashion gradually
- Studio portraits used deliberately conservative formal attire
- Without adjustment, model systematically skews late (estimates photos as older than they are)
- Source: Expert review (Sessions 15-16)

---

## Decision 5: Soft Label Training via KL Divergence

### What we chose
PyTorch model trained on Gemini's decade probability distributions using KL divergence auxiliary loss, not hard labels.

### Why
- Hard label "1940s" discards useful uncertainty. Soft distributions preserve calibrated signal.
- Standard knowledge distillation technique (Hinton et al., 2015)
- Produces better-calibrated confidence scores for regression gate and UX
- Deferred: Multi-pass Gemini aggregation (5 passes at different temperatures) for empirically robust distributions. Would 5x cost (~$21). Consider for low-confidence photos only.

---

## Decision 6: best_year_estimate Display Field

### What we chose
Gemini outputs `best_year_estimate` (integer year) alongside `estimated_decade` and `probable_range`.

### Why
- "circa 1937" more compelling than "1930s" for genealogy UX and engagement/sharing
- Matches MyHeritage user expectations
- Simpler than computing weighted average from decade_probabilities in app layer
- Three granularity levels: `best_year_estimate` (display), `probable_range` (uncertainty), `decade_probabilities` (full distribution)

---

## Decision 7: Heritage-Specific Augmentations

### What we chose
Custom augmentation pipeline: sepia simulation, resolution degradation, film grain noise, JPEG compression artifacts, scanning artifacts, geometric distortion (photos-of-photos), fading simulation.

### Why not standard augmentations only
Heritage photos have domain-specific degradation patterns absent from standard augmentation libraries. Expert review specifically recommended geometric distortion: "Photos-of-photos taken at angles are common in heritage work."

---

## Research References

1. **MyHeritage PhotoDater** (Aug 2023): Tens of thousands of training photos, within 5 years ~60%. blog.myheritage.com/2023/08/introducing-photodater
2. **Gemini 3 Pro Vision** (Dec 2025): "Frontier of vision AI", SOTA MMMU Pro. blog.google/innovation-and-ai/technology/developers-tools/gemini-3-pro-vision/
3. **"A Matter of Time"** (arXiv 2510.19559): Temporal awareness in 37 VLMs
4. **CORAL** (Cao, Mirjalili, Raschka 2020): Rank Consistent Ordinal Regression
5. **Gemini 3 Agentic Vision** (Feb 2026): 5-10% vision benchmark boost. marktechpost.com/2026/02/04/
6. **Gemini API Pricing** (Feb 2026): ai.google.dev/gemini-api/docs/pricing
