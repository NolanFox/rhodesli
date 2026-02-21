# PRD: Compare/Estimate Upload Pipeline Audit

**Session:** 49E Phase 5
**Date:** 2026-02-21
**Status:** COMPLETE (existing feature, messaging fix only)

## Problem Statement

Session 49D changed the compare page messaging to say "Your photo is analyzed for matching but not stored in the archive" (UX-044/052). This was believed to describe actual behavior, but the investigation found it to be **incorrect** — photos ARE stored.

## Investigation Findings

### Compare Upload Pipeline (already implemented)
1. User uploads photo to `/api/compare/upload`
2. Photo saved to R2: `uploads/compare/{upload_id}.jpg` via `upload_bytes_to_r2()`
3. Metadata saved to R2: `uploads/compare/{upload_id}_meta.json`
4. Face detection + comparison runs
5. Results displayed with "Contribute to Archive" CTA (logged-in users)
6. CTA calls `POST /api/compare/contribute` → creates `pending_uploads.json` entry
7. Admin reviews on `/admin/pending`

### Estimate Upload Pipeline (already implemented)
1. User uploads photo to `/api/estimate/upload`
2. Photo saved to R2: `uploads/estimate/{upload_id}.jpg` via `upload_bytes_to_r2()`
3. Date estimation runs (Gemini if available, fallback to face-based)
4. Results displayed

### What Was Incorrect
- Line 13590: `"Your photo is analyzed for matching but not stored in the archive."`
- Photos ARE stored in R2 (in uploads/ prefix, not the main archive)
- Logged-in users can contribute via CTA → admin moderation queue

## Fix

Update messaging to accurately reflect the two-tier behavior:
- Photos are uploaded for analysis
- Logged-in users can contribute them to the archive via admin review
- The "not stored" text is misleading — remove it

## Out of Scope
- No new pipeline work needed — everything already works
- No estimate contribute flow (estimate is informational only)
