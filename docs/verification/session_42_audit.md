# Session 42 Production Audit

Date: 2026-02-17
Environment: Local (auth disabled, STORAGE_MODE=local)

## Pre-Fix Route Health Check

| Route | Expected | Actual | Status |
|-------|----------|--------|--------|
| GET / | 200 | 200 | PASS |
| GET /photos | 200 | 200 | PASS |
| GET /collections | 200 | 200 | PASS |
| GET /collection/vida-capeluto-nyc-collection | 200 | 200 | PASS |
| GET /collection/jews-of-rhodes-family-memories-heritage | 200 | 200 | PASS |
| GET /people | 200 | 200 | PASS |
| GET /person/{confirmed_id} | 200 | 200 | PASS |
| GET /photo/{id} | 200 | 200 | PASS |
| GET /map | 200 | 200 | PASS |
| GET /connect | 200 | 200 | PASS |
| GET /tree | 200 | 200 | PASS |
| GET /timeline | 200 | 200 | PASS |
| GET /compare | 200 | 200 | PASS |
| GET /identify/{unresolved_id} | 200 | **500** | **FAIL** |
| GET /admin/gedcom | 200 | 200 | PASS |
| GET /admin/approvals | 200 | 200 | PASS |

### /identify 500 Root Cause

```
File "app/main.py", line 9619, in get
    for pid in photo_ids[:4]:
TypeError: 'set' object is not subscriptable
```

`photo_reg.get_photos_for_faces()` returns `set[str]`, but code slices it with `[:4]`.

## Pre-Fix Feature Verification

| Feature | Expected | Actual | Status |
|---------|----------|--------|--------|
| /connect renders D3 graph | Graph visible | D3 scripts + SVG present | PASS |
| /map renders Leaflet map with markers | Map + markers | Leaflet scripts present | PASS |
| /tree renders D3 family tree | Tree visible | D3 hierarchy scripts present | PASS |
| /timeline renders timeline | Timeline | 309 timeline elements found | PASS |
| Click identified face overlay → /person/{id} | Navigates | Links present | PASS |
| Photo carousel prev/next arrows | Navigate | "Photo 1 of 108" + next link | PASS |
| Collection link on photo page | Clickable | Correct href present | PASS |
| Person page action bar | Present | Timeline/Map/Tree/Connect all present | PASS |
| Person page comments section | Present | Form present | PASS |
| "Return to Inbox" hidden on /person/{id} | Hidden | Not found in HTML | PASS |
| Admin sidebar on admin pages | Present | Present | PASS |
| Admin sidebar NOT on public pages | Absent | Absent | PASS |
| "Tree" in nav on ALL public pages | Present | Missing on / landing page | **PARTIAL** |
| Admin elements on /photo/{id} | Hidden for anon | Visible (auth disabled=admin) | **FALSE POSITIVE** |
| /identify/{id} share button | Correct URL | Blocked by 500 | **BLOCKED** |
| Upload attribution | Present | Not implemented (no data field) | **MISSING** |
| "Add Photos" on collection pages | Present | Not implemented | **MISSING** |
| GEDCOM test data labeled | Warning shown | No warning | **PARTIAL** |
| Compare two-mode UX | Clear modes | Single-flow UI | **PARTIAL** |
| /collections counts | All collections | 8 collections with correct counts | PASS |

## Issues Found

1. **P0: /identify/{id} 500** — set not subscriptable
2. **P2: Landing page nav incomplete** — missing Map, Tree, Collections, Connect
3. **P3: GEDCOM test data not labeled** — no warning banner
4. **P3: Compare single-flow UX** — modes not clearly separated
5. **P3: No "Add Photos" on collection pages** — missing admin button
6. **DEFERRED: Upload attribution** — no `uploaded_by` field in data model

Note: Admin elements on /photo/{id} were a **false positive** — they are correctly
wrapped in `if is_admin else None` checks. When auth is disabled (local dev),
`is_admin=True` by design. In production with auth enabled, anonymous users see
`is_admin=False`.

---

## Post-Fix Verification

### All Routes Return 200

| Route | Status |
|-------|--------|
| GET / | 200 |
| GET /photos | 200 |
| GET /collections | 200 |
| GET /collection/vida-capeluto-nyc-collection | 200 |
| GET /collection/jews-of-rhodes-family-memories-heritage | 200 |
| GET /people | 200 |
| GET /person/{confirmed_id} | 200 |
| GET /photo/{id} | 200 |
| GET /map | 200 |
| GET /connect | 200 |
| GET /tree | 200 |
| GET /timeline | 200 |
| GET /compare | 200 |
| GET /identify/{unresolved_id} | **200** |
| GET /admin/gedcom | 200 |
| GET /admin/approvals | 200 |

### Fixes Applied

| Issue | Fix | Verified |
|-------|-----|----------|
| /identify 500 | `list()` wrap on `get_photos_for_faces()` result | 200 for both INBOX and SKIPPED identities |
| Landing page nav | Added all 8 public page links | All links present in HTML |
| GEDCOM test warning | Warning banner for files with "test" in name | `test-data-warning` div present |
| Compare two modes | Numbered sections "1. Search" + "2. Upload" | Both labels in HTML |
| Add Photos on collections | Admin-only button linking to /upload | Code added (visible in prod w/ admin auth) |
| Mock return type | `test_critical_routes.py` mock returns `set()` not `[]` | Tests pass |

### Test Results

| Suite | Result |
|-------|--------|
| App tests | 2209 passed, 3 skipped |
| ML tests | 306 passed |
| E2E tests | 48 passed, 7 skipped |
| Data integrity | 18/18 checks passed |
| **Total** | **2563 passed** |

### Share Button Verification

/identify/{id} share button confirmed working:
```html
<button data-action="share-photo"
  data-share-url="https://rhodesli.nolanandrewfox.com/identify/{id}"
  ...>Share to help identify</button>
```

The share URL correctly uses `/identify/` path, not `/photo/`.
