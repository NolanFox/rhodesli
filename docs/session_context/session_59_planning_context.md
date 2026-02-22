# Session 59 Planning Context — Face Compare Standalone

## Breadcrumb: Why We're Here

### The vision

Build a standalone face comparison experience that lets anyone upload
a photo and instantly find matching faces in a historical archive.
This is the "wow moment" you can text to an interviewer, share in
the Rhodes Facebook group, or pull up on your phone at a family dinner.

### Why now

Sessions 55b-58 built the ML infrastructure: ONNX serving contract,
CORAL date estimation, similarity calibration, MLflow registry. The
models work. What's missing is a user-facing experience that showcases
all three ML systems working together in one interaction.

### Sessions that feed into this

| Session | Contribution |
|---------|-------------|
| 23-25   | CORAL date estimation model trained |
| 32      | Initial compare tool with kinship calibration (AD-067/068/069) |
| 47      | Gatekeeper pattern for ML outputs |
| 55b     | Similarity calibration ONNX model |
| 56      | Landing page with feature cards, lazy loading |
| 57      | CORAL ONNX in production, /estimate endpoint |
| 58      | MLflow registry, promote_model.py |

---

## Architecture Decision: Route, Not Service

### Decision: Option 2 — same codebase, standalone UX

The compare tool lives as a route within Rhodesli (`/facecompare`) but
is designed as a self-contained experience with its own header, no
archive navigation required, and a completely standalone feel.

### Why not a separate service (Option 1)

- Code duplication for ML inference (same InsightFace, CORAL, calibration)
- Two Railway deployments to maintain
- Embeddings and photo data need to be accessible from both services
- Double the infrastructure cost for identical ML models

### Why not a shared library yet (Option 3)

- Premature abstraction — only one community archive exists
- Extract the shared library when a second community is added
- The current architecture doesn't prevent this later extraction

### The route strategy: /facecompare vs /compare

The app already has `/compare` (Session 32) — an archive-integrated
face comparison tool with the full Rhodesli nav bar. The new
`/facecompare` is a separate standalone experience:

- `/compare` = "tool for residents" — users already in the archive
- `/facecompare` = "front door for strangers" — entry point for
  people who've never heard of Rhodesli

Both coexist in the same codebase. `/facecompare` has its own layout
(no archive nav), its own design (museum-quality), and its own purpose
(viral sharing + discovery). Bridge CTAs lead users into the archive.

Railway Hobby plan limits one custom domain (already used for
`rhodesli.nolanandrewfox.com`), so a separate subdomain isn't
possible without upgrading to Pro ($20/mo). The shareable URL
`rhodesli.nolanandrewfox.com/facecompare` is clean and functional.

### Path to expansion beyond Rhodes

The compare route is community-agnostic from day one:
- Don't hardcode "Jews of Rhodes" in the compare UX
- Use language like "historical archive" or "community archive"
- Results show which collection a match came from
- When a second community is added, it's a dropdown, not a rewrite

---

## Competitive Analysis: What Exists and Why We're Better

### FamilySearch Compare-a-Face

Upload your photo, compare against your ancestors' portraits in your
family tree (up to 6 generations). Ranked results with resemblance
percentages. Requires login + existing tree with photos. Entertainment-
framed ("Who do you look like?") not identification-framed.

**Key insight:** One genealogist hacked it to identify unknown faces
by uploading the unknown photo and matching to known ancestors. This
IS our use case — but we're purpose-built for it.

### MyHeritage Photo Features

Animates faces (Deep Nostalgia, 119M+ animations), colorizes photos,
enhances quality. Face matching within YOUR collection only.
$199-$299/year. Proved genealogy + AI = viral sharing, but their
matching doesn't solve identification.

### Related Faces / Google Photos / Generic tools

Related Faces: purpose-built for genealogy identification, cross-
account matching, but requires collection building first. Google
Photos: best-in-class aging recognition but only YOUR library.
Generic tools (FacePair, mxface): compare A vs B only, no archive.

### What makes Rhodesli's Compare fundamentally different

| Capability | FamilySearch | MyHeritage | Related Faces | Rhodesli |
|-----------|-------------|-----------|--------------|---------|
| Compare against community archive | ✗ (own tree only) | ✗ (own photos) | Partial | **✓** |
| Multi-face detection in uploads | ✗ | ✓ | ✗ | **✓** |
| No account required for basic use | ✗ | ✗ | ✗ | **✓** |
| Calibrated confidence tiers | ✗ (raw %) | ✗ | Partial | **✓** |
| Date estimation on uploaded photo | ✗ | ✗ | ✗ | **✓** |
| Links to known identity profiles | ✗ | ✗ | ✗ | **✓** |
| Free, no subscription | ✗ | ✗ | ✗ | **✓** |
| Purpose: identification, not entertainment | ✗ | ✗ | **✓** | **✓** |

