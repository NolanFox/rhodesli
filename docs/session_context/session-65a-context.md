# Session 65a Context: Upload Fix, Compare Overhaul, Prompt Fidelity, UX Polish

## Source
- **Date:** 2026-02-23
- **Origin:** Nolan walkthrough of production app + Session 64c/64d review conversation
- **Previous sessions:** 64c (GEDCOM enrichment pipeline), 64d (batch Gemini alignment — 269/271 photos aligned)
- **App version:** v0.65.0 (per screenshot footer: "55 of 660 identified")
- **Production URL:** https://rhodesli.nolanandrewfox.com

---

## PART 1: CRITICAL — UPLOAD IS BROKEN

### What Nolan Observed
Upload page freezes at "Processing 0/1 (0%): morris_mazal_ancestry_murry_army.jpeg" and never progresses. The progress bar stays at 0%. This is the single biggest blocker — new photos cannot be added to the system.

### Screenshot Evidence
The upload page shows:
- Collection: "Family Tree", Source: "Ancestry", Source URL filled in
- File dropped: morris_mazal_ancestry_murry_army.jpeg
- Progress bar stuck at "Processing 0/1 (0%)"
- Upload area still shows "Drop photos here or click to upload"

### Likely Failure Modes to Investigate
1. **Server-side timeout:** The upload handler may be trying to run InsightFace face detection synchronously during upload, causing a timeout on Railway before processing completes.
2. **R2 upload failure:** Cloudflare R2 credentials or bucket configuration may have changed or expired.
3. **Frontend SSE/polling disconnect:** The progress bar relies on either SSE or polling. If the connection drops, the UI freezes even if the server is still processing.
4. **Memory/resource limit on Railway:** InsightFace models are large. If the container is hitting memory limits during face detection, it could OOM silently.
5. **Missing error handling:** The upload may be throwing an exception that isn't surfaced to the UI — the user just sees a frozen progress bar.

### Fix Requirements
- Upload must complete successfully for single photos (JPG/PNG)
- Upload must handle errors gracefully — show error message, don't freeze
- Progress bar must update or show meaningful status
- After upload completes: photo should appear in library, faces should be detected
- Test with the actual file name from screenshot if possible, or any JPEG

---

## PART 2: HIGH — COMPARE FACE NEEDS TWO-PHOTO COMPARISON

### What Nolan Observed
Compare page doesn't allow comparison between two uploaded pictures. This is a core use case: "I have two pictures and I want to see if one person in each photo is the same person." Currently it doesn't match the FamilySearch Compare-a-Face feature quality.

### FamilySearch Reference (what to beat)
FamilySearch's Compare-a-Face lets users:
1. Upload two photos
2. Select a face in each
3. Get a similarity score
4. See the comparison visually side-by-side

### Required UX Flow
1. User uploads (or selects from library) Photo A
2. User uploads (or selects from library) Photo B
3. Faces are detected in both photos
4. User clicks a face in Photo A, then a face in Photo B
5. System computes cosine similarity between the two face embeddings
6. Display: side-by-side face crops, similarity score, confidence level
7. Optional: show other faces in both photos for additional comparisons

### Current State
The Compare page exists at /compare but doesn't support the two-photo workflow. The Estimate page is described as "getting better" but "may not actually work."

---

## PART 3: HIGH — PROMPT FIDELITY INVESTIGATION

### Problem
Session 64d cost was 5x cheaper than estimated ($0.0077 vs $0.037/photo). While this could be efficiency, it could also mean prompts aren't including the full GEDCOM context and InsightFace coordinates as designed. Past sessions have had issues where Claude Code silently simplified prompts.

### Investigation Steps (from planning notes)
1. Pull 3 actual API call records from `gemini_api_calls` — one GEDCOM-enriched, two not
2. For GEDCOM-enriched: reconstruct what prompt was actually sent to Gemini. Does it include full family context (names, birth years, relationships, residence)? Or stripped-down?
3. For non-enriched: does the prompt include InsightFace coordinates (bounding boxes, landmarks, embedding metadata)? Or just the image?
4. Compare token counts: GEDCOM-enriched should be noticeably higher than non-enriched. If similar → GEDCOM context isn't actually being included.
5. Verify model: `SELECT DISTINCT model_used FROM gemini_api_calls WHERE batch_id LIKE 'session-64d%';` — should be ONLY gemini-3.1-pro-preview.

