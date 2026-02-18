# Year Estimation Research

**Created:** 2026-02-18 (Session 46)

## Prior Art

### MyHeritage PhotoDater (2023)
Scene-based CNN trained on dated historical photos 1860-1990. Within 5 years of actual date ~60% of the time. Uses visual style cues (clothing, film grain, color palette). No per-person reasoning — treats every photo as a standalone image classification task.

### "Photo Dating by Facial Age Aggregation" (Paplhám, Nov 2025, arXiv:2511.05464)
State-of-the-art approach. Key insight: if you know a person's identity and birth year, you can estimate the photo year as `birth_year + apparent_age`. Uses:
- Face detection (InsightFace/ArcFace for recognition)
- Age estimation model (NIST cvut-002, ViT-B/16)
- Probabilistic aggregation across multiple faces
- Career-based temporal priors

Multi-face aggregation consistently improves accuracy — more identified faces = tighter confidence interval.

### Date Estimation in the Wild (DEW dataset, 2017)
1M+ Flickr images 1930-1999. Scene-based CNN baselines. Shown that deep models beat untrained humans at dating photos.

## Rhodesli's Unique Advantage

Rhodesli already has the key ingredients:
- InsightFace face detection + 512-dim PFE embeddings (installed)
- Identity database with 46 confirmed people
- GEDCOM data with birth/death years for some identities
- Gemini integration for visual analysis (270+ photos labeled)
- Historical photo collection spanning 1900s-1990s

No other heritage archive combines all of these. The approach:

**For identified faces with known birth year:**
```
photo_year = birth_year + apparent_age
confidence = f(age_estimation_uncertainty, birth_year_certainty)
```

**For identified faces WITHOUT birth year:**
Fall back to Gemini scene-based estimation.

**Multi-face aggregation:**
If photo has 3 identified people with known birth years, combine their estimates probabilistically. More faces = narrower confidence interval.

## V1 Architecture (Gemini-first, lightweight)

V1 uses Gemini for age estimation rather than a dedicated ML model. This gets a working feature without training infrastructure.

### Pipeline
1. User selects archive photo (or uploads new one)
2. Load existing face detections from embeddings
3. For each face: Gemini estimates apparent age from crop
4. For identified faces: look up birth year from identities/GEDCOM
5. Calculate: `estimated_year = birth_year + apparent_age`
6. Aggregate across faces (weighted average by confidence)
7. Also ask Gemini for scene-based clues (clothing, setting, film type)
8. Present: "Estimated: c. 1935 (±5 years)" with per-person breakdown

### Existing Assets (no new ML needed)
- `rhodesli_ml/data/date_labels.json` — 270+ photos with Gemini labels including `subject_ages`
- `rhodesli_ml/data/birth_year_estimates.json` — 32 identities with ML birth year estimates
- `data/identities.json` — metadata with birth_year for some identities
- GEDCOM data with birth/death dates

### V2 (future)
Dedicated age estimation model (PyTorch ViT-B/16, fine-tuned on historical photos) replaces Gemini for step 3. Faster, cheaper, more consistent.
