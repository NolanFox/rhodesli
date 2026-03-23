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
- **Fix:** IN PROGRESS
