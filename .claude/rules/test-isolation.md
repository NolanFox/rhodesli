---
paths:
  - "tests/**"
  - "tests/conftest.py"
---

# Test Data Isolation Rules

## CRITICAL: Tests Must Never Write to Real Data Files

Any test that calls a route handler (via TestClient POST) that modifies data
MUST mock both the load and save functions:

```python
# REQUIRED for any test that POSTs to data-modifying routes
with patch("app.main.load_registry", return_value=mock_reg), \
     patch("app.main.save_registry"):
    response = client.post("/api/identity/{id}/rename", ...)

with patch("app.main.load_photo_registry", return_value=mock_reg), \
     patch("app.main.save_photo_registry"):
    response = client.post("/api/photos/bulk-update-source", ...)
```

## Rules

1. Tests must NEVER call `load_registry()` or `load_photo_registry()` to get real data for POST requests
2. Tests must NEVER let `save_registry()` or `save_photo_registry()` write to disk
3. Use `MagicMock()` or `PhotoRegistry()` with test data, not production data
4. GET-only tests that read real data are acceptable (they don't corrupt)
5. Tests using `tmp_path` for file I/O are safe

## Known Contamination History

- Session 12: `test_bulk_photos.py` wrote "Test Collection" to 2 real photos
- Session 12: `test_regression.py` renamed a real identity back and forth
- Session 12: `test_metadata.py` wrote metadata to a real identity

## Verification

Run `python scripts/check_data_integrity.py` after any test changes.
Run `md5 data/*.json` before and after `pytest` to verify no writes.

## Post-Fix Production Verification

When fixing production bugs, verification MUST include fetching rendered HTML from the live site:
```bash
curl -s https://rhodesli.nolanandrewfox.com/[page] | grep [expected]
```
Checking local JSON files or API responses is NOT sufficient verification.
