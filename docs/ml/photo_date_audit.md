# Photo Date Metadata Audit

**Date:** 2026-02-11 | **Photos audited:** 155

## 1. EXIF Date Metadata

An EXIF extraction system exists at `core/exif.py` (BE-013). It extracts `DateTimeOriginal`,
`DateTimeDigitized`, camera make/model, and GPS coordinates using PIL. It is integrated into the
ingestion pipeline (`core/ingest_inbox.py` lines 408-426) and runs automatically on upload.

**Results:** 12 of 155 photos (8%) have a `date_taken` field. However, **all 12 are scan-era
timestamps** (2012-2025), not original photograph dates. They record when the physical photo was
digitized, not when the picture was taken:

| Date Range       | Count | Source                      |
|------------------|-------|-----------------------------|
| 2019-11-29       | 10    | Nace Capeluto Tampa (phone scan session) |
| 2025-01-02       | 1     | Nace Capeluto Tampa         |
| 2012-05-22       | 1     | Find A Grave                |

Only 1 photo has camera metadata: `OLYMPUS IMAGING CORP. SZ-10` (the Find A Grave entry).
Zero photos have GPS coordinates. Zero photos have an `exif` blob stored in photo_index.json.

## 2. User-Assigned Dates

**Zero photos have user-assigned original dates.** The photo_index.json schema supports these
fields per photo entry: `path`, `face_ids`, `source`, `collection`, `source_url`, `width`,
`height`, `date_taken`, `camera`. There is no `era`, `decade`, or `approximate_year` field.

The admin UI (`POST /api/photo/{id}/metadata`) allows setting `date_taken` and `location`
manually, but this has not been used for any photo.

## 3. Collection Distribution

| Collection                              | Count | Undated | Notes                        |
|-----------------------------------------|-------|---------|------------------------------|
| Vida Capeluto NYC Collection            | 108   | 108     | Largest set, all undated      |
| Nace Capeluto Tampa Collection          | 14    | 3       | 11 have scan timestamps only  |
| Betty Capeluto Miami Collection         | 13    | 13      | All undated                   |
| Family Tree                             | 12    | 12      | All undated                   |
| Jews of Rhodes: Family Memories         | 4     | 4       | All undated                   |
| Newspapers.com                          | 3     | 3       | Publication dates recoverable |
| Find A Grave                            | 1     | 0       | Has scan date only            |
| **Total**                               | **155** | **143** |                            |

## 4. Assessment

### Current State

- **0 of 155 photos (0%) have a meaningful original date.** The 12 "dated" photos only have
  digitization timestamps from phone cameras, not the date the photograph was originally taken.
- **143 of 155 photos (92%) are completely undated** -- no date field at all.
- The archive covers roughly the 1920s-1970s based on the Sephardic Jewish heritage context,
  but no temporal metadata captures this.

### EXIF Feasibility

EXIF extraction is already built and wired into the ingestion pipeline. It works correctly for
new digital photos. However, it provides little value for this archive because:
- Scanned photos embed the **scan date**, not the original photo date.
- Pre-digital photos (1920s-1970s) have no embedded EXIF.
- The 3 Newspapers.com photos are web downloads with stripped EXIF.

### Silver-Labeling Feasibility (e.g., Gemini Vision)

A vision model could estimate approximate decades from visual cues (clothing, hairstyles,
photo quality, print style). Feasibility is **high** for this archive:
- **155 photos** is a manageable batch size (well under API rate limits).
- Sephardic Jewish family photos from Rhodes/NYC/Miami have strong era signals.
- Output schema: `{approximate_year: int, confidence: "high"|"medium"|"low", reasoning: str}`.
- Newspapers.com articles have printed dates that OCR or vision models can read directly.
- Cost estimate: ~$0.15-0.50 for the full set at current Gemini pricing.
- **Risk:** Violates Rule 4 ("No Generative AI -- forensic matching only") if used for
  anything beyond metadata enrichment. Date estimation is metadata, not identity matching,
  so this likely falls outside the rule's intent, but should be explicitly approved.

### Recommendations

1. **Add `approximate_year` and `era` fields** to the photo schema for human-assigned estimates.
2. **Backfill Newspapers.com dates** from source URLs (publication dates are in the URLs).
3. **Manual triage first:** The Vida Capeluto NYC collection (108 photos) likely spans a
   narrow range. A single admin session could bucket them into decades.
4. **Vision model labeling** as a second pass for photos where decade is ambiguous.
