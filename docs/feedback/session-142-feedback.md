# Session 142 Feedback

### FB-001: Similar Identities links go to review grid instead of person page
- **Severity:** P1
- **Context:** Clicking a person name/thumbnail in the Similar Identities panel on a person page goes to `/?section=to_review&view=browse#identity-{uuid}` instead of `/c/{community}/person/{uuid}`. The review grid doesn't scroll to or highlight the card.
- **Root cause:** `app/components/cards.py` neighbor_card() used `_section_for_state()` to build review grid URLs with hash anchors. Should use person page URL directly.
- **Fix:** FIXED — Changed thumbnail href, name href, and removed hyperscript scroll-to-card logic. Now links to `/person/{uuid}`.
- **Commit:** pending

### FB-002: "View Photo" button in Compare modal silently fails
- **Severity:** P1
- **Context:** In Compare Faces modal (Photos view), clicking "View Photo" does nothing. The button uses `hx_get="/photo/{id}/partial"` but is missing the community prefix — should be `/c/fox-family/photo/{id}/partial`.
- **Root cause:** `app/compare_routes.py` lines 5887/5900 — `hx_get` URL missing `{nav_prefix}` even though `nav_prefix` is available in scope.
- **Fix:** FIXED — Added `{nav_prefix}` to both View Photo button hx_get URLs.
- **Commit:** pending

### FB-003: Multi-merge from Focus mode fails after first merge
- **Severity:** P1
- **Context:** From Focus mode, merging more than one suggestion at a time — only the first succeeds, the rest fail silently. The page shows empty Focus mode after the error.
- **Root cause:** Second merge request finds the source identity already merged (from the first merge's side effects), triggers `_check_merged_identity` guard which returns `HttpHeader("HX-Redirect")`. In Focus mode, this redirect breaks the page. Also, no error logging for merge failures.
- **Fix:** FIXED — (1) When merge guard detects already-merged identity in Focus mode, return a toast + OOB delete instead of redirect. (2) Added `logger.warning()` for all merge guard hits and merge failures. (3) Added `logger.exception()` for registry load failures.
- **Commit:** pending
