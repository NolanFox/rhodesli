# Session 89c Context — Re-analyze Failures + Photo Location ID Mismatch

**Predecessor**: Session 89b (location persistence + model label + GEDCOM reasoning)
**Origin**: User testing re-analyze on photo 3192877a90a174e9 (Leon's Restaurant, Asheville)

## User Feedback (2026-03-05)

### Issue 1: Re-analyze fails with "Gemini analysis failed"
- User clicked Re-analyze on photo 3192877a90a174e9 (Leon's Restaurant)
- Railway logs show: `504 DEADLINE_EXCEEDED` from `gemini-3.1-pro-preview:generateContent`
- Error: "Deadline expired before operation could complete."
- The Gemini API timed out server-side (not our client timeout)
- Current timeout: 120s when GEDCOM context present, 30s otherwise
- Supabase `gemini_api_calls` row was logged with status=error

### Issue 2: No embedded map on photo page (but "See on Map" works)
**Root cause: Photo ID mismatch in photo_locations.json**

The photo page URL uses SHA256-based ID: `3192877a90a174e9`
But `photo_locations.json` stores the entry under inbox-style ID: `inbox_staged-20260210-182610_5_757557421.130308`

- `_load_date_labels()` (line 883) handles this with dual-keying — computes SHA256 from filename and stores under both IDs
- `_load_photo_locations()` (line 16687) does NOT dual-key — returns raw dict from JSON
- Result: `locations.get("3192877a90a174e9")` returns None → no inline Leaflet map rendered
- The "See on Map" button works because it passes people UUIDs to `/map?people=...` which uses a different lookup path

**This same bug affects ALL inbox-uploaded photos** — any photo with an `inbox_*` ID in photo_locations.json will have no inline map.

### Issue 3: Model label still shows "Gemini 3-flash"
- Since re-analyze failed (504), the old batch analysis results are still displayed
- The batch was run with Gemini 3-flash, so that label is shown
- After a successful re-analyze, it should update to "Gemini 3.1-pro"
- **Also needed**: timestamp of when analysis was run, visible in UI

### Issue 4: No analysis timestamp visible in UI
- `reanalyzed_at` is stored in JSON but never displayed
- User wants to know when the analysis was run and what model was used
- Important for admin workflow: "Is this result from the old batch or my recent re-run?"

### Issue 5: Prompt reconstruction for experimentation
- User wants ability to reconstruct the exact prompt used for any analysis
- Currently `gemini_config` JSONB stores parameters but not the full prompt text
- Need enough stored metadata to recreate the prompt deterministically

### Issue 6: "Run Face Analysis" naming confusion
- At bottom of photo page, "Run Face Analysis" sounds like it could be the re-analyze button
- Actually runs InsightFace face detection, not Gemini photo analysis
- Rename for clarity

## Historical Context: Leon's Restaurant Photo

- **Photo**: 3192877a90a174e9 = 757557421.130308.jpg
- **People identified**: Victor Capelluto + Victoria Capuano Capeluto
- **Location**: Leon's Restaurant, Asheville, NC (NOT Miami or NYC)
- **Date**: ~1938 or 1940 (Victor visited from Japan in 1938 and 1940)
- **GEDCOM data**: Victor (Haim) Capelluto arrived SF June 1938 "in transit to Asheville, N.C." per ship manifest. Leon opened restaurant in Asheville 1937.
- **Current AI result**: "circa 1944, NYC or Miami" — date roughly right, location wrong
- **Expected after re-analyze**: "Asheville, North Carolina" with GEDCOM biographical evidence

## Technical Root Causes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Re-analyze 504 | Gemini Pro server-side timeout | Add retry logic (1-2 retries with backoff) |
| No inline map | `_load_photo_locations()` lacks dual-keying for inbox IDs | Add SHA256 cross-reference like `_load_date_labels()` |
| Old model label | Re-analyze never succeeded (504) | Fix timeout + retry → label updates on success |
| No timestamp in UI | `reanalyzed_at` stored but not rendered | Display in model badge area |
| Prompt not stored | Only config params saved, not full text | Store prompt hash + version for reconstruction |
| "Run Face Analysis" | Confusing naming | Rename to "Run Face Detection" or "Detect Faces" |

## Key Code Locations

| File | Lines | What |
|------|-------|------|
| `app/main.py:883-934` | `_load_date_labels()` | Has dual-keying (works) |
| `app/main.py:16687-16704` | `_load_photo_locations()` | Missing dual-keying (broken) |
| `app/main.py:1719-1736` | Inline Leaflet map rendering | Only renders when lat/lng found |
| `app/main.py:18714-18722` | Model badge display | Shows "Analyzed with {model}" |
| `app/estimate_routes.py:490-493` | Gemini client timeout | 120s GEDCOM, 30s default |
| `app/estimate_routes.py:1096-1262` | Re-analyze endpoint | Full handler |
| `app/estimate_routes.py:457-595` | `_call_gemini_date_estimate()` | Gemini call + error handling |
| `data/photo_locations.json:2277` | Leon's Restaurant entry | Keyed by inbox ID, has Miami coords |

## Prior Art (Dual-Keying Pattern)

From `_load_date_labels()` (line 920-930):
```python
if pid.startswith("inbox_"):
    path = photo_registry.get_photo_path(pid)
    if path:
        fname = Path(path).name
        sha_id = hashlib.sha256(fname.encode("utf-8")).hexdigest()[:16]
        _date_labels_cache[sha_id] = label
```

The same pattern needs to be applied to `_load_photo_locations()`.

## Verification Targets

1. Photo 3192877a90a174e9: inline Leaflet map should render with Miami coords (before re-analyze)
2. Re-analyze should succeed (with retry) and update to Asheville
3. After re-analyze: model badge shows "Gemini 3.1-pro", timestamp shown
4. The Leon's Restaurant photo is the primary test case
5. Secondary: photo 746dd11e5b4d86a1 (Victoria in Asheville) should still work
