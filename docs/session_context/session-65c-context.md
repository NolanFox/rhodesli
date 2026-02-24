# Session 65c Context: Upload Fix (FOR REAL), Harness Enforcement, Verification Sweep

## Source
- **Date:** 2026-02-24
- **Origin:** 65a + 65b assessment, Nolan walkthrough (Feb 23), accumulated gaps
- **Previous sessions:** 65a (upload "fix" — added error detection, not actual fix), 65b (skipped upload verification citing "admin auth required")
- **App version:** v0.69.0
- **Production URL:** https://rhodesli.nolanandrewfox.com

---

## PART 1: UPLOAD IS STILL BROKEN — HISTORY OF FAILURE

### Timeline of Upload Failure
- **Feb 23 walkthrough:** Nolan uploaded `morris_mazal_ancestry_murry_army.jpeg`. Progress bar stuck at "Processing 0/1 (0%)". Never completed. This is the #1 blocker.
- **Session 65a (Phase 1):** Added subprocess PID tracking, death detection, 5-min timeout. 8 tests written. **Never verified in production.** The fix detects failure faster but does not fix the root cause of WHY the subprocess dies.
- **Session 65b (Phase 1):** Attempted production verification. **Skipped upload** with excuse "admin auth required." Verified compare, overlay, share links, navigation (5/6 pass). Upload remains untested and broken.

### Why This Is Unacceptable
Upload is the single most critical feature. Without working uploads:
- No new photos can be added to the archive
- The app cannot grow beyond its current 271 photos
- Community members cannot contribute photos
- Nolan cannot even use his own app
- Every other feature (compare, identify, GEDCOM linking) depends on having photos in the system

**This session does not end until upload works in production, verified by browser automation with screenshots.**

### The Auth Excuse Is Invalid
"Admin auth required" is not a reason to skip. Solutions:
1. **Claude Chrome plugin:** Nolan is logged in as admin in Chrome. The Chrome plugin inherits his session. Use it.
2. **Playwright with cookies:** Export auth cookies from the browser, inject into Playwright session.
3. **Direct API call with auth token:** Get the Supabase auth token from environment variables, pass as header.
4. **Temporarily disable auth on upload route for testing:** Add a test-only bypass, verify, then remove it.

Pick whichever works. Do not skip.

---

## PART 2: ALL UPLOAD SURFACES IN THE APP

Upload is not just /upload. Every place a user can provide a photo must work:

### 2A: /upload (Main Upload Page)
- Drop zone for JPG/PNG/ZIP
- Collection, Source, Source URL metadata fields
- Progress bar with real-time updates
- After upload: photo appears in library, faces detected

### 2B: /compare/pair (Compare Two Photos)
- Each panel has an upload zone for a photo
- After upload: faces detected, shown in panel
- Upload here may use a different code path than /upload

### 2C: /estimate (Age/Date Estimation)
- Upload a photo to get estimated dates
- May use yet another upload code path

### 2D: Any Other Upload Surfaces
- Check for upload inputs on: Help Identify flow, any admin pages, any API endpoints that accept photos
- `grep -rn "upload\|file.*input\|drop.*zone\|multipart" app/ --include="*.py" --include="*.html"` to find all

**Every upload surface must be tested. If any use different code paths, they all need the fix.**

---

## PART 3: REMAINING GAPS FROM 65b EVALUATION

### 3A: GEDCOM Linking — No Browser Verification of End-to-End Flow
65b built the GEDCOM linking feature (20 tests) but never browser-tested the actual admin flow: identify face → see GEDCOM matches → click link → see success. Must verify in production.

### 3B: Enriched Pipeline Sample Run
The enrichment fix (curated → first_order) was applied to code but never tested against real Gemini API calls. Run 10-20 photos through the fixed pipeline to verify:
- GEDCOM context is actually 400-1000+ tokens (not 106)
- Gemini responses are richer with the additional context
- `gemini_config` and `response_summary` fields are populated
- Cost per call is in expected range

### 3C: Assessment File Missing from Harness
65b did not produce an assessment file. The harness (CLAUDE.md) must mandate this as a persistent rule, not just a prompt instruction that gets lost during context compaction.

### 3D: Prompt-Writing Template
Create `docs/templates/session-prompt-template.md` — a checklist/template for writing session prompts that encodes our hard-won lessons:
- Small phases with /clear between them
- Browser verification mandated for all UX changes
- Assessment file always produced
- Data safety rules for production testing
- AD entries with full provenance
- Session context files in `docs/session_context/`

---

## PART 4: SELF-EVALUATION PROTOCOL

### What Must Happen at Session End
After all feature phases complete, the session must run a **self-evaluation phase** that:
1. Re-reads the original prompt
2. Checks every phase/task against actual output
3. For each item: PASS (with evidence), FAIL (with explanation), or PARTIAL
4. If any FAIL or PARTIAL: runs targeted fix-up work right there
5. After fix-ups: re-evaluates
6. Writes `docs/assessments/session-65c-assessment.md` with:
   - Full evaluation table
   - Any fix-ups performed
   - Red flags or concerns for next session
   - Recommended next session priorities
7. Includes the evaluation results in the final console output (not just the file)

### Why Visible Output Matters
If the evaluation is only in a file, there's no guarantee Claude Code actually did the work vs writing a superficial "all good" summary. By mandating the evaluation results appear in console output, Nolan can verify at a glance.

---

## PART 5: BROWSER TESTING INSTRUCTIONS

### Primary: Claude Chrome Plugin
The Claude Chrome plugin runs inside Nolan's browser where he is already logged in as admin. This solves the auth problem completely.

**How to use:**
- Call the browser tool to navigate to URLs
- Take screenshots at each verification step
- Interact with page elements (click, type, upload files)
- Check DOM for expected elements

### Fallback: Playwright with Auth
If Chrome plugin is unavailable:
```bash
pip install playwright
playwright install chromium
```

To handle auth, either:
- Export cookies from Chrome and inject into Playwright context
- Use Supabase auth API to get a session token programmatically
- Check environment for `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

### Data Safety Rules
1. **Use synthetic test images only** — solid color squares, clearly not heritage photos
2. **Name test files:** `_test_65c_delete_me_[N].jpg`
3. **After verification: DELETE all test data** from app library AND R2 storage
4. **Screenshot every step** → `docs/screenshots/session-65c/`

---

## PART 6: ARCHITECTURE REMINDERS

### Stack
FastHTML + Starlette | InsightFace + PyTorch CORAL | Supabase + JSON | Cloudflare R2 | Railway | Supabase Auth

### Upload Pipeline (as understood)
1. User drops file in browser → JS sends multipart POST
2. Server receives file → saves to temp location
3. Subprocess spawned for processing (face detection, R2 upload, metadata extraction)
4. Progress updates sent via SSE or polling
5. On completion: photo added to library, faces indexed

### Key Environment Variables (likely needed for upload debugging)
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- Check Railway dashboard or `.env` for these

### Deployment
`git push origin main` → Railway auto-deploys. Smoke test after every push.
