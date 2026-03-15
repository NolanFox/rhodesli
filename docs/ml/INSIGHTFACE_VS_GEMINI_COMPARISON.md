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
- FaceXBench (2025): arxiv.org/html/2501.10360v2
- FRoundation (2024): arxiv.org/abs/2410.23831
- Foundation vs Domain-specific (ICCV 2025): arxiv.org/html/2507.03541v2
- ChatGPT Biometrics (2024): arxiv.org/abs/2401.13641

## Breadcrumbs
- BACKLOG: TOOLS-007 (Deep Comparison), TOOLS-008 (reliability research)
- Session 104 Gemini analysis: docs/user_feedback/robert_mattatia_gemini_comparison_104.md
- AD-225 (Compare community scoping)
