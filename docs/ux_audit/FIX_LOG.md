# Fix Log — Session 53 Audit

## Fix 1: HTMX Indicator CSS Selector
**Route:** All pages with HTMX indicators
**Problem:** Custom CSS only had `.htmx-request .htmx-indicator` (descendant selector). When `hx-indicator="#id"` is used, HTMX adds `htmx-request` directly to the indicator element itself, requiring `.htmx-request.htmx-indicator` (combined selector).
**Root cause:** HTMX's built-in CSS handles both selectors, but the app's custom CSS override only had the descendant variant.
**Fix:** Added `.htmx-request.htmx-indicator` combined selector to the CSS.
**Verified:** Test passes, triage dashboard CSS includes both selectors.
**Regression risk:** Low — additive CSS change, doesn't affect existing behavior.

## Fix 2: Compare Upload Loading Indicator
**Route:** `/compare`, `/api/compare/upload`
**Problem:** Loading message said "a few seconds" but compare can take 60+ seconds on Railway CPU. No visual spinner.
**Root cause:** Optimistic messaging from initial implementation. No spinner animation.
**Fix:** Updated to "Analyzing your photo for faces... This may take up to a minute for group photos." Added animated SVG spinner.
**Verified:** Test confirms new message text present.
**Regression risk:** Low — text-only change to indicator content.

## Fix 3: Uploaded Photo Display
**Route:** `/api/compare/upload`
**Problem:** After uploading a photo and getting results, the user's uploaded photo was not visible. Only match results showed.
**Root cause:** Upload was saved to R2 but the URL was not included in the response HTML.
**Fix:** Added uploaded photo preview above results with face count badge. Uses `storage.get_upload_url()` to construct the R2 URL.
**Verified:** Code review confirms image element is in response.
**Regression risk:** Low — additive change to response HTML. Falls back gracefully if URL fails.

## Fix 4: Resize Target Optimization
**Route:** `/api/compare/upload`
**Problem:** Images were resized to max 1280px, but InsightFace detection runs at 640x640 internally. The extra resolution provided no quality benefit.
**Root cause:** Initial implementation used conservative resize target.
**Fix:** Reduced max dimension from 1280 to 1024. Balances quality with processing speed.
**Verified:** Code change in place. Actual performance improvement requires production testing.
**Regression risk:** Low — 1024px is well above InsightFace's internal 640x640 detection size.
