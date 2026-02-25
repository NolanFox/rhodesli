# Rhodesli ML Pipeline: Face Identification in a Heritage Photo Archive

## Executive Summary

Rhodesli is an ML-powered heritage photo archive built for the Jewish community of Rhodes, a Sephardic diaspora that scattered across three continents after the Holocaust. The system identifies and matches faces across 271 historical photographs spanning from the 1890s to the present, linking faces to a 21,809-person genealogical database (GEDCOM).

The core technical challenge is face recognition under conditions that break standard approaches: the same person appears as a child in 1920s Rhodes and as a grandparent in 1970s Miami. Photos range from formal studio daguerreotypes to newspaper clippings to phone-photographed prints. The population is endogamous -- most subjects share family resemblance, making false positives from kin far more common than in general face recognition. Standard off-the-shelf thresholds produce unusable results on this data.

The pipeline combines InsightFace embeddings with isotonic similarity calibration (AUC 0.9577), CORAL ordinal regression for date estimation, and Gemini multimodal analysis enriched with genealogical context. Every ML output is a proposal that a human admin adjudicates; confirmed decisions feed back as ground truth for recalibration. The system processes 271 photos with 775 detected faces at a total Gemini API cost under $2 and runs on a Railway hobby instance with 512 MB RAM.

## Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["Ingestion (Local Machine)"]
        PHOTO[Photo Upload] --> INSIGHTFACE[InsightFace buffalo_l<br/>512-dim PFE embeddings]
        INSIGHTFACE --> CROPS[Face Crops + BBoxes]
        INSIGHTFACE --> EMB[embeddings.npy]
        CROPS --> R2[Cloudflare R2]
    end

    subgraph Clustering ["Clustering & Matching"]
        EMB --> GROUPING[Union-Find Grouping<br/>Euclidean < 0.95 threshold]
        GROUPING --> CLUSTER[Agglomerative Clustering<br/>Complete linkage + MLS + Temporal priors]
        CLUSTER --> PROPOSALS[Identity Proposals<br/>state = PROPOSED]
    end

    subgraph Calibration ["Similarity Calibration"]
        CONFIRMED[Admin-Confirmed Pairs] --> ISOTONIC[Isotonic Regression<br/>AUC = 0.9577]
        ISOTONIC --> CALIBRATED[Calibrated P(same_person)<br/>displayed in UI]
    end

    subgraph Alignment ["Gemini Alignment Pipeline"]
        GEDCOM[(GEDCOM 21,809 individuals<br/>Supabase Postgres)] --> CONTEXT[Context Builder<br/>5 enrichment variants]
        CONTEXT --> PROMPT[Unified Extraction Prompt<br/>forensic photo analysis]
        PHOTO2[Photo Bytes] --> GEMINI[Gemini 3.1 Pro<br/>~$0.008/photo]
        PROMPT --> GEMINI
        GEMINI --> ALIGNMENT[Face Descriptions<br/>Date Estimates<br/>Location + Cultural Markers]
    end

    subgraph DateEstimation ["Date Estimation"]
        GEMINI --> SILVER[Silver Labels<br/>decade_probabilities]
        SILVER --> CORAL[CORAL Ordinal Regression<br/>EfficientNet-B0 backbone]
        CORAL --> DECADE[Decade Classification<br/>13 classes: 1900s-2020s]
    end

    subgraph HumanLoop ["Human-in-the-Loop (Gatekeeper)"]
        PROPOSALS --> ADMIN[Admin Review UI]
        CALIBRATED --> ADMIN
        ALIGNMENT --> ADMIN
        ADMIN -->|confirm| CONFIRMED
        ADMIN -->|reject| NEGATIVE[Negative Pairs<br/>rejection memory]
        CONFIRMED --> EMB
        NEGATIVE --> CLUSTER
    end

    style CONFIRMED fill:#2d5016,color:#fff
    style NEGATIVE fill:#8b1a1a,color:#fff
    style GEMINI fill:#1a4d8b,color:#fff
