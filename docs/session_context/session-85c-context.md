# Session 85c Planning Context — Universal Comparison Workspace

**Date:** 2026-03-03
**Predecessor:** [Session 85b Context](session-85b-context.md)
**Prompt:** [Session 85c Prompt](../prompts/session-85c-prompt.md)
**Status:** Planning complete, ready for execution

## Origin: Nolan Feedback (2026-03-03)

Nolan reviewed the current Compare UX (v0.87.1, post-85b) and identified that the
feature is incomplete relative to the original vision. Key quotes:

> "I believe I explicitly said that we need to be able to compare any of the following:
> any given individual, existing picture, or newly uploaded picture with any other
> individual, existing picture, or newly uploaded picture."

> "If a picture is uploaded the faces should be processed like a normal upload and
> the photo should be saved."

> "You should be able to know how strong face similarity is relative to the top
> similar faces or each match or matches (if the picture has multiple photos)."

> "The UX should allow you to see both faces and photos and be able to smoothly
> toggle between them."

> "You should be able to search for a person or photo (include unidentified people)."

> "This UX should also allow you to hide matches if there are multiple ones in a
> photo, and also select multiple identities to compare against."

> "This should be easier to use, more elegant, better designed (currently it is NOT)
> and faster with more fluid animation and faster upload than something like
> FamilySearch compare a face."

### Nolan's Design Decisions (from Q&A):
- **Photo search**: Both text-based browse AND visual similarity search
- **Approach**: Full workspace redesign (not incremental), two-slot UI selected
- **Scope**: Complete vision, OK to split across 85c + 85d if needed
- **Visual similarity**: Confirmed as valuable — "Find visually similar people" auto-populates targets

## Gap Analysis (16 items)

### The 3x3 Entity Matrix

|  | vs Person | vs Photo | vs Upload |
|--|-----------|----------|-----------|
| **Person source** | PARTIAL (Find Similar) | NO | YES (vs-person) |
| **Photo source** | YES (from-photo) | NO | NO |
| **Upload source** | YES (vs-person) | NO | JANKY (/compare/pair) |

Only ~4/9 combinations work. The full matrix must be supported.

### All 16 Gaps

| # | Gap | Severity | Notes |
|---|-----|----------|-------|
| 1 | No Individual vs Individual direct compare | P1 | Find Similar gives ranking but no direct side-by-side |
| 2 | No Individual vs Existing Photo compare | P1 | |
| 3 | No Existing Photo vs Existing Photo compare | P1 | |
| 4 | No Existing Photo vs Uploaded Photo compare | P1 | |
| 5 | Uploaded vs Uploaded is separate janky page | P2 | /compare/pair exists but separate, clunky |
| 6 | No face/photo toggle | P1 | Only see crops, never full photo context |
| 7 | No multi-select targets | P1 | Single person only |
| 8 | No hide/collapse individual matches | P2 | All matches always visible |
| 9 | Search excludes INBOX/unidentified people | P2 | |
| 10 | No photo search at all | P2 | Only person search |
| 11 | No context per match card | P2 | How does score rank vs that person's best? |
| 12 | Design is sparse and unfocused | P1 | User: "currently it is NOT well designed" |
| 13 | No animations | P2 | No smooth transitions |
| 14 | Fragmented UX (3 separate pages) | P1 | /compare, /compare/pair, /facecompare |
| 15 | Upload progress has no visual polish | P3 | |
| 16 | No URL state | P3 | Can't bookmark a comparison setup |

## FamilySearch Competitive Analysis

### FamilySearch Compare-a-Face Summary
- **Flow**: Sign in → upload selfie → compare against tree portraits (up to 6 generations) → horizontal carousel of results ranked by %
- **Positioned as entertainment** ("which ancestor do I look like?"), not identification
- **Strengths**: Low barrier (free), auto-pulls tree portraits, engaging/shareable
- **Weaknesses**:
  - Accuracy unreliable with old photos, glasses, beards, age differences
  - Opaque percentages with no calibration or explanation
  - Session expiration bugs, slow platform
  - Only compares against YOUR tree (walled garden)
  - No community identification workflow
  - No sharing of results outside the session
  - Confusing privacy terms initially damaged trust

