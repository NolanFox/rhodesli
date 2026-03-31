# PRD-059: Temporal Co-Occurrence Analysis

**Status:** Phases 1-3 COMPLETE, Phase 4 SPECIFIED
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

### Phase 4: Identity Inference Engine

Multi-signal scoring function that fuses all available evidence into a continuous confidence score per candidate identity. NOT a binary classifier — produces a ranked list of hypotheses with explainable evidence breakdown.

**Signal 1: Family Cluster Score (AD-235)**
- Average L2 embedding distance from unknown face centroid to all confirmed members of target family
- Mean aggregation (0.892 balanced accuracy, beats median/min)
- Threshold: 1.34–1.35 for Fox family (86% recall, 90% precision)
- Per-family calibrated — not a global constant
- Validated: Person 82863536 scores 0.95 to Rachel (same as Albert), Person 3481 scores 1.43 (no Fox signal)

**Signal 2: Co-Occurrence Frequency (Phase 3 data)**
- How often does this unidentified person appear with confirmed family members?
- Drawn from the 391 co-occurrence pairs computed in Phase 3
- Normalized: co-occurrence count / total photos of confirmed person
- High co-occurrence with Esther + Albert = likely close family

**Signal 3: Age Trajectory Consistency**
- For each candidate identity, compute expected age at each photo date from GEDCOM birth year
- Compare against Gemini-estimated subject ages across dated photos
- Score = inverse of mean absolute deviation between expected and estimated ages
- Eliminates impossible candidates (e.g., Bessie b.1877 cannot be age 98 in 1975 color photo)

**Signal 4: GEDCOM Relationship Matching**
- Expected relationships from family tree: siblings, children, spouses, in-laws
- Cross-reference: if unknown person appears with Esther and Albert in 1920s photos, GEDCOM siblings of that era are candidates
- 1894 Minsk revision list provides definitive birth orders for Fox siblings
- Score: 1.0 for matching generation/era, 0.5 for adjacent generation, 0.0 for impossible

**Signal 5: Human Testimony**
- Input from descendants (Howard Newman, Erik Josowitz, etc.)
- Weighted highest — human identification overrides ML signals
- Stored as structured evidence: source person, relationship to subject, confidence, date
- Example: Howard Newman "almost certain NOT my grandmother" → strong negative for Rachel hypothesis on Person 3481

**Signal 6: Source Provenance**
- Who labeled the photo and their relationship to subjects
- First-party labels (family member) > community labels > ML proposals
- Fox cousin labeled Person 82863536 as "Ervin Fox's sister Sadie" — wrong name but confirms Fox family membership

**Scoring Approach**
- Weighted sum of normalized signals (0.0–1.0 each)
- Default weights: testimony (0.30), family_cluster (0.25), age_trajectory (0.20), co_occurrence (0.10), gedcom_match (0.10), provenance (0.05)
- Weights adjustable per investigation — testimony absent in most cases, redistributed to other signals
- Output: confidence score 0.0–1.0 per candidate identity, with per-signal breakdown

**Evidence Dossier**
- For each unidentified person: structured JSON document with all signals, raw scores, weighted scores, and recommended identity
- Stored in Supabase `identity_suggestions` table
- Batch-computed by script, recomputed on identity mutations or new evidence

**Admin UI: "Identity Suggestion" Panel**
- Displayed on person page for unidentified persons with sufficient evidence
- Shows: top 3 candidate identities, confidence score, per-signal breakdown
- Each signal rendered as a progress bar with tooltip explanation
- Accept button: promotes to CONFIRMED with full evidence audit trail
- Reject button: records rejection reason, prevents re-suggestion
- "Need More Evidence" button: flags for follow-up investigation

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
- Phase 1: All Esther + Albert photos have Gemini date estimates with subject ages — DONE (337/337)
- Phase 2: At least 3 "event groups" identified for Esther's early life photos — DONE (17 event groups)
- Phase 3: Co-occurrence matrix with meaningful pairs — DONE (391 pairs, 102 identities)
- Phase 4: Identity inference produces correct top-1 suggestion for at least 2 of the 6 unidentified Fox persons (3299, 82863528, 82863536, 4044, 3481, 3378), validated by leave-one-out against confirmed identities

## Related
- AD-229: Local ML removal deferred — embedding comparison still needed
- AD-235: Family Cluster Score — aggregate kinship signal (Session 145)
- CLUSTER-QUALITY-001: Harry/Albert Fox sibling resemblance
- PRD-038: Longitudinal Face Modeling (related but different approach)
- Session 142: Batch Gemini estimation + interactive feedback fixes
- Session 144b: Event grouping + co-occurrence matrix (Phases 2-3)
- Session 145: Family research intake + identity inference design
- SDD: `docs/prds/059_phase4_sdd.md` — Implementation specification
