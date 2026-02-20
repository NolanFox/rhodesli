# Fix Log — Production Audit Sessions

## Session 54 Fixes

### Fix 5: Compare Upload 640px ML Resize (UX-003)
**Route:** `/api/compare/upload`
**Problem:** Images resized to 1024px max, but InsightFace runs detection at 640x640 internally. Wasted compute above 640px.
**Root cause:** Session 53 reduced from 1280 to 1024 conservatively. The correct target is 640px matching InsightFace det_size.
**Fix:** Split into two paths: original image saved to R2 for display, separate 640px copy for ML processing. `_ML_MAX_DIM = 640`.
**Verified:** Tests pass. Source code assertions confirm split-path and 640px target.
**Regression risk:** Low — display quality unchanged (original to R2). ML quality unchanged (640px matches InsightFace internal resolution).

### Fix 6: HTTP 404 for Non-Existent Resources (UX-005)
**Route:** `/person/{id}`, `/photo/{id}`, `/identify/{id}`, `/identify/{a}/match/{b}`
**Problem:** Non-existent person/photo pages returned HTTP 200 with friendly "not found" HTML. SEO and link-sharing tools expect 404 for missing resources.
**Root cause:** FastHTML tuple returns default to 200. Needed explicit HTMLResponse with status_code=404.
**Fix:** Wrapped 404 page HTML in `HTMLResponse(..., status_code=404)`. Same friendly visual design preserved.
**Verified:** 6 tests updated to expect 404. All 2481 tests pass.
**Regression risk:** Low — only affects non-existent resources. Friendly HTML unchanged.

### Fix 7: Estimate Loading Indicator Enhancement (UX-014)
**Route:** `/estimate` upload zone
**Problem:** Loading indicator just said "Analyzing photo..." with simple pulse animation. No spinner, no duration warning.
**Root cause:** Estimate indicator not updated when compare indicator was enhanced in Session 53.
**Fix:** Added SVG spinner (same as compare), updated message to "Analyzing your photo for date clues...", added secondary text "This may take a moment for group photos."
**Verified:** Source code inspection confirms new spinner and messages.
**Regression risk:** Low — additive change to indicator content.

## Session 53 Fixes

### Fix 1: HTMX Indicator CSS Selector
**Route:** All pages with HTMX indicators
**Problem:** Custom CSS only had `.htmx-request .htmx-indicator` (descendant selector). When `hx-indicator="#id"` is used, HTMX adds `htmx-request` directly to the indicator element itself, requiring `.htmx-request.htmx-indicator` (combined selector).
**Root cause:** HTMX's built-in CSS handles both selectors, but the app's custom CSS override only had the descendant variant.
**Fix:** Added `.htmx-request.htmx-indicator` combined selector to the CSS.
**Verified:** Test passes, triage dashboard CSS includes both selectors.
**Regression risk:** Low — additive CSS change, doesn't affect existing behavior.

### Fix 2: Compare Upload Loading Indicator
**Route:** `/compare`, `/api/compare/upload`
**Problem:** Loading message said "a few seconds" but compare can take 60+ seconds on Railway CPU. No visual spinner.
**Root cause:** Optimistic messaging from initial implementation. No spinner animation.
**Fix:** Updated to "Analyzing your photo for faces... This may take up to a minute for group photos." Added animated SVG spinner.
**Verified:** Test confirms new message text present.
**Regression risk:** Low — text-only change to indicator content.

### Fix 3: Uploaded Photo Display
**Route:** `/api/compare/upload`
**Problem:** After uploading a photo and getting results, the user's uploaded photo was not visible. Only match results showed.
**Root cause:** Upload was saved to R2 but the URL was not included in the response HTML.
**Fix:** Added uploaded photo preview above results with face count badge. Uses `storage.get_upload_url()` to construct the R2 URL.
**Verified:** Code review confirms image element is in response.
**Regression risk:** Low — additive change to response HTML. Falls back gracefully if URL fails.

### Fix 4: Resize Target Optimization
**Route:** `/api/compare/upload`
**Problem:** Images were resized to max 1280px, but InsightFace detection runs at 640x640 internally.
**Root cause:** Initial implementation used conservative resize target.
**Fix:** Reduced max dimension from 1280 to 1024 (then further to 640 in Session 54).
**Verified:** Code change in place.
**Regression risk:** Low.
