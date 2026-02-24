# Session 65b Context: Production Verification, GEDCOM Linking, Enrichment Pipeline Fix

## Source
- **Date:** 2026-02-24
- **Origin:** Session 65a assessment + Nolan walkthrough notes + planning doc
- **Previous session:** 65a (upload fix, compare overhaul, prompt fidelity, UX wins)
- **App version:** v0.68.0
- **Production URL:** https://rhodesli.nolanandrewfox.com

---

## PART 1: 65a ISSUES REQUIRING PRODUCTION VERIFICATION

### 1A: Upload Fix — UNVERIFIED
Session 65a added subprocess PID tracking, death detection, and a 5-minute timeout to the upload pipeline. This means the progress bar no longer freezes forever — it now reports errors. **However, we do not know if uploads actually complete successfully.** The fix may have addressed the symptom (frozen UI) without fixing the root cause (why the subprocess dies).

**What 65b must do:**
1. Use browser automation (Chrome plugin preferred, Playwright fallback) to attempt a real upload on production
2. Use a small test image (NOT a real heritage photo — do not pollute production data)
3. If upload succeeds: verify the photo appears in the library and faces are detected
4. If upload fails: read the error message now surfaced by the 65a fix, diagnose the actual root cause, and fix it
5. After testing: DELETE any test photos uploaded during verification

**Test data safety rule:** Use a clearly-named test image like `_test_upload_65b_delete_me.jpg`. After verification, remove it from both the library and R2 storage. Do NOT leave test data in production.

### 1B: Compare Pair — UNVERIFIED
Session 65a built 3 new routes: /compare/pair, /api/compare/pair/upload, /api/compare/pair/match. 11 tests pass locally. **Zero production verification.**

**What 65b must do:**
1. Browser-verify /compare/pair loads in production
2. Verify the two-panel layout renders correctly
3. Verify face detection works on uploaded photos
4. Verify similarity scoring displays correctly
5. Check mobile layout (if possible)

### 1C: Face Overlay Toggle — BARELY TESTED
4 of 5 UX tests were skipped due to no real photo data in test environment. Only 1 test ran.

**What 65b must do:**
1. Browser-verify the toggle button appears on a real photo page
2. Verify clicking toggle hides/shows face bounding boxes
3. Verify default state: ON for admin, OFF for non-admin

### 1D: Share Links for People
Added in 65a but needs browser verification that the copy-link button actually works.

---

## PART 2: PROMPT FIDELITY — CRITICAL FINDING FROM 65a

### The Problem
Session 65a's investigation (documented in `docs/analysis/prompt_fidelity_64d.md` and AD-159) found:
- Only **17 of 136 API calls (12.5%)** received GEDCOM context
- Even enriched calls only got **~106 tokens** of GEDCOM context
- This means 88% of photos got bare prompts (just image + basic instructions)
- The remaining 12% got thin GEDCOM context (106 tokens ≈ 1-2 sentences of family info)

### What This Means
- The 269 "aligned" photos from Session 64d have lower quality than designed
- A full GEDCOM enrichment should include: person names, birth/death years, spouse names, parent names, sibling names, residence locations, Ancestry IDs — easily 500-1000+ tokens
- The combined pipeline's key value proposition (rich context → better alignment) wasn't delivered
- **This does NOT mean the alignments are worthless** — Gemini still described the photos, just without genealogical context to help identify people

