# Case Study: Gemini Content Safety Filters vs Heritage Photo Preservation

**Date:** 2026-02-25
**Source:** Session 68 Photo Retry Analysis
**Related:** `docs/analysis/photo_retry_analysis.md`, AD-139 (Gemini 3.1 Pro)

---

## Summary

During batch face alignment of 266 heritage photos using Gemini 3.1 Pro,
2 photos were permanently blocked by Google's content safety filters.
Both photos depict children from the mid-20th century Rhodes Jewish
community. The block occurs specifically when the "forensic photo
analyst" prompt requests detailed facial analysis — simple description
prompts work fine for both images.

This case study documents the incident, its implications for heritage
archives using modern AI APIs, and mitigation strategies.

---

## What Happened

### The Pipeline

Rhodesli uses Gemini 3.1 Pro for face alignment — analyzing each photo
to generate per-face descriptions including estimated age, identifying
features, clothing, and historical context. The prompt instructs Gemini
to act as a "forensic photo analyst" and produce structured JSON output
for each detected face.

### The Batch Run

- 266 photos processed across multiple batches (Session 63-68)
- Total cost: $2.04 across all retries
- 264 photos (99.2%) processed successfully
- 2 photos permanently blocked: `PROHIBITED_CONTENT` finish reason

### The Blocked Photos

| Photo | Filename | Subject | Collection |
|-------|----------|---------|------------|
| 1 | Image 914_compress.jpg | Young girl with brown hair, braces, white robe | Vida Capeluto NYC |
| 2 | Image 018_compress.jpg | Young girl in plaid dress, standing outside | Vida Capeluto NYC |

Both are ordinary family photos from the Vida Capeluto collection —
typical mid-century snapshots of children in everyday settings. There
is nothing objectionable about the images themselves.

### Why They Were Blocked

The block is triggered by the **combination** of:
1. Images containing children (minors)
2. A prompt requesting detailed facial biometric analysis
3. The "forensic photo analyst" role framing

Evidence:
- HTTP 200 returned (API call technically succeeds)
- `response.text` is None (no content generated)
- `finish_reason` is `PROHIBITED_CONTENT`
- Simple prompts ("describe this photo") work fine for both images
- Each photo was attempted 4 times across different batches — all failed

This behavior is consistent with Google's Responsible AI policies
around child safety, which restrict facial biometric analysis of minors
regardless of the benign context.

---

## Implications for Heritage Archives

### The Tension

Heritage photo archives routinely contain images of children. Family
photo collections are, by definition, multigenerational — children
appear in wedding photos, school portraits, immigration documents,
holiday gatherings, and everyday snapshots.

Modern AI safety filters, designed to prevent facial recognition and
biometric profiling of minors, create a blanket restriction that does
not distinguish between:

- **Malicious use:** Building a facial recognition database of children
- **Heritage preservation:** Identifying a grandmother in her childhood
  photo to connect it to her descendants

For Rhodesli specifically, the Rhodes Jewish community was devastated
by the Holocaust in 1944. Many of the "children" in these photos are
now deceased. Their families are actively trying to identify and
preserve these images as part of cultural recovery. The safety filter
treats this preservation work identically to surveillance.

### Scale of Impact

- Current: 2 out of 266 photos (0.8%) — minimal
- At scale: Heritage archives with thousands of photos will have
  significantly more children's images. School photos, family
  gatherings, and community events often feature dozens of children.
- The Vida Capeluto NYC collection has the highest density of
  single-child portraits, which may be more likely to trigger filters
  than group photos where children are among adults.

### The Asymmetry

The safety filter applies equally to:
- A stranger uploading a child's photo for surveillance purposes
- A grandchild uploading their grandmother's childhood photo to
  connect it to her life story

There is currently no mechanism to communicate intent, context, or
legitimate heritage preservation use cases to the API.

---

## Mitigation Strategies

### Strategy 1: Prompt Reformulation (Recommended First Try)

Modify `build_alignment_prompt()` to avoid triggering language:
- Replace "forensic photo analyst" with "historical photo archivist"
- Replace "biometric analysis" with "visual description"
- Reduce specificity of facial feature requests for detected minors
- Frame age estimation as "approximate era/generation" not "age"

**Risk:** May reduce output quality for all photos. Requires A/B
testing across the full corpus.

**Cost:** Development time + ~$0.06 to re-run the 2 blocked photos.

### Strategy 2: Adaptive Prompting

When a photo returns `PROHIBITED_CONTENT`:
1. Automatically retry with a gentler prompt variant
2. Request "general description" instead of "facial analysis"
3. Accept reduced-detail output for flagged photos
4. Log the fallback for admin review

**Advantage:** Preserves full-detail prompts for non-flagged photos.
**Complexity:** Requires prompt variant system and retry logic.

### Strategy 3: Accept Partial Coverage

For 2 out of 266 photos, manual description by the admin is feasible:
- Admin views the photo and writes a brief description
- Stored in the same face_alignment table as Gemini outputs
- Marked with `source: "manual"` for provenance

**Advantage:** Zero engineering effort. Works now.
**Disadvantage:** Does not scale if the archive grows to thousands.

### Strategy 4: Alternative API

Use a different vision API (Claude, OpenAI) for flagged photos:
- Different providers have different safety thresholds
- Could use as automatic fallback when Gemini returns PROHIBITED

**Risk:** Multiple API integrations to maintain. Different output
formats require normalization. Additional API keys and billing.

### Strategy 5: Local Vision Model

Run a local vision-language model (LLaVA, CogVLM) for flagged photos:
- No content safety filters in local models
- Runs on development machine (not production)

**Risk:** Lower quality than Gemini 3.1 Pro. Significant setup.
Only worthwhile if blocked photo count grows substantially.

---

## Recommended Approach

For the current 2-photo situation: **Strategy 3** (manual description).
The admin can describe these two photos in under 5 minutes.

For future scale: **Strategy 2** (adaptive prompting) as the first
automated defense, with **Strategy 1** (prompt reformulation) as a
broader improvement. Implement when blocked photos exceed 5% of corpus.

---

## Broader Context

This is not unique to Rhodesli. Any heritage, genealogy, or historical
archive project using modern AI APIs will encounter this tension. The
key insight is that content safety policies are designed for the
general case (preventing harm) and do not yet have mechanisms for
legitimate heritage preservation use cases.

Potential industry-level solutions:
- **Verified heritage archive programs:** API providers could offer
  reduced restrictions for verified cultural preservation projects
- **Context-aware safety:** Filters that consider the broader context
  (archive vs. surveillance) rather than just image + prompt content
- **Appeal mechanisms:** A way to submit specific images for manual
  review and exemption

Until such mechanisms exist, heritage archives must design their
pipelines to gracefully degrade when safety filters activate.

---

## References

- `docs/analysis/photo_retry_analysis.md` — Full retry statistics
- AD-139: Gemini 3.1 Pro integration
- Session 68 log: Phase 3 (Subagent C: Photo Retry)
- Google Responsible AI policies: https://ai.google/responsibility/
