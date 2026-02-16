# PRD: Birth Date Estimation

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Complete
**Session:** 34

---

## Problem Statement

We have 46 confirmed identities appearing across 271 photos. Each photo has an AI-estimated date (best_year_estimate from CORAL/Gemini) AND per-face age estimates (subject_ages from Gemini, ordered left-to-right). Currently, zero identities have birth_year metadata populated. Birth year inference unlocks:
- Accurate age overlays on the timeline ("Big Leon, age 32")
- Temporal consistency validation (flag impossible ages)
- Better date estimation (birth years constrain photo dates)
- GEDCOM cross-validation (Session 35)

## Data Audit Findings (Pre-Implementation)

| Data Source | Available | Coverage |
|-------------|-----------|----------|
| Gemini subject_ages per photo | Yes | 271/271 (100%) |
| Gemini best_year_estimate | Yes | 271/271 (100%), 80% high confidence |
| Face bounding boxes (x-coords) | Yes | 1061 faces |
| Confirmed identity-to-face mapping | Yes | 175 faces across 46 identities |
| face_to_photo mapping | Yes | 857 entries |
| Identity metadata.birth_year | No | 0/775 (system exists, never populated) |

**Key insight**: No new data collection needed. Gemini already provides subject_ages for every photo.

## Who This Is For

| Role | Value |
|------|-------|
| Family member | "How old was grandpa in this photo?" |
| Timeline viewer | Accurate age badges instead of "Age unknown" |
| ML pipeline | Bidirectional: birth years improve dates, dates improve birth years |

## Core Algorithm

### Step 1: Face-to-Age Matching

Gemini provides `subject_ages` as an integer list ordered left-to-right. Face bounding boxes have x-coordinates. For each photo:

1. Get all detected face bboxes, sort by x1 coordinate (left-to-right)
2. Get `subject_ages` from date labels
3. If `len(sorted_faces) == len(subject_ages)`: match by position index
4. If counts differ: mark as "ambiguous" (skip for birth estimation)
5. For single-person photos: matching is trivially unambiguous

### Step 2: Birth Year Computation

For each confirmed identity with 2+ photo appearances AND matched age data:

1. GATHER all (photo_year, estimated_age) pairs
2. COMPUTE implied_birth_year = photo_year - estimated_age for each
3. AGGREGATE via weighted average:
   - Weight by date confidence: high=1.0, medium=0.5, low=0.25
   - Weight single-person photos 2x (unambiguous matching)
4. COMPUTE standard deviation for confidence tier:
   - std < 3 years AND n >= 3: HIGH confidence
   - std < 5 years OR n == 2: MEDIUM confidence
   - Otherwise: LOW confidence
5. VALIDATE:
   - birth_year in range [1850, 2010]
   - Person 0-100 years old in every appearance
   - Flag outliers (> 2 std from mean)

### Step 3: Output

File: `rhodesli_ml/data/birth_year_estimates.json`

```json
{
  "schema_version": 1,
  "generated_at": "2026-02-15T...",
  "estimates": [
    {
      "identity_id": "b6d9ea5b-...",
      "name": "Big Leon Capeluto",
      "birth_year_estimate": 1903,
      "birth_year_confidence": "high",
      "birth_year_range": [1900, 1906],
      "birth_year_std": 1.76,
      "n_appearances": 25,
      "n_with_age_data": 10,
      "evidence": [
        {
          "photo_id": "ca69d9decc37b0ec",
          "photo_year": 1939,
          "date_confidence": "high",
          "estimated_age": 36,
          "implied_birth": 1903,
          "matching_method": "single_person",
          "weight": 2.0
        }
      ],
      "flags": [],
      "source": "ml_inferred"
    }
  ]
}
```

## UI Integration

### Timeline (/timeline?person=X)
- Load `birth_year_estimates.json` as fallback when `metadata.birth_year` is not set
- Show age on each timeline card: "Age ~32"
- Style by confidence: HIGH=normal, MEDIUM=italic with ~, LOW=faded

### Person Page (/person/{id})
- Show "Born ~1903" with confidence indicator
- Source label: "ML estimated" vs "confirmed" (when metadata.birth_year set)

### Priority: metadata.birth_year > ml_estimated birth_year
Human-confirmed birth years always override ML estimates.

## Acceptance Criteria

1. `rhodesli_ml/data/birth_year_estimates.json` exists and is valid JSON
2. Identities with 5+ appearances AND matched age data have estimates
3. Each estimate has HIGH/MEDIUM/LOW confidence
4. Each estimate has per-photo evidence array
5. No person has impossible ages (negative or >100) in any photo
6. Big Leon Capeluto has an estimate near 1903 (range 1900-1910)
7. /timeline?person=leon_id shows age overlay using estimated birth year
8. Known birth year validation: if any identity has metadata.birth_year, compare to ML estimate

## Actual Results (Session 34)

- **32 estimates** from 46 confirmed identities (14 skipped — no age data matched)
- **3 HIGH** confidence: Selma Capeluto (1917), Victoria Cukran Capeluto (1927), Betty Capeluto (1951)
- **6 MEDIUM** confidence: Big Leon (1907), Moise (1919), Victoria Capuano (1916), Rica Moussafer Pizante (1907), Leon (1972), Esther Diana (1903)
- **23 LOW** confidence: single-evidence-point identities
- **Big Leon validation**: 1907 estimated (expected ~1903). Single-person photos give 1903/1905 — group photo bbox noise pulls estimate up. Within 5 years.
- **Key limitation**: Vida Capeluto (15 photos) gets 0 estimates — all her photos have face count mismatches between InsightFace and Gemini
- **48 tests** (37 ML + 11 integration): all passing

## Deferred

- User correction flow for birth years (Session 35 with GEDCOM)
- Bidirectional date improvement (birth year constrains photo dates)
- InsightFace age estimation (not needed — Gemini already covers it)
- Age progression visualization
