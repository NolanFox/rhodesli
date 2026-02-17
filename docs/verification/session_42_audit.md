# Session 42 Production Audit

Date: 2026-02-17
Environment: Local (auth disabled, STORAGE_MODE=local)

## Route Health Check

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

## Feature Verification

| Feature | Expected | Actual | Status |
|---------|----------|--------|--------|
| /connect renders D3 graph | Graph visible | D3 scripts + SVG container present | PASS |
| /map renders Leaflet map with markers | Map + markers | Leaflet scripts + container present | PASS |
| /tree renders D3 family tree | Tree visible | D3 hierarchy scripts present | PASS |
| /timeline renders timeline | Timeline | 309 timeline elements found | PASS |
| Click identified face overlay → /person/{id} | Navigates | Links present (href="/person/{id}") | PASS |
| Click unidentified face overlay → /identify/{id} | Navigates | Not tested (would need unidentified faces on photos) | N/A |
| Photo carousel prev/next arrows work | Navigate photos | "Photo 1 of 108" + next link present | PASS |
| Collection link on photo page → collection | Clickable | href="/collection/vida-capeluto-nyc-collection" | PASS |
| Person page action bar (Timeline/Map/Tree) | Present | All 4 links (Timeline/Map/Tree/Connect) present | PASS |
| Person page comments section | Present + submittable | Comments section with form present | PASS |
| "Return to Inbox" hidden on /person/{id} | Hidden | Not found in HTML | PASS |
| Admin sidebar on admin pages | Present | 8 sidebar references found | PASS |
| Admin sidebar NOT on public pages | Absent | 0 sidebar references on /photos | PASS |
| "Tree" in nav on ALL public pages | Present everywhere | Present on /photos, /people, /timeline, /map, /connect, /compare. **Missing on /** | **PARTIAL** |
| Admin elements hidden on public /photo/{id} | Hidden | **"Admin: Add a back image" + "Front orientation" visible** | **FAIL** |
| /identify/{id} share copies identify URL | Correct URL | Can't test — page 500s | **BLOCKED** |
| Photo uploader attribution | "Uploaded by X" | Not implemented | **MISSING** |
| "Add Photos" button on collection pages | Present | Not implemented | **MISSING** |
| GEDCOM test data labeled as test | Warning shown | File name shown but no explicit warning | **PARTIAL** |
| Compare shows two clear modes | Clear UX | Single mode "Select a Person" + "Or Upload" subsection | **PARTIAL** |
| /collections shows all with counts | All collections | 8 collections: 118, 108, 14, 13, 12, 3, 2, 1 photos | PASS |

## Issues to Fix (Priority Order)

### P0: Route 500 Errors
1. **`/identify/{id}` 500** — set not subscriptable on line 9619

### P1: Security/Privacy
2. **Admin tools visible to anonymous on /photo/{id}** — "Admin: Add a back image" + "Front orientation" exposed

### P2: Navigation
3. **Landing page (/) missing full nav** — only /about, /compare, /timeline shown (no /photos, /people, /map, /connect, /tree)

### P3: Missing Features (from Session 40 feedback)
4. Upload attribution on photo page (FB-40-22)
5. "Add Photos" button on collection pages (FB-40-23)
6. GEDCOM test data warning (FB-40-11)
7. Compare page two-mode UX (FB-40-13)
