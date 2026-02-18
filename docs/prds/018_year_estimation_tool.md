# PRD-018: Year Estimation Tool

**Status:** IN PROGRESS
**Priority:** HIGH
**Session:** 46
**Date:** 2026-02-18

## Problem Statement

Most archive photos have no date. Gemini's current scene-based estimates lack transparency ("c. 1950s" with no reasoning visible). Users want to know WHY a date was estimated and see the evidence chain.

## Solution

A tool that estimates when a photo was taken by combining:
1. Apparent ages of people in the photo (from existing Gemini labels)
2. Known birth years from the identity database / GEDCOM
3. Visual scene cues (clothing, setting, film type)

And shows its reasoning for each factor.

## User Experience

### On /photo/{id} pages (automatic)
- Date estimate badge: "c. 1935 ± 5 years"
- Expandable "How we estimated this" section showing per-person evidence
- Link to interactive estimation tool

### On /estimate page (interactive tool)
- Select photo from archive (or upload)
- See face detection + age estimation per face
- Per-person breakdown: "Big Leon (born ~1890) appears ~45 → c. 1935"
- Scene analysis clues
- Combined estimate with confidence
- "The more people you identify, the better the estimate"
- Share results

## Technical Implementation (V1)

### Data Sources (all existing)
- `rhodesli_ml/data/date_labels.json` — Gemini labels with `subject_ages` per photo
- `rhodesli_ml/data/birth_year_estimates.json` — ML birth year estimates
- `data/identities.json` — metadata with birth_year, GEDCOM enrichment

### Estimation Pipeline
```python
def estimate_photo_year(photo_id: str) -> dict:
    # 1. Load face data for this photo
    # 2. For each face with known identity + birth year:
    #    estimated_year = birth_year + apparent_age
    # 3. Aggregate across faces (weighted by confidence)
    # 4. Include scene evidence from Gemini labels
    # 5. Return combined estimate with reasoning
```

### Data Model
Add `date_estimate` to photo display (computed, not stored):
```json
{
  "year": 1935,
  "confidence": "high",
  "margin": 5,
  "method": "facial_age_aggregation",
  "face_evidence": [
    {
      "face_id": "...",
      "identity_id": "...",
      "person_name": "Big Leon Capeluto",
      "birth_year": 1890,
      "apparent_age": 45,
      "estimated_year": 1935
    }
  ],
  "scene_evidence": {
    "clues": ["B&W photography", "formal attire"],
    "scene_estimate": "1930s-1940s"
  }
}
```

### Graceful Degradation
- No identified faces with birth years → scene-only estimate from Gemini labels
- No Gemini labels → return None (no estimate)
- Missing data → skip that face, use remaining evidence

## Acceptance Criteria

1. /estimate page loads and shows archive photo selector
2. Selecting a photo shows face-by-face age evidence
3. Identified faces with birth years show year calculation
4. Scene evidence from Gemini labels displayed
5. Combined estimate shown with confidence level
6. Reasoning display is prominent (not hidden in collapsed section)
7. Share button produces working link
8. Graceful degradation when data is missing

## Out of Scope (V1)
- Real-time Gemini API calls (V1 uses pre-computed labels only)
- Photo upload + live face detection (production lacks InsightFace)
- Dedicated age estimation ML model (V2)
- User date corrections from this tool (use existing correction flow)

## Priority Order
1. Estimation engine (core/year_estimation.py)
2. /estimate page with archive selector
3. Per-face reasoning display
4. Scene evidence display
5. Share button + OG tags
6. Integration as Compare tab
