# Robert Mattatia — Gemini Deep Comparison Analysis (Session 104)

**Date:** 2026-03-15
**Requested by:** Nolan (on behalf of Claude Benatar)
**Models used:** Gemini 2.5 Pro, Gemini 3.1 Pro Preview
**API calls logged:** Yes (Supabase gemini_api_calls, batch_id=claude-benatar-104)

## Summary

| Model | Confidence | Key Finding |
|-------|-----------|-------------|
| InsightFace ML | Cannot match (1.2727 > 1.10 threshold) | Above threshold |
| Gemini 2.5 Pro | **9/10** | Strong bone structure match, age progression consistent |
| Gemini 3.1 Pro | **8.5/10** | False negative from ML — periocular region obscured in both photos |

**Both Gemini models agree**: These are very likely the same person. The ML system's failure is a **false negative** caused by:
1. Pith helmet obscuring forehead/eyes in Congo photo
2. Dark glasses obscuring eyes/brow in family photo
3. Low resolution (557x399 family photo)
4. Different lighting conditions (harsh colonial sun vs. softer outdoor light)

## Key Gemini Observations

### Facial Features (both models agree)
- Long, rectangular face shape (dolichocephalic) — consistent
- Strong, squared jawline with prominent chin — consistent
- Prominent straight nose with medium bridge — consistent
- Thin lips with flat resting expression — consistent
- High, prominent cheekbones — consistent
- Overall facial proportions and geometry — consistent

### Age Progression
- Congo photo: Late 20s to early 40s → dates to mid-1940s to early 1950s
- Family photo: Late 40s to early 50s → dates to late 1950s to early 1960s
- 10-15 year gap is consistent with Robert Mattatia (born 1914, murdered 1967)

### Additional Insights
- Robert was notably tall — stands out physically in both photos
- Woman in family photo may be Rebecca Cohen (his wife, 1918-2010)
- Family photo likely taken 1958-1964, meaning final years before 1967 murder
- Congo photo shows European in supervisory role — consistent with colonial era work

## ML vs Gemini: Why the Disagreement?

The ML system relies on mathematical distance between face embedding vectors. It needs clear visibility of key facial landmarks, especially the periocular region (eyes, brow ridge, inter-pupillary distance). In these photos:
- **Photo 1**: Pith helmet + harsh shadows = no eye data
- **Photo 2**: Dark glasses = no eye data

Gemini can reason about: lower-face geometry, bone structure, age progression, historical context, clothing era, physical build, and setting — none of which ML embeddings capture.

## Potential Feature: Deep Comparison Workflow

**Nolan's idea**: Let users request a "deep comparison" where they provide photos + all known context, and Gemini provides a forensic-style analysis combining ML scores with contextual reasoning.

### Proposed Workflow
1. User uploads two photos via Compare tool
2. ML runs face detection + embedding comparison (current)
3. User optionally clicks "Deep Analysis" button
4. User types everything they know (names, dates, locations, relationships)
5. Gemini receives: both photos, face crops, ML distance, user context
6. Returns: forensic analysis with confidence score + reasoning
7. Result is shareable via link

### Why This Is Valuable
- ML alone cannot handle: occlusion, age gaps, low resolution, context
- Family members have critical context (names, dates, locations)
- Gemini can integrate visual + textual evidence in ways ML cannot
- Creates a premium, differentiated feature for heritage archives

### Cost Estimate
- Gemini 2.5 Pro: ~5,463 tokens ($0.003 at current pricing)
- Gemini 3.1 Pro: ~7,874 tokens ($0.005 at current pricing)
- Per comparison: <$0.01 — negligible cost

## API Call Details

### Call 1: Gemini 2.5 Pro
- Tokens: 1,467 prompt + 1,631 completion = 5,463 total
- Latency: 39.1 seconds
- Config: temperature=0.3, max_output_tokens=4000

### Call 2: Gemini 3.1 Pro Preview
- Tokens: 4,739 prompt + 1,257 completion = 7,874 total
- Latency: 35.8 seconds
- Config: temperature=0.3, max_output_tokens=4000

## Breadcrumbs
- BACKLOG: TOOLS-007 (Deep Comparison feature)
- BACKLOG: OBS-002 (Contributor action logging gaps)
- AD-225 (Compare community scoping — this session)
- Session 104 analysis: docs/user_feedback/robert_mattatia_analysis_104.md