```

## Key Technical Decisions

| Decision | Choice | Rationale | Reference |
|----------|--------|-----------|-----------|
| Identity matching | Multi-anchor (not centroid) | Heritage photos span decades. Averaging a child and grandparent embedding creates a "ghost vector" matching neither. Single-linkage across all anchors preserves signal. | AD-001 |
| Distance metric | Euclidean (runtime), MLS (clustering) | PFE sigma_sq is scalar-uniform in this dataset, making MLS marginal over Euclidean. Open experiment (AD-027). | AD-003 |
| Clustering | Complete linkage + temporal priors | Complete linkage prevents chaining. Bayesian temporal penalties via CLIP era classification penalize cross-era merges. | AD-005 |
| Date estimation | CORAL ordinal regression | Predicting 1940 when the answer is 1950 is less wrong than predicting 2000. Flat cross-entropy treats all errors equally, which is incorrect for ordered decades. | AD-015 |
| Silver labels | Gemini 3.1 Pro (not Flash) | Cost difference is $4 total for 155 photos. Silver labels are the foundation for all downstream training -- quality dominates at this scale. | AD-039 |
| Cultural lag | 5-15 year fashion adjustment | Studio portraits in Sephardic communities used conservative attire that appears older. Without adjustment, dates are systematically biased toward earlier decades. | AD-042 |
| Soft labels | KL divergence (weight 0.3) | Gemini outputs decade_probabilities. Discarding this into hard labels wastes calibrated uncertainty. Standard knowledge distillation (Hinton 2015). | AD-043 |
| Similarity calibration | Isotonic regression | More flexible than Platt scaling for non-standard score distributions. Versioned models with drift detection and automatic recalibration triggers. | AD-149 |
| GEDCOM enrichment | first_order family context | Providing genealogical context (parents, spouses, children, events) transforms Gemini's location accuracy from vague to city-level in 80% of cases. | AD-147 |
| Serving architecture | Local ML, pre-computed serving | Web requests NEVER run heavy ML. InsightFace/PyTorch run locally. Production serves pre-computed JSON, embeddings, and crops only. | AD-007/110 |

## Results

**Face Detection & Matching**
- 775 faces detected across 271 photos (InsightFace buffalo_l, det_size 640x640)
- 55 confirmed identities with 125 golden set mappings
- Five-tier threshold calibration: 100% precision up to distance 1.05 (zero false positives on golden set)
- First false positive at 1.0502: family resemblance between Rosa and Sol Sedikaro (true negative, correct behavior for endogamous population)

**Similarity Calibration**
- AUC = 0.9577 on 348 calibration pairs (isotonic regression)
- Calibrated probabilities displayed in the UI, replacing raw distances
- Automatic recalibration hooks: triggers on 20+ new pairs, 30-day model age, or 50% class ratio shift
- Drift detection: flags threshold shifts > 0.1 for human review

**Gemini Alignment**
- 269 of 271 photos successfully aligned (2 API failures, 0 skipped)
- Total API cost: $1.86 across 269 calls (Gemini 3.1 Pro at ~$0.008/photo)
- 17 photos enriched with GEDCOM genealogical context
- GEDCOM effect: location accuracy improves from generic to city-level in 80% of enriched photos; date precision narrows by 3-7 years; confidence jumps from 60% "high" to 100% "high" with first_order context

**Date Estimation**
- 92% of photos lacked date metadata (EXIF dates are scan timestamps)
- Gemini silver labels with decade_probabilities feed CORAL ordinal regression
- Heritage-specific augmentations: sepia tone, resolution degradation, scanning artifacts, projective distortion (photos-of-photos)

**Cost & Infrastructure**
- Total Gemini cost for full archive: under $2
- Every API call logged to gemini_api_calls table: model, tokens, cost, config, response summary
- Production runs on Railway (Docker, 512 MB RAM, persistent volume)
- InsightFace/PyTorch stay local -- production only serves pre-computed results

## Challenges Overcome

**The Aging Problem.** A person photographed at age 8 in 1925 and again at age 65 in 1982 produces embeddings that are far apart in standard face recognition space. Centroid averaging (the standard approach) creates a meaningless midpoint. Multi-anchor comparison with single-linkage allows matching if ANY pair of faces across the two age groups is close, which is the correct behavior for heritage archives.

**Endogamous Population Bias.** The Rhodes Jewish community was small and intermarried. Most subjects share family resemblance at a level that produces false positives in general-purpose face recognition. The five-tier threshold calibration was designed specifically to handle this: the first false positive in the golden set evaluation was between two members of the same family (Rosa and Sol Sedikaro), exactly the kind of error that a generic system would not flag. The confidence gap metric (distance between 1st and 2nd nearest neighbor, as a percentage) gives the admin a reliable signal for adjudication.

**Historical Photo Quality.** Photos range from 1890s cabinet cards to newspaper clippings to phone photographs of album pages. PFE (Probabilistic Face Embeddings) handles this by design: each embedding carries uncertainty (sigma_sq), and low-quality faces are down-weighted rather than filtered. The system retains every detected face because a blurry match to a great-grandfather is more valuable than no match at all.

**Small Dataset, Big Ambitions.** With 775 faces and 55 confirmed identities, there is insufficient data for fine-tuning or training from scratch. The architecture is designed around this constraint: frozen InsightFace embeddings, lightweight calibration (isotonic regression, 32K-parameter Siamese MLP), knowledge distillation from Gemini silver labels. Each layer adds signal without requiring thousands of labeled examples.

**Cultural Context Gap.** Standard photo dating assumes Western mainstream fashion timelines. Studio portraits in Sephardic communities used deliberately conservative attire that lags mainstream fashion by 5-15 years. Without explicit cultural lag adjustment in the Gemini prompt, dates are systematically biased toward earlier decades. The prompt architecture includes domain-specific context about Rhodes, the Sephardic diaspora, and Ladino cultural markers.

**Genealogical Grounding.** A 21,809-person GEDCOM file provides family structure but no photos. The GEDCOM context builder bridges these worlds: for photos where faces have been identified and linked to genealogical records, it injects birth dates, marriage records, immigration events, and family relationships into the Gemini prompt. Five enrichment variants (none, full, curated, first_order, co_occurrence) were evaluated in a 3-model x 5-variant comparison ($2.46 total). The winner -- Gemini 3.1 Pro with first_order family context -- achieves 100% high-confidence date estimates on linked photos.

## What's Next

**LoRA Fine-Tuning (Session 67).** The 55 confirmed identities now provide enough same-person pairs (~950) for LoRA adaptation of InsightFace's final layers. This would adapt the embedding space to the specific aging patterns and photo styles in this archive. Recalibration of the isotonic regression must follow any embedding space change.

**Active Learning Pipeline.** When the baseline Euclidean model and the calibrated MLP disagree on a pair, that pair is maximally informative for admin review. The architecture supports uncertainty-driven suggestion ordering, which would prioritize the most useful faces for human attention.

**Multi-Community Expansion.** The pipeline is designed to be community-agnostic in its ML components. The GEDCOM context builder, similarity calibration, and Gatekeeper pattern all work with any face archive. Rhodesli-specific domain knowledge (Sephardic cultural markers, Ladino text detection, surname variant matching across transliterations) lives in prompt text and data registries, not in model weights.

**Multi-Pass Gemini Re-Labeling.** Low-confidence date estimates and face descriptions can be re-analyzed with additional context as more faces are confirmed. The progressive refinement architecture (AD-102) supports feeding verified facts back into subsequent Gemini passes, narrowing uncertainty over time.

---

*Built with InsightFace, PyTorch Lightning, Gemini 3.1 Pro, scikit-learn, and FastHTML. ~3,553 tests. 163 algorithmic decisions documented.*
