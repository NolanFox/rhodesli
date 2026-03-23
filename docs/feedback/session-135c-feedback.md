# Session 135c Feedback

Continuing from Session 135 (FB-012 was last).

## Items

### FB-013: Find Similar completely broken — perf_cache checks wrong embedding key
- **Severity:** P0
- **Context:** `_rebuild_global_matrix()` in perf_cache.py checked for `"embeddings"` key, but `load_face_embeddings()` returns `"mu"` (PFE format). Global matrix was empty — ALL identities returned "No similar identities."
- **Root cause:** Session 135b introduced perf_cache global matrix with wrong key name. Mock tests used `"embeddings"` key, masking production mismatch (Lesson 105/152).
- **Fix:** FIXED — check for both `"mu"` and `"embeddings"` keys. Commit f3abe93.

### FB-014: "Same community only" filter not applied on Load More
- **Severity:** P1
- **Context:** In Similar Identities panel, selecting "Same community only" filter correctly filters visible results. But clicking "Load More" / "See more" loads additional results WITHOUT the filter applied — cross-community results appear.
- **Root cause:** TBD — Load More likely doesn't pass the community filter param
- **Fix:** FIXED — commit 8444c8a

### FB-015: Speed-run shows wrong faces (cluster contamination) + community filter broken
- **Severity:** P1
- **Context:** First speed-run cluster at `/c/fox-family/admin/upload-review?mode=speed` shows faces that aren't the same person (bad clustering). Community filter also not working correctly.
- **Root cause:** TBD — may be cluster quality issue (data), or community scoping gap in speed-run suggestions. The `mu` vs `embeddings` fix (FB-013) may have exposed previously-hidden cross-community results.
- **Fix:** INVESTIGATING

### FB-016: Speed-Run purpose unclear — user doesn't understand when to use it vs Focus mode
- **Severity:** P2 (UX clarity)
- **Context:** User asks: "How am I supposed to use this? Was the main use case for uploading a 2nd or more collection?" and "I thought you were supposed to investigate the difference between each further." DD-018 documented the distinction but it's not communicated in the UI.
- **Root cause:** No in-app explanation of Speed-Run purpose. DD-018 exists but only as internal design doc.
- **Fix:** BACKLOG — DD-018-002 (add subtitle text)
