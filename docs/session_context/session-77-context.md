# Session 77 Context — Compare Feature Rebuild (Codex)

## Purpose

This is the first Codex eval session on Rhodesli. Codex is being tested on a
real, high-value task: rebuilding the Compare feature, which is currently broken.
This session also evaluates Codex's strengths relative to Claude Code (our primary
tool) and Antigravity/Gemini (which we tested in Session 74).

## Why Compare Is Broken

The compare feature has been attempted across multiple sessions (32, 57, 59, and
partial work in others). Despite this, the following remain broken:

1. **Upload is completely broken.** Users cannot successfully upload photos for
   comparison. The upload flow silently fails or gets stuck at 0%. This has been
   attempted at least 5 times across sessions.
2. **Two-photo comparison doesn't work.** The pair upload at `/compare/pair` does
   not complete successfully.
3. **UX doesn't match market expectations.** Compared to similar tools (MyHeritage,
   FamilySearch, Betaface), the current design is confusing and poorly organized.
4. **Photos uploaded for comparison are not saved.** The original vision was that
   uploads would enter an admin queue for potential archive inclusion. This pipeline
   is broken.
5. **No Gemini enrichment on uploads.** Uploaded photos should get Gemini analysis
   displayed as a "photo detective" experience showing evidence categories.
6. **No progressive feedback.** Users see no indication that processing is happening
   during the 5-10 second face detection/comparison cycle.

## The Vision for Compare

Compare should serve three audiences:

1. **Rhodesli community members** who have family photos and want to find matches
   in the archive. Bridge CTA: "Explore the full archive →"
2. **General users** who find Compare via search/social and want to compare faces
   across historical photos. This is the standalone product use case.
3. **Contributors** who upload photos that could enrich the archive. Every upload
   should be saved and queued for admin review.

### Multi-Photo Compare (the full vision)

- Upload 2+ photos → compare THEM against each other AND against archive
- Multi-face detection in each photo → cross-match all faces
- Every uploaded photo gets saved for archive processing
- Date estimation runs on every upload automatically
- Gemini evidence displayed for each photo — "photo detective" UX

### Upload → Pipeline Flow (must be verified and fixed)

1. User uploads photo(s) → saved to R2 `uploads/compare/`
2. InsightFace → face detection + embeddings (immediate)
3. CORAL ONNX → decade estimate (immediate, if available)
4. Compare embeddings to archive → match proposals (immediate)
5. Gemini → evidence-based analysis (background, if API key available)
6. Results displayed progressively via SSE or HTMX polling
7. All photos enter admin queue for archive consideration
8. Approved photos join next batch processing run

## Competitive Landscape Research

### MyHeritage Deep Nostalgia / Photo Enhancer
- Clean upload UX, single drag-drop zone
- Results show side-by-side comparison
- Upsells to premium features after showing results
- Weakness: no multi-photo compare, no evidence display

### FamilySearch Compare-a-Face
- Simple upload → compare against historical collection
- Shows confidence percentage
- Good at scale but generic — no per-photo analysis
- Weakness: no explanation of WHY faces match

### Betaface
- Technical demo feel, not consumer-grade
- Shows facial landmarks and measurements
- Useful reference for what metadata to surface
- Weakness: terrible UX, feels like a developer tool

### What Rhodesli Can Do Better
- **Evidence-based results**: Show WHY a match was found (Gemini analysis)
- **Calibrated confidence**: Use Platt-scaled scores, not raw cosine similarity
- **Multi-photo cross-matching**: Compare uploaded photos against each other AND archive
- **Archive contribution pipeline**: Every upload is a potential archive addition
- **Historical context**: Date estimates, clothing analysis, location evidence

## Architecture Context

### Key Services (in `app/services/`)
- `CalibrationService` — Platt scaling for face similarity scores
- `DateEstimationService` — CORAL model for decade estimation
- `GeminiService` — Photo analysis via Gemini API
- Face detection/embedding via InsightFace (loaded on startup)

### Key Routes (in `app/main.py`)
- `/compare` — Main compare landing page
- `/compare/pair` — Two-photo comparison
- `/api/compare/upload` — Upload endpoint
- `/api/compare/upload-multiple` — Multi-upload endpoint

### Pre-computed Data
- 271 photos in archive with face detections
- 662 face embeddings stored in `data/face_index.json`
- 46 confirmed identities in `data/confirmed_identities.json`
- Confirmed birth years serve as ML ground truth anchors

### Confidence Tiers (from calibration work)
- 🟢 **Identity match** (>0.95 calibrated): Same person
- 🟡 **Family/strong resemblance** (0.75-0.95): Likely related
- 🟠 **Possible connection** (0.55-0.75): Worth investigating
- ⚪ **No significant match** (<0.55): Different people

## Gemini Enrichment Display Context

When Gemini analyzes a photo, it produces evidence across categories:
- **Clothing/Fashion**: Era indicators, style analysis
- **Architecture/Setting**: Location clues, era indicators
- **Text/Signage**: Any readable text in the photo
- **Faces/People**: Number of people, age estimates, expressions
- **Photo Quality**: Format indicators (daguerreotype, color film, etc.)

The UX should expose this as a "Photo Detective" experience — showing each
evidence category, the reasoning chain, and how verified facts improve estimates.
This is NOT just showing a year number. It's showing the detective work.

## Session 74 (Antigravity/Gemini) Lessons Learned

What Gemini excelled at: ambitious scope, UX thinking, creative ideas.
What Gemini failed at: tech stack hallucination (tried to add React to a
FastHTML project), key reordering that created 9K lines of noise, didn't
respect existing patterns. Session 75 spent significant time reverting.

**Lessons for Codex:**
- Read existing code patterns BEFORE proposing changes
- Verify the tech stack from actual code, not assumptions
- Small commits, not one giant rewrite
- Test after every change

## Harness Rules (from CLAUDE.md / project conventions)

These rules apply to ALL agents working on this repo:

1. Read CLAUDE.md, ROADMAP.md, ALGORITHMIC_DECISIONS.md before starting
2. Commit after every phase with descriptive messages
3. Run tests after every code change
4. Update ALGORITHMIC_DECISIONS.md for ML decisions
5. Never modify `data/` files
6. Use FastHTML + HTMX patterns (no React/Node)
7. Document everything — the repo must be self-documenting
8. If stuck, read more code first (`grep`/`rg` are your friends)

## Test Suite Context

- ~2100+ passing tests in `tests/`
- ~100+ ML tests in `rhodesli_ml/tests/`
- Tests use pytest-xdist for parallel execution
- Known issue: some tests are slow due to model loading
- Goal: identify and fix slow tests, add compare-specific golden tests

## What "Success" Means for This Session

1. User uploads photo at `/compare` → sees face matches IMMEDIATELY
2. User uploads two photos at `/compare/pair` → sees similarity score
3. Comparison results have shareable URLs that WORK
4. Confidence labels are calibrated (not misleading)
5. Uploaded photos are saved for potential contribution
6. Test suite has a "golden test" that catches upload chain breaks
7. Test suite runs faster than before
8. All harness files updated with full provenance
9. Every phase has its own commit
10. Fresh ideas from Codex's own research are incorporated