The killer combination: upload ANY photo → detect ALL faces →
for each face, find matches in a curated historical archive WITH
calibrated confidence AND estimated date AND links to identified
people's stories. No login required. Free. On your phone.

---

## UX Design Direction

### Design philosophy

The biggest problem with existing tools is they feel either:
- Utility-grade ugly (mxface, FacePair, Related Faces)
- Subscription-gated entertainment (MyHeritage, FamilySearch)

We want: **museum-quality presentation meets instant utility.**
Think: the feel of a well-curated exhibit, but the speed of an app.

### The emotional arc

1. **Landing:** "Who is in your photo?" — single upload CTA, clean
2. **Processing:** Brief loading with face detection visualization
3. **Discovery:** "We found N faces" with face selector if multiple
4. **Results:** Tiered matches with photos, names, confidence, dates
5. **Connection:** "This is Leon Franco, born 1902. Explore his story →"
6. **Share:** Shareable result URL, "Know someone? Help identify them"

### Mobile-first

This will be used on phones at family gatherings. Design for:
- Thumb-friendly upload (camera or gallery)
- Swipeable results
- Readable on small screens
- Fast on mobile networks

### No login wall

The compare experience must work without any account. This is the
entry point — the funnel, not the product. Users who discover matches
get drawn into the archive. The CTA is "Explore more" not "Sign up."

### Community-agnostic language

The standalone experience uses:
- "historical archive" not "Jews of Rhodes archive"
- "community" not specific community names
- Collection name appears in results: "Match found in: Jews of Rhodes"

---

## Technical Architecture

### What already exists (from Session 32)

- `/facecompare` route with basic upload UI
- Upload persistence to `uploads/facecompare/{uuid}.ext`
- Multi-face detection with face selector UI
- Kinship calibration thresholds (AD-067): strong <1.16, possible <1.31
- Tiered results: Identity Match, Possible Match, Similar Faces, Other
- CDF-based confidence percentages

### What needs to change

1. **Standalone landing page:** New self-contained page at `/facecompare`.
   No sidebar, no archive nav. Its own header with just the tool name.
   Completely separate from the existing `/compare` page.

2. **Date estimation integration:** After face detection, also run
   CORAL on the uploaded photo. Show estimated decade alongside
   face matches. "Your photo appears to be from the 1930s."

3. **Results redesign:** Museum-quality presentation of matches.
   Each match shows: archive photo, person name (if identified),
   confidence tier with visual indicator, decade estimate, link to
   person's page in the archive.

4. **Shareable results:** Each comparison gets a permalink
   (`/facecompare/result/{uuid}`) that can be shared. Shows the same
   results without needing to re-upload.

5. **Bridge CTAs:** "Explore the full archive →", "Know someone in
   this photo? Help identify them →", "See more photos from this era →"

### InsightFace on Railway

InsightFace is already in the Docker image (required for the upload
pipeline). The face detection and embedding generation work in
production. This is NOT a new dependency — it was validated in
Session 32 and subsequent sessions.

### Upload storage

Uploads go to local filesystem on Railway. For this session, that's
acceptable — uploads are transient (for comparison purposes). If
engagement warrants it, a future session migrates to R2. The key
decision: do NOT block the compare experience on solving storage
permanence. Store the result JSON (matches, scores) for shareable
results — not the uploaded photo long-term.

### SEO / Discoverability

- `/facecompare` gets its own meta tags (separate from archive pages)
- OpenGraph tags for shared results (preview image of the match)
- Page title: "Face Compare — Find matches in historical archives"
- Google can index it independently of the archive pages

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| InsightFace memory on Railway | Already validated — in Docker image |
| Upload storage on Railway ephemeral disk | Store result JSON, not photos long-term |
| Session scope creep (too much UX polish) | Ship functional first, polish later |
| Subdomain DNS propagation delay | Deferred — Railway Hobby plan limit. Use /facecompare route. |
| CORAL + InsightFace + CalibrationService all loading | Models already loaded on startup |
| Mobile upload handling | Use standard HTML file input with accept="image/*" |

---

## Deferred Items

| Item | Target Session |
|------|---------------|
| Gemini Progressive Refinement | 60 |
| Interactive Upload UX (SSE) | 61 |
| Admin/Public UX Unification | 62 |
| Docker Image Slimming | 63+ |
| R2 migration for compare uploads | Future (if engagement warrants) |
| compare.nolanandrewfox.com subdomain | Future (requires Railway Pro $20/mo) |
| Second community archive integration | Future (expansion) |
