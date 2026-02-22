# RHODESLI — Session 59: Face Compare Standalone

## ROLE

You are Lead Engineer for Rhodesli, a heritage photo archive with ML-powered face recognition for the Jewish community of Rhodes. Stack: FastHTML + HTMX + InsightFace + Supabase + Cloudflare R2 + Railway.

## SESSION GOALS (in priority order)

1. **Build a standalone face comparison landing page** at `/facecompare` — no login, no sidebar, mobile-first, museum-quality design
2. **Integrate all three ML systems** into a single user flow: InsightFace (face detection + embeddings), similarity calibration (calibrated match confidence), CORAL (date estimation)
3. **Create shareable result URLs** at `/facecompare/result/{uuid}`
4. **Add bridge CTAs** from compare results into the full archive
5. **Session documentation + verification gate**

**The test for this session:** A user visits `rhodesli.nolanandrewfox.com/facecompare` on their phone, uploads a photo, sees detected faces, selects one, gets tiered matches with calibrated confidence + date estimation + links to identified people, and can share the result URL with someone else who sees the same results.

## WHY THIS SESSION (Breadcrumb)

Sessions 55b-58 built the ML infrastructure. Two ONNX models are deployed (date estimation, similarity calibration), the MLflow registry tracks versions, and the serving contract separates user-facing requests from heavy processing. But there's no interactive demo that showcases these systems working together. This session creates that demo.

**Portfolio impact:** "Upload a photo and my system detects faces, finds matches in a historical archive with calibrated confidence scores, and estimates the photo's decade — all running local ONNX models on a $5/month Railway instance."

**Growth impact:** This is the viral entry point. Someone shares a link on Facebook: "I uploaded my grandmother's photo and it found her in a 1930s archive from Rhodes." That person's friend tries it. The archive grows.

Read `docs/session_context/session_59_planning_context.md` for full architecture, competitive analysis, and design direction.

## SCOPE

### IN SCOPE (this session — target ~90 min)

- P1: Orient + checkpoint + understand existing compare code (~5 min)
- P2: Standalone landing page design (~20 min)
- P3: Upload flow + multi-face detection + face selector (~20 min)
- P4: Results page with all 3 ML systems + tiered display (~25 min)
- P5: Shareable results + bridge CTAs (~10 min)
- P6: Verification gate + docs (~10 min)

### OUT OF SCOPE

- Gemini Progressive Refinement → Session 60
- R2 migration for uploaded photos (local filesystem for now)
- Account creation / login from compare (just CTAs)
- Admin features or moderation queue for uploaded photos
- Permanent storage of uploaded photos (result JSON only)
- Animation / Deep Nostalgia-style features

## NON-NEGOTIABLE RULES

### Execution Rules

1. Run `pytest tests/ -x -q` before each commit.
2. Commit after every logical unit.
3. Update ALGORITHMIC_DECISIONS.md with every decision.
4. No doc over 300 lines. CLAUDE.md under 80 lines.
5. Mobile-first: test all layouts at 375px width.
6. No login wall: the entire compare flow works without authentication.

### Documentation Rules (COMPACTION PROTECTION)

1. Save this prompt to `docs/prompts/session_59_prompt.md` immediately.
2. Create checkpoint at `docs/session_context/session_59_checkpoint.md`.
3. Update checkpoint after EVERY phase.

### Design Rules

1. **NO generic AI aesthetics.** No Inter font, no purple gradients,
   no cookie-cutter cards. This should look intentionally designed.
2. **Museum-quality presentation.** Think editorial photo layouts,
   generous whitespace, thoughtful typography.
3. **Community-agnostic language.** Use "historical archive" not
   "Jews of Rhodes" in the compare UI. Collection name appears in
   results only: "Match found in: Jews of Rhodes Community Archive."
4. **FastHTML + HTMX only.** No React, no JavaScript frameworks.
   Vanilla JS for upload handling and face selection only.

---

## PHASE 0: Orient + Checkpoint (~5 min)

### 0A: Read state

```bash
cat CLAUDE.md
head -20 CHANGELOG.md
git log --oneline -5
cat docs/session_context/session_58_checkpoint.md 2>/dev/null | tail -20
```

### 0B: Read planning context

```bash
cat docs/session_context/session_59_planning_context.md
```

If this file doesn't exist, create it from the companion document provided with this prompt.

### 0C: Understand existing compare code

