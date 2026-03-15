# InsightFace vs Gemini/LLM for Face Matching: Research Summary

**Date:** 2026-03-15 (Session 104)
**Purpose:** Evaluate reliability of ML embeddings vs LLM visual analysis for heritage photo matching

## Key Finding

**InsightFace/ArcFace is the correct primary system. LLMs are a valuable secondary signal.**

| System | LFW Accuracy | Face Verification | Best Use |
|--------|-------------|-------------------|----------|
| ArcFace/InsightFace | 99.4-99.8% | Primary system | High-throughput matching |
| GPT-4o (FaceXBench) | ~50% | Near chance level | Explainability, context |
| Gemini 1.5 Pro (FaceXBench) | ~54% | Near chance level | Explainability, context |
| ChatGPT (avg across DBs) | ~77% | Too many false positives | Soft biometrics |

## When Each Method Fails

### InsightFace Failure Modes
- **Cross-age**: 10-17% accuracy drop on 30-year age gaps
- **Occlusion** (masks, glasses, hats): Severe identity info loss
- **Low resolution**: Degrades at very low res (normalizes to 112x112)
- **Silent failure**: No explanation for why a match failed

### LLM Failure Modes
- **False positives**: Generates convincing but wrong explanations
- **Safety refusals**: Models decline face identification requests
- **Hallucination**: Confabulates matching features
- **Non-deterministic**: Different answers on repeated queries
- **No stable metric**: Can't produce reproducible similarity scores

## Hybrid Approach (Literature Recommendation)

Score-level fusion of embeddings + LLM improved accuracy at **low false match rates** (ICCV 2025). This is exactly the regime that matters for archival photos — the hard cases.

### Recommended Architecture for Rhodesli
1. **InsightFace**: Primary matching (proposals, clustering, auto-match)
2. **LLM (Gemini)**: Secondary signal for:
   - Explaining proposed matches to admins
   - Contextual reasoning (photo era, location, clothing)
   - Breaking ties in ambiguous distance range (1.0-1.3)
   - "Deep Comparison" feature (TOOLS-007)
3. **Human admin**: Final arbiter (Gatekeeper pattern already in place)

## Robert Mattatia Case Study

This session demonstrated the hybrid approach in practice:
- InsightFace: 1.2727 distance → false negative (hat/glasses occlusion)
- Gemini 2.5 Pro: 9/10 confidence → used bone structure + context
- Gemini 3.1 Pro: 8.5/10 → identified periocular occlusion as cause

The LLM succeeded because it could integrate:
- Lower-face geometry (not occluded)
- Age progression reasoning
- Historical context (Congo/Bukavu setting)
- Clothing era analysis

## Caution: LLM False Positive Risk

Gemini's 8.5-9/10 confidence should NOT be treated as proof. The research shows LLMs generate false positives with detailed, convincing explanations. The correct interpretation:
- ML says: "I can't tell" (true — insufficient data)
- Gemini says: "Very likely the same" (plausible but not proof)
- Both together: "Worth investigating further with family members"

## Sources

### Primary Benchmarks
1. **FaceXBench** (Jan 2025) — 26 open-source + 2 proprietary MLLMs, 14 face tasks, 5000 questions. GPT-4o ~50%, Gemini ~54% on face verification. https://arxiv.org/html/2501.10360v2
2. **FRoundation** (Oct 2024) — Pre-trained foundation models vs face-specific models. Fine-tuned foundation models promising when training data limited. https://arxiv.org/abs/2410.23831
3. **Foundation vs Domain-specific Models** (ICCV 2025 Workshop) — GPT-4o, Grok-4, CLIP, BLIP vs ArcFace/AdaFace. Domain-specific wins on all benchmarks. Score fusion improves at low FMR. https://arxiv.org/html/2507.03541v2

### ChatGPT/LLM Face Recognition Studies
4. **How Good is ChatGPT at Face Biometrics?** (Jan 2024) — Recognition, soft biometrics, explainability. ~77% avg accuracy, false positive tendency. https://arxiv.org/abs/2401.13641
5. **ChatGPT and Biometrics** (Mar 2024) — Face recognition, gender, age estimation. 97.5% on Black faces, 83.9% on White (demographic variance). https://arxiv.org/abs/2403.02965
6. **Face to Face: Comparing ChatGPT with Human Performance** (2024) — Direct comparison with human face matching. https://pmc.ncbi.nlm.nih.gov/articles/PMC11646356/
7. **Benchmarking MLLMs for Face Recognition** (Oct 2025) — Multi-model benchmark. https://arxiv.org/html/2510.14866v1

### Specialized Topics
8. **Synthetic Face Ageing** (Jun 2024) — Evaluation of age-robust facial recognition. Cross-age degradation analysis. https://arxiv.org/html/2406.06932v1
9. **Impact of Image Resolution on Age Estimation** (Nov 2025) — DeepFace and InsightFace resolution study. https://arxiv.org/html/2511.14689v1
10. **Masked Face Recognition Challenge** — InsightFace track report on occlusion handling. https://researchgate.net/publication/356518573
11. **50 Years of Automated Face Recognition** (May 2025) — Comprehensive survey. https://arxiv.org/html/2505.24247v1/
12. **GPT-4 Emergent Facial Recognition** — Without explicit training. https://idtechwire.com/gpt-4-demonstrates-emergent-facial-recognition-capabilities-without-explicit-training-study/
13. **FaceLLM** (ICCV 2025 Workshop) — Multimodal LLM for face understanding. https://openaccess.thecvf.com/content/ICCV2025W/FoundGen-Bio/papers/
14. **llm-face-vision benchmark** — GitHub repo with benchmark code. https://github.com/yhenon/llm-face-vision

## Breadcrumbs
- BACKLOG: TOOLS-007 (Deep Comparison), TOOLS-008 (reliability research)
- Session 104 Gemini analysis: docs/user_feedback/robert_mattatia_gemini_comparison_104.md
- AD-225 (Compare community scoping)
