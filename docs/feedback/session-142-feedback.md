# Session 142 Feedback

### FB-001: Similar Identities links go to review grid instead of person page
- **Severity:** P1
- **Context:** Clicking a person name/thumbnail in the Similar Identities panel on a person page goes to `/?section=to_review&view=browse#identity-{uuid}` instead of `/c/{community}/person/{uuid}`. The review grid doesn't scroll to or highlight the card.
- **Root cause:** `app/components/cards.py` neighbor_card() used `_section_for_state()` to build review grid URLs with hash anchors. Should use person page URL directly.
- **Fix:** FIXED — Changed thumbnail href, name href, and removed hyperscript scroll-to-card logic. Now links to `/person/{uuid}`.
- **Commit:** e953ba6

### FB-002: "View Photo" button in Compare modal silently fails
- **Severity:** P1
- **Context:** In Compare Faces modal (Photos view), clicking "View Photo" does nothing. The button uses `hx_get="/photo/{id}/partial"` but is missing the community prefix — should be `/c/fox-family/photo/{id}/partial`.
- **Root cause:** `app/compare_routes.py` lines 5887/5900 — `hx_get` URL missing `{nav_prefix}` even though `nav_prefix` is available in scope.
- **Fix:** FIXED — Added `{nav_prefix}` to both View Photo button hx_get URLs.
- **Commit:** e953ba6

### FB-003: Multi-merge from Focus mode fails after first merge
- **Severity:** P1
- **Context:** From Focus mode, merging more than one suggestion at a time — only the first succeeds, the rest fail silently. The page shows empty Focus mode after the error.
- **Root cause:** Second merge request finds the source identity already merged (from the first merge's side effects), triggers `_check_merged_identity` guard which returns `HttpHeader("HX-Redirect")`. In Focus mode, this redirect breaks the page. Also, no error logging for merge failures.
- **Fix:** FIXED — (1) When merge guard detects already-merged identity in Focus mode, return a toast + OOB delete instead of redirect. (2) Added `logger.warning()` for all merge guard hits and merge failures. (3) Added `logger.exception()` for registry load failures.
- **Commit:** e953ba6

### FB-004: "Confirm as [Name]" only confirms, does not merge
- **Severity:** P0
- **Context:** In New Matches, clicking "Confirm as Leona Fox Smilg" only changes state to CONFIRMED — it doesn't merge with the named target. User expects confirm+merge.
- **Root cause:** Confirm endpoint had no merge_target_id parameter. Button label showed merge intent but only triggered state change.
- **Fix:** FIXED — Added merge_target_id param to both /confirm/{id} and /inbox/{id}/confirm. Button now passes best match target_id. Full audit trail + logging.
- **Commit:** efa43f5

### FB-005: Merge from Similar Identities panel has no feedback
- **Severity:** P2
- **Context:** After merging from Similar Identities on person page, the merged card disappears but no toast appears. Panel stays open with stale content.
- **Root cause:** OOB delete works but toast targeting may miss if toast-container isn't in HTMX swap target chain.
- **Fix:** Improved via FB-003 merge guard + FB-006 toast improvements.
- **Commit:** efa43f5

### FB-006: Bulk merge "already merged" shown as errors
- **Severity:** P1
- **Context:** Bulk merge from Focus mode shows "4 skipped: ... (already merged)" as yellow warning. These are expected stale references, not real failures.
- **Root cause:** Toast message treated "already merged" same as real failures like co_occurrence.
- **Fix:** FIXED — Separated "already merged" from real failures in toast. Already-merged shown as info, not warning.
- **Commit:** efa43f5

### FB-007: Similar Identities shows already-merged identities
- **Severity:** P1
- **Context:** Betty Capeluto Fox's Similar panel showed 5 identities but 4 were already merged — attempting bulk merge failed for all but one.
- **Root cause:** Neighbors endpoint returned merged identities from stale embedding matrix.
- **Fix:** FIXED — Added merged_into filter to neighbors endpoint + increased fetch limit from 20 to 100 to compensate.
- **Commit:** efa43f5, 7a32cf7

### FB-008: Esther Burd Fox shows "No similar identities"
- **Severity:** P1
- **Context:** 142-face CONFIRMED identity shows empty Similar Identities. Should have unmatched candidates.
- **Root cause:** merged_into filter (FB-007) removed all 20 nearest neighbors. 51% of identities are merged, and Esther's nearest matches were all absorbed.
- **Fix:** FIXED — Increased base fetch limit from 20 to 100 so filtering doesn't empty the list.
- **Commit:** 7a32cf7

### FB-009: Speed Loop not suggesting Albert Fox for clearly matching face
- **Severity:** P2
- **Context:** In Speed Loop tagging mode, face clearly resembling Albert Fox shows no suggestion. User must type name manually.
- **Root cause:** Speed Loop "Type name to tag" is a manual search input — it doesn't auto-suggest from proposals or nearest neighbors. This is a feature gap, not a bug in the current code. Proposals may be stale or this face may lack a cross-batch match proposal.
- **Fix:** DEFERRED — Requires proposal pipeline re-run or auto-suggestion feature. Logged for next session.