The app already has a `/compare` page (Session 32). The new
`/facecompare` is a SEPARATE standalone experience. Understand
what exists so you can reuse ML logic without touching the old page.

```bash
# What compare routes exist?
grep -n "compare" app/*.py app/**/*.py 2>/dev/null | head -30

# What's the current compare page structure?
grep -n "def.*compare\|@app.*compare\|rt.*compare" app/*.py 2>/dev/null | head -20

# What upload handling exists?
ls uploads/compare/ 2>/dev/null | head -5
grep -n "upload" app/*.py app/**/*.py 2>/dev/null | head -20

# What's the kinship calibration data?
cat rhodesli_ml/data/model_comparisons/kinship_thresholds.json 2>/dev/null

# Check what ONNX services are available
grep -n "class.*Service\|CalibrationService\|DateEstimation" app/*.py app/**/*.py 2>/dev/null | head -10

# Check the existing compare CSS
grep -n "compare" app/static/*.css 2>/dev/null | head -10
```

### 0D: Save prompt + create checkpoint

Save this prompt to `docs/prompts/session_59_prompt.md`. Create checkpoint at `docs/session_context/session_59_checkpoint.md`.

### 0E: Install compact hooks

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'echo \"=== POST-COMPACTION RECOVERY ===\"; echo \"Read docs/prompts/session_59_prompt.md for instructions.\"; echo \"Read docs/session_context/session_59_checkpoint.md for progress.\"; echo \"Session 59: Face Compare Standalone. ~90 min. Resume from checkpoint.\"; echo \"=== END RECOVERY ===\"'"
          }
        ]
      }
    ]
  }
}
```

Commit: `chore(harness): session 59 orient — checkpoint + compact hooks`

---

## PHASE 1: Standalone Landing Page (~20 min)

**Important context:** An existing `/compare` page already exists in
the app (Session 32). It's integrated into the archive nav and serves
users who are already browsing the archive. DO NOT modify it.

`/facecompare` is a NEW, separate page — the "front door for strangers."
It has its own self-contained design, no archive nav, and is optimized
for someone who's never heard of Rhodesli. The existing `/compare`
continues to serve archive users.

### 1A: Create the /facecompare route

Register a new route at `/facecompare` that renders a standalone page.
This page should NOT use the standard Rhodesli layout template (no
archive nav bar, no sidebar). It has its own minimal header.

### 1B: Design the standalone landing page

This is the most design-critical deliverable. The page needs to
immediately communicate what it does and invite upload. Study the
planning context's competitive analysis and design direction.

**Required elements:**

1. **Hero section:** Clean, compelling headline. Something like
   "Find faces in history" or "Who is in your photo?" — NOT
   "AI-Powered Face Recognition Tool" (that's developer-speak).
   Subtitle: brief explanation. Single prominent upload button.

2. **How it works:** 3-step visual (Upload → Detect → Discover).
   Keep it tight — this isn't a tutorial, it's confidence-building.

3. **Sample results preview:** Show what a result looks like using
   an anonymized/representative example. This tells users what to
   expect before they commit to uploading.

4. **Footer:** Minimal. Link to full archive. Privacy note
   ("Your photo is processed and not stored permanently").

**Design direction:**

- Editorial, not enterprise. Think magazine layout, not SaaS landing.
- Warm, sepia-adjacent color palette (heritage/archival feel).
- A single distinctive serif font for headlines, clean sans for body.
- Import fonts from Google Fonts CDN.
- Generous whitespace. Let the photos breathe.
- Subtle texture/grain overlay for archival atmosphere.
- NO stock photography. Use actual archive photos (blurred/cropped
  as needed for the preview section).

**Mobile layout:**

- Stack vertically. Upload button thumb-friendly (min 48px tap target).
- Hero image scales down or becomes a subtle background.
- "How it works" steps stack as vertical timeline, not horizontal.

### 1C: SEO meta tags

Add meta tags for the facecompare page:
- `<title>` Face Compare — Find matches in historical archives
- OpenGraph tags (og:title, og:description, og:image)
- Description meta tag for Google indexing

### 1D: Tests for Phase 1

- Landing page renders at `/facecompare` (200 status)
- Landing page contains upload form/button
- Landing page does NOT contain the archive navigation bar
- Meta tags are present (title, og:title, og:description)
- Existing `/compare` page still works and is unmodified
- Page works without JavaScript (progressive enhancement)

Commit: `feat(facecompare): standalone landing page at /facecompare`

---

## PHASE 2: Upload Flow + Face Detection + Face Selector (~20 min)

### 2A: Upload handler

When user selects/drops a photo:

1. Upload to server via HTMX or fetch
2. Save to `uploads/facecompare/{uuid}.{ext}`
3. Run InsightFace face detection
4. Return detected faces with bounding boxes

Accept: JPEG, PNG, WebP. Max size: 10MB. Validate on client AND server.

Show a loading state during processing. This is a critical UX moment —
the user needs feedback that something is happening. Use HTMX to swap
in a processing indicator, then swap in results when ready.

### 2B: Multi-face detection and selector

If >1 face detected:
- Show the uploaded photo with numbered bounding boxes overlaid
- Let user click/tap a face to select it for comparison
- Selected face gets highlighted, others dimmed
- URL updates: `/facecompare?upload={uuid}&face={index}`

If exactly 1 face detected:
- Skip selection, go straight to results
- Still show the detected face highlighted in the photo

If 0 faces detected:
- Show helpful message: "No faces detected. Try a clearer photo
  with faces visible and well-lit."
- Offer to try again

### 2C: Face detection visualization

Show bounding boxes as semi-transparent overlays on the uploaded
photo. Number each face. On hover/tap, show a cropped thumbnail
of that face. This is a differentiator — competitors just crop
to one face and discard the rest.

### 2D: Run CORAL date estimation on the uploaded photo

While detecting faces, also run the CORAL model on the full image:
- Show: "Your photo appears to be from the [decade]s"
- If decade probability bars are available, show them
- This adds context even before the face comparison runs

### 2E: Tests for Phase 2

- Upload endpoint accepts image files
- Upload rejects non-image files (400 status)
- Upload rejects files >10MB (413 status)
- Multi-face photo returns multiple detected faces with bounding boxes
- Single-face photo auto-selects the one face
- Zero-face photo returns appropriate error message
- Upload creates file in uploads/facecompare/ directory
- CORAL date estimation runs on uploaded photo
- Face selector UI updates URL with face index parameter

Commit: `feat(compare): upload flow with multi-face detection and date estimation`

---

## PHASE 3: Results Page — All 3 ML Systems (~25 min)

This is the core deliverable. The results page showcases three ML
systems working together:

1. **InsightFace:** Detected faces, generated embeddings
2. **Similarity calibration:** Calibrated confidence tiers
3. **CORAL:** Date estimation for the uploaded photo

### 3A: Run similarity comparison

For the selected face:
1. Get its embedding from InsightFace
2. Compare against all embeddings in the archive
3. Apply calibrated thresholds (from kinship_thresholds.json)
4. Group results into tiers:
   - **Strong Match** (distance < 1.16): Green indicator, high confidence
   - **Possible Match** (distance < 1.31): Amber indicator
   - **Similar Features** (distance < 1.36): Blue indicator
   - Below threshold: don't show (not "Other Faces")

### 3B: Results layout

Each match card shows:
- Archive photo (thumbnail from the archive)
- Person name (if identified) or "Unidentified Person"
- Confidence tier with visual indicator (color + label)
- Confidence percentage (CDF-based, from Session 32's sigmoid approx)
- Collection: "Jews of Rhodes Community Archive"
- If person is identified: link to their person page
- If photo has a date: show it

**Layout:** Grid on desktop (2-3 cards per row), stack on mobile.
Cards should have generous spacing, subtle shadows, and the archival
aesthetic from the landing page.

**Above the results grid:**
- The uploaded photo with selected face highlighted
- Date estimation: "Your photo appears to be from the 1930s"
- Summary: "We found N potential matches in the archive"

### 3C: Empty state

If no matches above the "Similar Features" threshold:
- "No strong matches found in the archive — but that doesn't mean
  they aren't here. Historical photos vary in quality and angle."
- Offer: "Browse the archive yourself →" / "Try a different photo"

### 3D: Tiering logic

Use the existing kinship calibration from Session 32 (AD-067).
The thresholds are empirically derived from 46 confirmed identities:
- Same person: mean=1.01, std=0.19
- Same family: mean=1.34, std=0.07
- Different person: mean=1.37, std=0.06

The tiers map to these distributions. Do NOT change the thresholds
without re-running calibration — document this as an AD if tempted.

### 3E: Tests for Phase 3

- Results page shows tiered matches for a known face
- Tiers are correctly ordered (Strong > Possible > Similar)
- Each match card contains: photo, name/placeholder, confidence, tier
- Date estimation appears in results header
- Empty state renders when no matches found
- Results include collection name
- Identified persons have links to their person pages
- Confidence percentages are between 0-100%

Commit: `feat(compare): results page with calibrated tiers, date estimation, and archive links`

---

## PHASE 4: Shareable Results + Bridge CTAs (~10 min)

### 4A: Persist comparison results

When a comparison completes, save the result to a JSON file:

```python
# uploads/facecompare/results/{uuid}.json
{
    "upload_uuid": "abc123",
    "face_index": 0,
    "date_estimation": {"decade": "1930s", "confidence": 0.72},
    "matches": [
        {
            "person_id": "P001",
            "person_name": "Leon Franco",
            "photo_id": "photo_123",
            "distance": 0.98,
            "tier": "strong_match",
            "confidence_pct": 87.3
        }
    ],
    "created_at": "2026-02-22T03:00:00Z"
}
```

### 4B: Shareable result URL

`/facecompare/result/{uuid}` loads the persisted result and renders it
WITHOUT requiring the original upload. The result page shows:
- Cropped face from the original (save a small thumbnail)
- All matches with the same layout as the live results
- Meta tags for social sharing (og:title, og:image)

### 4C: Share UI

After results load, show share options:
- "Share this result" button → copy link to clipboard
- Web Share API on mobile (navigator.share)
- Social-friendly preview text: "I found a match in a historical
  archive from the 1930s! See the results →"

### 4D: Bridge CTAs

At the bottom of results (and in each match card):

1. **For identified matches:** "Explore [Name]'s story in the archive →"
   Links to the person's page in the full Rhodesli archive.

2. **For unidentified matches:** "Know this person? Help identify them →"
   Links to the archive photo page (where admin can eventually
   review and confirm).

3. **General:** "Explore the full archive →" links to the main
   Rhodesli landing page.

4. **Upload CTA:** "Have more photos? Upload to the archive →"
   Links to the upload flow (login required — make that clear).

### 4E: Tests for Phase 4

- Result JSON is persisted after comparison
- Shareable URL `/facecompare/result/{uuid}` renders correctly
- Shareable URL returns 404 for non-existent UUID
- Share button is present in results
- Bridge CTAs link to correct archive pages
- OG meta tags are present on result pages

Commit: `feat(compare): shareable results with bridge CTAs to archive`

---

## PHASE 5: Verification Gate + Documentation (~10 min)

### 5A: Full verification

```bash
echo "=== SESSION 59 VERIFICATION GATE ==="