### Rhodesli's Competitive Advantages
| Dimension | FamilySearch | Rhodesli Target |
|-----------|-------------|-----------------|
| Purpose | Entertainment | Identification |
| Database | User's tree only (6 gen) | 662+ identified people |
| Accuracy | Opaque %, unreliable | Calibrated (AUC 0.9577) |
| Transparency | "Software from a renowned provider" | Per-face scores, confidence bars, context |
| Access | Account required | No account needed |
| Speed | Platform-wide slowness | HTMX instant results |
| Sharing | Trapped in session | Public shareable URLs with OG cards |
| Community | No identification workflow | Full growth loop: share → identify → confirm |
| Old photos | Struggles with quality | Purpose-built for historical archive photos |

Full competitive analysis in [docs/research/compare_faces_competitive.md](../research/compare_faces_competitive.md)

## Current Compare Architecture (Code Audit)

### Existing Routes (~2000 lines in app/main.py)
- `GET /compare` (line ~16302) — Main landing page
- `POST /api/compare/upload` (line ~17418) — Unified upload endpoint
- `GET /api/compare/status/{job_id}` (line ~17654) — Poll upload progress
- `GET /api/compare/from-photo` (line ~18144) — Archive photo vs person
- `POST /api/compare/vs-person` (line ~17792) — Upload vs specific person
- `GET /api/compare/search-person` (line ~17738) — Person search autocomplete
- `GET /api/compare/search-person-photo` (line ~18484) — Person search for photo flow
- `POST /api/compare/upload-multiple` (line ~18536) — Multi-photo upload (2-5)
- `GET /compare/pair` (line ~19682) — Two-photo comparison page
- `POST /api/compare/pair/upload` — Detect faces in one photo
- `POST /api/compare/pair/match` — Score two faces
- `GET /compare/result/{result_id}` (line ~19139) — Shareable result page
- `POST /api/compare/result/{id}/respond` (line ~19443) — Community response

### Key Helpers
- `_compare_result_card()` (line ~16649) — Single result card with tier styling
- `_compare_results_grid()` (line ~16929) — Groups results by tier
- `_build_compare_results_view()` (line ~17142) — Full results after upload
- `_resolve_crop_url()` (line ~17374) — Handle legacy + inbox crop formats
- `_generate_result_id()` (line ~19134) — 12-char UUID hex
- `_save_comparison_result()` (line ~19112) — Persist to comparison_results.json
- `SimilarityCalibrator` — Isotonic regression, cosine_sim → probability

### Confidence Tiers
- 85%+ = STRONG MATCH (green)
- 70-84% = POSSIBLE MATCH (amber)
- 50-69% = SIMILAR (blue)
- <50% = WEAK (gray)

### Auth: All compare routes are public (no auth required). Admin-only features:
merge/not-same buttons, raw distance display.

## Design Decision: Full Workspace Redesign

**Chosen**: Two-slot workspace (Source + Targets → Results matrix)
**Rejected**: Incremental improvement to existing upload-first flow
**Reason**: Current UX is fundamentally fragmented (3 pages). Adding multi-select
and toggle to existing flow would be bandaid on broken architecture. The workspace
model naturally supports all 9 entity combinations.

## Deferred Work for Future Sessions
- `/facecompare` changes (different audience, keep as-is)
- GPU inference on Railway (blocked by AD-007)
- ML model changes
- Feature-level similarity breakdown (eyes, nose, jawline)
- Visual clue tagging (Civil War Photo Sleuth pattern)

## Post-Session Planning

### If 85c completes fully:
- Verify all 14 browser checks pass
- Community testing with Claude Benatar use case
- Consider A/B testing old vs new compare page

### If 85c needs continuation (85d):
- Priority: finish animations + polish + edge cases
- Secondary: photo browse UI, visual similarity auto-population
- Tertiary: advanced context intelligence features