### What 65b Should Do
- **Do NOT re-run the full pipeline this session** — that's expensive and should be planned separately
- DO investigate the enrichment code path: find where GEDCOM context is assembled and injected into prompts
- Fix the pipeline so future runs include full GEDCOM context
- Document the fix in AD-159 (update, don't create new)
- Add a verification step: log GEDCOM token count per call, flag calls with <200 tokens as "under-enriched"

### Additional Logging Gap
`gemini_config` and `response_summary` fields in the `gemini_api_calls` table are never populated. The `call_gemini_alignment()` function should save: prompt hash, key params, response summary. This makes future audits much easier.

---

## PART 3: GEDCOM ↔ IDENTITY LINKING UX (PRIMARY FEATURE — FE-041 Extension)

### Problem Statement
When an admin identifies a face (names a person), there is no UI to link that person to their GEDCOM record. Currently requires direct database inserts via Claude Code sessions. This doesn't scale.

### Example
Nolan added "Regina Reina Israel Capeluto" but has no way in the app to specify her Ancestry ID / GEDCOM xref so the app knows who she is in the family tree.

### Proposed UX Flow
1. Admin identifies a face (names a person) — existing flow
2. **NEW:** After naming, app shows a "Link to Family Tree" step
3. App searches GEDCOM database by name, shows top matches with:
   - Full name
   - Birth year / death year
   - Family relationships (spouse, parents)
   - Ancestry ID for disambiguation
4. Admin clicks to link (or "No match — skip for now")
5. Link saved to `gedcom_face_links` table (already exists in schema)
6. GEDCOM context now automatically enriches that person's data across the app

### Integration with Gatekeeper Pattern
- Non-admin user suggests identification → goes to Gatekeeper queue
- Admin reviews → confirms identity → THEN gets the "Link to Family Tree" step
- GEDCOM link is admin-only — non-admins never see this step

### Technical Notes
- GEDCOM data is already loaded via `_build_parsed_gedcom_from_supabase()`
- The `gedcom_face_links` table may already exist — check schema first
- Name matching should be fuzzy (Sephardic names have many spelling variants: Capeluto/Capuano/Capueto, Israel/Yisrael, etc.)
- Show enough disambiguation info that the admin can pick the right person from multiple matches
- If no matches: allow "skip" — not every person in photos has a GEDCOM record

### Data Safety
- GEDCOM linking is additive only — it adds a link, never deletes or modifies existing identity data
- Links should be reversible (admin can unlink if they made a mistake)
- Linking to GEDCOM should not change any existing face data, embeddings, or similarity scores

---

## PART 4: BROWSER TESTING INSTRUCTIONS

### Preferred: Claude Chrome Plugin
Use the Claude Chrome plugin for browser automation when available. This provides real browser rendering verification.

### Fallback: Playwright
If Chrome plugin is not available, use Playwright:
```bash
pip install playwright
playwright install chromium
```

### Critical Rules for Browser Testing
1. **DO NOT create, modify, or delete real production data** during testing
2. If you must upload a test photo: name it clearly (`_test_65b_delete_me.jpg`), verify, then DELETE it
3. Use read-only verification where possible (load pages, check elements exist, screenshot)
4. If testing requires auth: use Nolan's admin session (check for existing auth cookies or session tokens)
5. Save screenshots to `docs/screenshots/session-65b/` for review

### What to Verify (browser checklist)
- [ ] /upload page loads, file drop zone renders
- [ ] Upload a small test image → progress bar updates → photo appears in library
- [ ] /compare/pair loads with two-panel layout
- [ ] Photo page: face overlay toggle button visible and functional
- [ ] Person page: share/copy-link button visible
- [ ] Navigation: photo → person → back to photo works
- [ ] Delete test photo after verification

---

## PART 5: ARCHITECTURE REMINDERS

### Stack
- Frontend: FastHTML (Python, server-rendered)
- Backend: FastHTML + Starlette
- ML: InsightFace, PyTorch CORAL
- Database: Supabase + JSON files
- Storage: Cloudflare R2
- Hosting: Railway
- Auth: Supabase auth

### Gatekeeper Pattern
ML outputs = proposals. Admin accepts/rejects. Confirmed data = ground truth anchors for future ML.

### Deployment
`git push origin main` triggers Railway deploy. Smoke test after every deploy.

### Context Management
/clear between phases (NOT /compact). Re-read CLAUDE.md + context file after each /clear.

---

## PART 6: SESSION PRIORITY ORDER

1. **VERIFY:** 65a production verification (upload, compare, overlay, share links) — browser automation
2. **FIX IF BROKEN:** If upload still doesn't work, diagnose and fix the actual root cause
3. **BUILD:** GEDCOM ↔ Identity linking UX
4. **FIX:** GEDCOM enrichment pipeline (so future Gemini calls get full context)
5. **IMPROVE:** API call logging (gemini_config, response_summary fields)
6. **HOUSEKEEPING:** Docs sync
