# Production Smoke Test — 2026-02-20

## Summary
- Total routes tested: 35
- Fully working: 33
- Partial/degraded: 0
- Broken: 0
- Minor issues: 2
- Auth-required (correctly blocked): 10

## Health Check
```json
{"status":"ok","identities":664,"photos":271,"processing_enabled":true,"ml_pipeline":"ready","supabase":"skipped"}
```

## Public Routes

| Route | HTTP | Time | Size | Images | Content | Status |
|-------|------|------|------|--------|---------|--------|
| `/` | 200 | 0.38s | 58KB | 10 | Real content | OK |
| `/timeline` | 200 | 0.88s | 443KB | 271 | All photos | OK |
| `/compare` | 200 | 0.29s | 36KB | 46 | Upload form | OK |
| `/people` | 200 | 0.16s | 38KB | 46 | Person links | OK |
| `/photos` | 200 | 0.63s | 294KB | 271 | Photo grid | OK |
| `/collections` | 200 | 0.29s | 19KB | 8 | 5 collections | OK |
| `/map` | 200 | 0.33s | 40KB | 1 | Map view | OK |
| `/tree` | 200 | 0.62s | 28KB | 0 | Tree structure | OK |
| `/connect` | 200 | 0.21s | 37KB | 0 | Connection UI | OK |
| `/estimate` | 200 | 0.20s | 22KB | 1 | Estimate page | OK |
| `/about` | 200 | 0.19s | 14KB | 0 | About content | OK |
| `/activity` | 200 | 0.26s | 6KB | 0 | 2 activities | OK |

## Detail Pages

| Route | HTTP | Time | Content | Status |
|-------|------|------|---------|--------|
| `/person/c93e5c13...` (Abraham Almaleh) | 200 | 0.27s | Name, 2 imgs, photo links | OK |
| `/photo/2c74818e...` | 200 | 0.27s | Photo, 5 face overlays, AI section | OK |
| `/collection/vida-capeluto-nyc-collection` | 200 | 0.64s | 108 imgs, photo links | OK |
| `/timeline?person=c93e5c13...` | 200 | 0.21s | Filtered timeline | OK |
| `/identify/c93e5c13...` | 200 | 0.32s | Identify page | OK |

## Auth-Protected Routes (all correctly 401)

| Route | HTTP | Status |
|-------|------|--------|
| `/admin/pending` | 401 | PASS |
| `/admin/proposals` | 401 | PASS |
| `/admin/review/birth-years` | 401 | PASS |
| `/admin/approvals` | 401 | PASS |
| `/admin/gedcom` | 401 | PASS |
| `/admin/audit` | 401 | PASS |
| `/admin/ml-dashboard` | 401 | PASS |
| `/upload` | 401 | PASS |
| `/admin/review-queue` | 401 | PASS |
| `/admin/export/identities` | 401 | PASS |

## R2 Image Verification

| Type | URL (truncated) | HTTP | Size | Status |
|------|-----------------|------|------|--------|
| Face crop | crops/inbox_52cbbbe7f308.jpg | 200 | 78KB | OK |
| Full photo | raw_photos/zeb_capuano_New_Lido_Opens.jpg | 200 | 1.8MB | OK |
| Thumbnail | raw_photos/Image%20001_compress.jpg | 200 | 1.7MB | OK |

## Content Analysis

- No broken images (src="" or src="None"): 0 across all pages
- No Python None values leaking into HTML attributes
- No admin-only forms visible to anonymous users
- All HTML entities correctly encoded (ampersands in URLs, collection names)
- Compare/Estimate upload forms visible to anonymous (by design — read-only operations)

## Minor Issues

1. **Not-found pages return 200 instead of 404**: `/person/{nonexistent}` and `/photo/{nonexistent}` return HTTP 200 with a "not found" message. Should return 404 for proper HTTP semantics.
2. **Duplicate activity entries**: Activity page shows 2 identical "Name suggestion approved" entries from 2026-02-13. May be actual data or a dedup issue.
