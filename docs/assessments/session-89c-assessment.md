# Session 89c Assessment

## Shipped
- [x] Act 1: Orient — Confirmed all 3 root causes (ID mismatch, no retry, no timestamp)
- [x] Act 2: Dual-key `_load_photo_locations()` for inbox IDs — Evidence: 2 new tests pass, pattern matches `_load_date_labels()`
- [x] Act 2: Rename "Run Face Analysis" to "Detect Faces" — Evidence: tests updated, button text changed
- [x] Act 3: Retry logic (2 retries, 5s/15s backoff) for 504/503/DEADLINE_EXCEEDED — Evidence: 3 new tests
- [x] Act 3: GEDCOM timeout increased 120s -> 180s
- [x] Act 3: Model badge shows analysis timestamp + prompt_version — Evidence: 2 new tests
- [x] Act 3: `prompt_version` stored in date_labels on re-analyze
- [x] Act 4: Pushed to Railway — Deploy ID 57541907, commit 2d060f8

## Deferred
- **Re-analyze Leon's Restaurant photo** — Deploy still BUILDING during session. User should click Re-analyze after deploy completes. Expected: location updates from Miami to Asheville with GEDCOM evidence.
- **Inline Leaflet map verification** — Could not verify in browser because deploy not yet live. Code and tests confirm dual-keying works. BACKLOG: verify after deploy.
- **"Detect Faces" button verification** — Same: deploy not yet live.

## Red Flags
- [LOW] Railway build taking unusually long (>10 min). Docker image export phase. May be one-time cache miss due to code changes touching many files.
- [LOW] 2 flaky xdist test failures (test_p0_fixes_49d, test_og_meta_tags) — pass in isolation, pre-existing xdist ordering issue. Not introduced by this session.
- [INFO] The inline Leaflet map rendering depends on the Location Estimate accordion section looking up lat/lng from `_load_photo_locations()`. The dual-keying fix ensures the SHA256 key exists. But the actual map div is only rendered when the page code finds lat/lng — verify this path works end-to-end after deploy.

## Test Results
- `make test-fast`: 1437+ passed (2 flaky xdist failures, pre-existing)
- `make test-ml`: 551 passed
- New tests: 7 total (2 dual-keying, 3 retry logic, 2 model badge timestamp)

## Next Session Should Verify
1. Deploy 57541907 completed successfully
2. Photo 3192877a90a174e9: inline Leaflet map renders (Miami coords initially)
3. "Detect Faces" button text visible (not "Run Face Analysis")
4. Click Re-analyze on Leon's Restaurant photo — verify Asheville result
5. Model badge shows "Gemini 3.1-pro" with timestamp after re-analyze
6. Photo 746dd11e5b4d86a1 still displays correctly (regression check)
