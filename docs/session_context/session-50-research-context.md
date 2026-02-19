# Session 50 Context: Research + Feedback

Save this file to: docs/session_context/session_50_research_context.md

## Community Sharing Results (Session 49C)

Rhodesli shared on Jews of Rhodes Facebook group (~2,000 members).
First public test of sharing + identification flows.

### Engagement (22 hours)
- 17 comments, 108 post reach
- 3 family members actively identifying people:
  - Howie Franco: identified his father Isaac Franco + uncle Morris Franco
  - Carey Franco: identified 8 people in ONE comment (Albert + Eleanore 
    Cohen, Morris + Ray Franco, Molly + Herman Benson, Belle + Isaac Franco)
  - Stu Nadel: confirmed face match ("Looks the same to me..!!")
- Howie initially confused Vida Capeluto for his grandmother, then 
  self-corrected — this triggered the Compare tool use attempt

### Bugs Found During Live Use
1. P0 FIXED: Photo 404 for community/inbox photos (alias map)
2. P0 FIXED: Compare upload silent failure (onchange handler)
3. P1 FIXED: Version v0.0.0 in admin (Dockerfile COPY)
4. P1 FIXED: Collection name truncation (6 locations)
5. P1 REMAINING: Compare upload has no error handling/feedback

### Product Insights
- "Are these the same person?" sharing page works great
- Face match links generated most engagement
- Community members want to identify ALL faces, not just one
- Carey Franco's 8-name comment = proof that batch identity entry 
  is the #1 UX gap
- The sharing → comment → identification loop works but is friction-heavy

## Estimate Page Issues (Screenshots Feb 19, 2026)

### Problems Observed
1. Every photo shows "0 faces" (not reading from data)
2. Page loads all 271 photos — very slow
3. No upload capability (core missing feature)
4. "No detailed evidence available" for most photos
5. Only accessible via Compare tab (no standalone nav)
6. No date correction mechanism
7. No search or filter
8. No CTAs deeper into the app

### What Works
- Photo selection shows estimate with year + confidence range
- "Share Estimate" and "View Photo" buttons present
- "Try Another Photo" grid renders (but slow, wrong face counts)

## Gemini 3.1 Pro (Released Feb 19, 2026)

### Key Facts
- Model: gemini-3.1-pro-preview
- ARC-AGI-2: 77.1% (vs 31.1% for 3 Pro — 2x improvement)
- Pricing: $2.00/$12.00 per 1M tokens (same as 3 Pro)
- Context: 1M tokens
- Vision: improved bounding box, media_resolution parameter
- Available via: Google AI Studio, Vertex AI, Gemini API
- Status: preview (GA expected soon)

### Decision: Use 3.1 Pro for All Vision Work
Rationale: The evidence quality IS the product. When Gemini 
identifies "Marcel wave hairstyle typical of 1920s Rhodes studios" 
that's what makes people share the tool. Don't compromise on 
model quality for the wow factor features.

Cost for full library (271 photos): ~$7.60
Cost for PRD-015 face alignment: ~$7.60
Total: ~$15.20 for complete re-analysis

## Progressive Refinement Architecture

### Core Idea (from Nolan)
Every time a verified fact is confirmed (identity, date, location, 
GEDCOM data), re-run the Gemini analysis with the new context.
Compare before/after results. Log everything for analysis.

### Research: Region-Specific Dating
Nolan's example: A postcard from Rhodes. When Gemini learned it 
was from Rhodes, it gave a more accurate date based on 
region-specific hairstyles. This is a form of:
- **Context-enriched VLM analysis** — providing domain knowledge 
  alongside the image
- **Geographic cultural calibration** — different regions have 
  different fashion timelines
- Closest academic parallel: DeepMind's Ithaca system for 
  dating ancient inscriptions using geographic + temporal context

### Research: Iterative Refinement with Verified Facts
Pattern matches "SELF-REFINE" (Madaan et al. 2023) but with 
EXTERNAL verified facts rather than self-generated feedback:
- SELF-REFINE: generate → self-critique → refine
- Our approach: generate → community verifies facts → re-analyze 
  with verified context → compare → admin approves
The human-in-the-loop component and domain-specific genealogical 
knowledge make this a novel application.

### Combined API Call
Date + faces + location should be ONE Gemini call:
- More cost-efficient (one API call, not three)
- Better results (model cross-references evidence)
- Example: "Military uniforms suggest WWII, 'WELCOME HOME' 
  banner confirms post-war, menorah symbol confirms Jewish 
  community" — coherent multi-signal analysis

### API Result Logging
ALL Gemini calls must be logged with:
- Full prompt and response
- Model version
- Input context (verified facts)
- Cost (input/output tokens)
- Comparison to previous estimate (if re-analysis)
Purpose: build analytical dataset to understand which facts 
improve estimates most, compare model versions systematically.

## Compare/Estimate Upload → ML Pipeline Flow

When user uploads a photo:
1. Immediate: PyTorch CORAL (local) → decade estimate
2. Immediate: InsightFace → face detection + embeddings
3. Background: compare embeddings to archive → match proposals
4. Background: Gemini enriched analysis (if API key)
5. If match found: proposal appears in admin New Matches queue
6. Admin accepts/rejects (existing Gatekeeper workflow)

Key: match discovery uses EXISTING infrastructure (New Matches, 
proposals, Gatekeeper). No new architecture needed — just 
trigger the match search on upload.

## Gemini Face Coordinate Work (PRD-015) Status

- PRD-015 written: Session 41
- AD-090 written: Session 41
- Implementation: NOT STARTED
- Recommended model: gemini-3.1-pro-preview
- Approach B: feed InsightFace coordinates TO Gemini
- Combined with date + location in single API call
- Scheduled: Session 53 (after Gemini API integration in 52)

## Harness: Phase Isolation Pattern

From Session 48 research, the "Prompt Decomposition with Phase 
Isolation and Verification Gate" pattern:
1. Save prompt to file
2. Parse into phases with checklist
3. Execute one phase at a time
4. Commit after each phase
5. /compact if context > 60%
6. Re-read original prompt at end
7. Verify EVERY phase against checklist
8. Fix any failures before declaring done

This prevents the context degradation that caused Session 47 
to claim phantom features and Session 49C to produce a shallow 
compare upload fix.