### Why This Matters
If prompts are simplified, the 99.3% alignment coverage is misleading — we'd have 269 low-quality alignments instead of 127 high-quality ones. The combined pipeline was designed to send rich context (coordinates + GEDCOM + photo metadata) in a single call.

---

## PART 4: MEDIUM — WALKTHROUGH UX ISSUES

### Face Overlay Toggle
"You should be able to turn on and off the face overlay. It makes it hard for people to see when they look closer." Need a toggle button on photo view pages to show/hide face bounding boxes.

### Search on Browse Pages
"You can't search on the photos, collections, and people pages." The sidebar has a "Search names..." input but the browse pages themselves lack search/filter functionality.

### Share Links for Unidentified People
"There is no way to share an unidentified person other than manually typing their id in the url." Need a share button or copy-link action on person cards/pages.

### Page Navigation
"The connections between all these pages is haphazard and inconsistent. It makes navigating through the site tough and never very direct." Cross-linking between photo → person → collection → map needs consistency.

### Map Location Accuracy
"The picture from Asheville of Victoria Capuano Capeluto with 3 of her 4 children is shown in BK." Location data from GEDCOM or Gemini is mapping incorrectly — Asheville photo showing in Brooklyn.

---

## PART 5: QUICK WINS FROM PLANNING NOTES

### Pre-commit Hook Regex Fix
Hook regex `^git commit` misses chained commands like `cd repo && git commit`. Fix to `\bgit commit\b` in `.claude/settings.json`.

### AD Update: Batch API Findings
AD-157 says "Use Batch API for bulk photo processing (50% discount)." Reality from 64d: Batch API was extremely slow (>20 min for 1 request). Sync pipeline completed 136 photos in 20 min. Update AD-157 with actual findings.

### Verify 64d Results in Production
- Both Supabase tables still have data (269 alignments, 156 API calls)
- Production photo pages show face descriptions for newly aligned photos
- No duplicate alignment entries from batch + sync overlap
- The 2 failing photos (Image 914, Image 018) don't cause errors

---

## PART 6: GEDCOM ↔ IDENTITY LINKING UX (for Phase 4 if time allows)

### Problem
When an admin identifies a face, there's no UI to link that person to their GEDCOM record. Currently requires direct database inserts.

### Proposed UX Flow
1. Admin identifies a face (names a person)
2. App searches GEDCOM database by name, shows matches with: full name, birth/death year, family relationships, Ancestry ID
3. Admin clicks to link (or "No match — create new person")
4. Link saved to `gedcom_face_links` table
5. GEDCOM context now automatically enriches that face's data

### Extension of FE-041 (Help Identify)
- Non-admin suggests identification → Gatekeeper queue
- Admin confirms → links to GEDCOM record
- GEDCOM link step is admin-only part of the flow

---

## PART 7: ARCHITECTURE REMINDERS

### Stack
- Frontend: FastHTML (Python, server-rendered)
- Backend: FastHTML + Starlette
- ML: InsightFace (face detection/embeddings), PyTorch (CORAL date estimation)
- Database: Supabase (user data, identities) + JSON files (ML-generated data)
- Storage: Cloudflare R2
- Hosting: Railway
- Auth: Supabase auth

### Gatekeeper Pattern
ML outputs are staged as proposals. Admin accepts/rejects/corrects before going public. Confirmed data feeds back as ML ground truth anchors.

### Deployment
Deploy via git push (not Railway dashboard). Test uploads with curl/Playwright. Run smoke test after deploys.

### Context Management
Use /clear (not /compact) between phases. /compact is lossy. /clear + re-read from disk is correct pattern.

---

## PART 8: SESSION PRIORITY ORDER

1. **CRITICAL:** Fix uploads (blocks all new data entry)
2. **HIGH:** Compare face two-photo workflow (key portfolio feature + user need)
3. **HIGH:** Prompt fidelity investigation (validates 64d data quality)
4. **MEDIUM:** UX quick wins (face overlay toggle, share links)
5. **MEDIUM:** GEDCOM ↔ Identity linking UX
6. **HOUSEKEEPING:** Docs sync, AD updates, pre-commit hook fix