echo "--- Phase 0: Checkpoint ---"
ls docs/prompts/session_59_prompt.md && echo "✓ Prompt" || echo "✗ MISSING"
ls docs/session_context/session_59_checkpoint.md && echo "✓ Checkpoint" || echo "✗ MISSING"
ls docs/session_context/session_59_planning_context.md && echo "✓ Planning context" || echo "✗ MISSING"

echo "--- Phase 1: Landing Page ---"
# Test that /facecompare returns 200
python3 -c "
from app.main import app
from starlette.testclient import TestClient
client = TestClient(app)
resp = client.get('/facecompare')
print(f'/facecompare status: {resp.status_code}')
assert resp.status_code == 200, 'Facecompare page failed'
assert 'upload' in resp.text.lower(), 'No upload element found'
print('✓ Standalone landing page works')

# Verify existing /compare still works
resp2 = client.get('/compare')
print(f'/compare status: {resp2.status_code}')
assert resp2.status_code == 200, 'Existing compare page broken!'
print('✓ Existing /compare still works')
" 2>/dev/null || echo "✗ Landing page check failed"

echo "--- Phase 2: Upload Flow ---"
# Verify upload endpoint exists
grep -q "upload" app/*.py && echo "✓ Upload handler" || echo "✗ MISSING"

echo "--- Phase 3: Results ---"
# Verify tiered results logic exists
grep -q "strong_match\|Strong Match\|tier" app/*.py && echo "✓ Tiered results" || echo "✗ MISSING"

echo "--- Phase 4: Shareable Results ---"
ls uploads/facecompare/results/ 2>/dev/null && echo "✓ Results directory" || echo "Results dir will be created on first use"
grep -q "compare/result" app/*.py && echo "✓ Shareable route" || echo "✗ MISSING"

echo "--- Tests ---"
pytest tests/ -x -q 2>&1 | tail -5

echo "--- Cross-cutting ---"
wc -l CLAUDE.md | awk '{if ($1 > 80) print "✗ CLAUDE.md over 80 lines: "$1; else print "✓ CLAUDE.md: "$1" lines"}'

echo "=== END VERIFICATION GATE ==="
```

### 5B: Manual test checklist (for user)

Document in checkpoint for manual verification:

```markdown
## Manual Test Checklist
- [ ] Visit /facecompare — landing page loads, looks good on mobile
- [ ] Upload a photo — face detection runs, shows bounding boxes
- [ ] Upload group photo — multiple faces shown, can select one
- [ ] Select a face — results load with tiered matches
- [ ] Results show date estimation for uploaded photo
- [ ] Strong matches link to person pages in archive
- [ ] Share button works (copies URL)
- [ ] Shared URL loads results without re-uploading
- [ ] Page looks good at 375px width (mobile)
- [ ] Page looks good at 1440px width (desktop)
```

### 5C: Update session documentation

**CHANGELOG.md:** Add entry:
- Face Compare Standalone at /facecompare — upload a photo, find matches in the archive
- Three ML systems in one flow: face detection, calibrated similarity, date estimation
- Shareable result URLs with social preview tags
- Mobile-first, no-login-required design
- Separate from existing /compare (archive-integrated tool)

**ROADMAP.md:**
- Session 59 → Recently Completed
- Verify Session 60 (Gemini Progressive Refinement) is next

**ALGORITHMIC_DECISIONS.md:** Document:
- AD-XXX: Standalone at /facecompare separate from existing /compare
- AD-XXX: Compare Standalone as route (not separate service)
- AD-XXX: Community-agnostic compare UX for future expansion

**tasks/lessons.md:** Add:
- Separate /facecompare from /compare: "front door for strangers" vs "tool for residents"
- Community-agnostic language in ML tools enables future expansion
- Museum-quality design for ML demos > developer-quality utility screens
- Three ML systems in one user interaction = compelling portfolio demo

### 5D: Final commit and push

```bash
git add -A
git commit -m "docs: session 59 verification gate — face compare standalone complete"
git push origin main
```

Update checkpoint: SESSION COMPLETE.

---

## TIME ESTIMATES

| Phase | Est. Time | Priority |
|-------|-----------|----------|
| 0: Orient + checkpoint | 5 min | MUST DO |
| 1: Standalone landing page | 20 min | MUST DO |
| 2: Upload + face detection + selector | 20 min | MUST DO |
| 3: Results with 3 ML systems | 25 min | MUST DO |
| 4: Shareable results + CTAs | 10 min | SHOULD DO |
| 5: Verification + docs | 10 min | MUST DO |
| **Total** | **~90 min** | |

If time is limited: Phases 1-3 are the minimum viable demo. Phase 4
(shareable results) is the highest-leverage addition beyond core.
Phase 5 verification is non-negotiable.

**Phase 3 is the core deliverable.** If Phases 1-2 take longer than
expected, simplify the landing page design and invest the time in
getting the results page right — that's what people share.

---

## CRITICAL REMINDERS (read these if context was compacted)

1. **You are in Session 59.** Read prompt, checkpoint, planning context.
2. **This is Face Compare Standalone at `/facecompare`.** A no-login, mobile-first tool.
3. **DO NOT modify the existing `/compare` page.** That's the archive-integrated tool from Session 32.
4. **Three ML systems in one flow:** InsightFace + Calibration + CORAL.
5. **Community-agnostic language.** "Historical archive" not "Jews of Rhodes."
6. **Museum-quality design.** No generic AI aesthetics. Editorial feel.
7. **Existing code:** Session 32 built `/compare`. Reuse ML logic but NOT the page layout.
8. **Kinship thresholds:** strong <1.16, possible <1.31, similar <1.36
9. **FastHTML + HTMX only.** No React. Minimal vanilla JS for uploads.
10. **Test suite:** `pytest tests/ -x -q` — app + ML tests must pass.
11. **ALGORITHMIC_DECISIONS.md** must capture every decision.
12. **No doc over 300 lines.** CLAUDE.md under 80.
13. **Out-of-scope:** Gemini (60), R2 upload migration, account creation, Deep Nostalgia, subdomain routing.
