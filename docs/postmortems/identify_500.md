# Postmortem: /identify/{id} 500 Error

**Date discovered:** 2026-02-17 (Session 42 audit)
**Severity:** P0 — all /identify pages broken
**Impact:** Every shareable identification link returned 500

## Root Cause

`core/photo_registry.py::get_photos_for_faces()` returns `set[str]`, but
`app/main.py` line 9619 tried to slice it with `[:4]`:

```python
photo_ids = photo_reg.get_photos_for_faces(face_id_strings)
# ...
for pid in photo_ids[:4]:  # TypeError: 'set' object is not subscriptable
```

## Fix

Wrapped in `list()` on assignment:

```python
photo_ids = list(photo_reg.get_photos_for_faces(face_id_strings))
```

## Why It Wasn't Caught

- No test existed for GET /identify/{id} with a real identity
- The /identify route was added in Session 40 but only tested with mocks
- The `get_photos_for_faces()` return type annotation (`set[str]`) was correct,
  but the caller didn't account for it

## Prevention

- Added `test_identify_page_loads` test
- Session 42 audit process catches all 500s via systematic route checking
