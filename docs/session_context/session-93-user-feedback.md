# Session 93 User Feedback: GEDCOM Reanalysis Analysis Requirements

## Analysis Requirements (from Nolan)
1. **In-depth comparison**: Old vs new Gemini results (pre/post GEDCOM enrichment)
2. **What changed**: Did date estimates shift? Did location estimates improve? Did confidence change?
3. **Model tracking**: Note which model was used (gemini-3.1-pro-preview)
4. **Cost and performance**: Track cost per photo, total batch cost, API call timing
5. **Value-add analysis**: When does GEDCOM enrichment actually improve results vs not?

## GEDCOM Enrichment Context
- The GEDCOM file is Nolan's family tree
- Enrichment is **irregular** - deeper for closer relatives, sparser for distant branches
- Some people have extensive records (census, city directories), others minimal
- Practical implication: GEDCOM enrichment value varies by how well-linked the person is

## Future Directions
- **Multiple GEDCOMs**: Allow community members to upload their own GEDCOM files
  - Need to handle merging/deduplication across GEDCOMs
  - Each community member's research adds unique enrichment
- **Local/bespoke models**: Eventually may fine-tune or train our own ML models
  - Second-tier ML work, needs larger corpus first
  - Could reduce API costs significantly
- **Value tracking over time**: As models improve and data grows, track ROI of API calls
  - Eventually need to decide what's worth including in an API call vs not
  - Currently permissive (costs minor), but need framework for future decisions

## Database Schema Requirements
- Verify we're recording everything needed for longitudinal analysis:
  - Old vs new results per photo
  - GEDCOM context used per call
  - Model version per call
  - Cost per call
  - Confidence changes over time

## Breadcrumb Requirements
- Analysis should be in `docs/ml/GEDCOM_REANALYSIS_REPORT.md`
- Link from ALGORITHMIC_DECISIONS.md (new AD entry)
- Link from session assessment
- Link from BACKLOG for future multi-GEDCOM work
