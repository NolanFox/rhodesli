# PRD-059: Temporal Co-Occurrence Analysis

**Status:** DRAFT
**Author:** Session 142 (Claude + Nolan)
**Date:** 2026-03-27
**Priority:** P1 — enables sibling/family identification workflow

## Problem Statement

Esther Burd Fox and Albert Fox have 282 unique photos across the Fox Family Archive. Many photos show young Esther or Albert with unidentified people who are likely siblings or close family members. The same unidentified person appears in multiple photos at different ages, but we can't currently:

1. Group photos by approximate event/time period
2. Cross-reference unidentified faces across time-grouped photos
3. Use known family relationships (GEDCOM) to infer identities by elimination

## User Workflow (Nolan's Vision)

1. **Date all photos** — Run Gemini on all photos to get year estimates + subject ages
2. **Group by event** — Cluster photos by estimated date + shared faces (same beach trip, same photo shoot)
3. **Cross-reference faces** — For each unidentified person appearing with Esther/Albert, show all their appearances sorted by date
4. **Infer identity** — Use GEDCOM family tree + estimated ages + co-occurrence patterns to suggest who each unidentified person might be

### Example Scenario
- Photo A (1928): Young Esther (22) with unknown woman (18) at beach
- Photo B (1929): Young Esther (23) with same unknown woman (19) at family event
- Photo C (1935): Same unknown woman (25) now appears with Albert at a wedding
- GEDCOM says Esther had a sister born 1910 (4 years younger)
- **Inference**: Unknown woman is likely Esther's sister based on age gap + co-occurrence

## Key Challenge: Harry Fox / Albert Fox Problem

ML embeddings cannot distinguish siblings who look very similar (AD-229, CLUSTER-QUALITY-001). Albert and Harry Fox are indistinguishable by face embeddings alone. Temporal context + co-occurrence is the only reliable disambiguation:
- If a face appears with Esther in a 1920s photo and Albert married Esther in 1925, the young man is likely Albert
- If the same face appears in a 1945 military photo without Esther, it could be Harry

## Data Requirements

### Already Available
- [x] Face embeddings for all faces (InsightFace 512-dim)
- [x] Identity assignments (confirmed + proposed)
- [x] GEDCOM family tree with birth/death years, relationships
- [x] Photo-to-face and face-to-identity mappings

### Needed (Session 142 batch)
- [ ] Gemini date estimates for all Esther + Albert photos (279 photos, in progress)
- [ ] Subject age estimates per face per photo (included in "full" Gemini preset)

### Derived (to build)
- [ ] Event grouping: photos clustered by estimated_date ± 2 years AND shared faces
- [ ] Co-occurrence matrix: which unidentified faces appear together across events
- [ ] Age trajectory: estimated age of each unidentified person across photos, sorted by date

## Proposed Features

### Phase 1: Data Foundation (Session 142 — in progress)
- [x] Batch Gemini estimation script with full preset
- [x] Subject ages, face analysis, group composition for each photo
- [ ] Verify all 279 photos processed with complete results

### Phase 2: Event Grouping (Next Session)
- Group photos into "events" based on:
  - Estimated year within ±2 years
  - Shared faces (>= 2 faces in common = same event)
  - Similar setting/location from Gemini metadata
- Admin UI: `/c/{community}/person/{id}/timeline` showing photo groups by era
- Highlight which unidentified faces appear in multiple event groups

### Phase 3: Co-Occurrence Matrix (Future)
- For a given confirmed person (Esther), compute which unidentified faces appear most frequently alongside her
- Show "Frequent Companions" panel on person page
- Cross-reference with GEDCOM: if Esther's sister was born 1910, highlight unidentified faces whose estimated age matches (±3 years)

### Phase 4: Identity Inference (Future)
- Combine evidence signals:
  - Embedding distance to known family members
  - Age trajectory consistency across dated photos
  - Co-occurrence frequency with confirmed people
  - GEDCOM relationship data (expected siblings, children, etc.)
- Present "Identity Suggestion" with evidence breakdown
- Admin can accept/reject with one click

## Out of Scope
- Automatic identity assignment (always human-in-the-loop)
- Modifying face embeddings or ML pipeline
- Non-family co-occurrence (friends, colleagues)

## Technical Notes
- Event grouping should be computed from `date_labels.json` data (not real-time)
- Co-occurrence matrix can reuse existing `validate_merge()` co-occurrence logic
- GEDCOM queries already implemented in `_build_gedcom_context_for_photo()`
- Subject ages from Gemini are per-face estimates — need to align with face bounding boxes

## Success Criteria
- Phase 1: All Esther + Albert photos have Gemini date estimates with subject ages
- Phase 2: At least 3 "event groups" identified for Esther's early life photos
- Phase 3: At least 1 previously unidentified person correctly identified through co-occurrence + GEDCOM inference

## Related
- AD-229: Local ML removal deferred — embedding comparison still needed
- CLUSTER-QUALITY-001: Harry/Albert Fox sibling resemblance
- PRD-038: Longitudinal Face Modeling (related but different approach)
- Session 142: Batch Gemini estimation + interactive feedback fixes
