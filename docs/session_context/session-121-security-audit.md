# Session 121 Security Audit

**Date**: 2026-03-19
**Auditor**: Claude Opus 4.6 (automated)
**Scope**: All files changed in Session 121

---

## Files Reviewed

### 1. `app/admin_routes.py` — `/api/admin/ml-compare` endpoint

| Check | Result | Notes |
|-------|--------|-------|
| Admin auth guard | PASS | `_check_admin(sess)` at line 128, returns 401/403 before any processing |
| File upload handling | PASS | Temp file created with `delete=False`, cleaned up in `finally` block (line 173) via `pathlib.Path(tmp_path).unlink(missing_ok=True)` |
| Input validation | PASS | Checks for missing file field (returns 400), checks ML_SERVICE_URL configured (returns 503) |
| SQL injection | N/A | No database writes, no raw SQL |
| XSS | N/A | Returns JSON only, no HTML rendering |
| Error leak | LOW RISK | Exception `str(e)` returned in 502 response. Acceptable for admin-only endpoint; no stack traces exposed |

### 2. `app/admin_routes.py` — Approvals community filtering (UX-207)

| Check | Result | Notes |
|-------|--------|-------|
| Admin auth guard | PASS | Existing `_check_admin(sess)` on `/admin/pending` route unchanged |
| Community filter logic | PASS | Inclusive filter: shows uploads for current community + uploads with no community set. Cannot be used to access other communities' uploads |
| Data modification | PASS | Filtering is read-only; no writes changed |

### 3. `app/admin_routes.py` — source_url persistence (UX-212)

| Check | Result | Notes |
|-------|--------|-------|
| Input validation | LOW RISK | `source_url` from upload metadata stored as-is. It originates from the upload form (submitted by admin) and is stored via `PhotoRegistry.set_source_url()`. Since only admins can approve uploads, self-XSS is the only vector and is not a concern |
| SQL injection | N/A | Written through PhotoRegistry abstraction, not raw SQL |

### 4. `app/main.py` — Community badge logic (UX-208)

| Check | Result | Notes |
|-------|--------|-------|
| XSS | PASS | Badge text derived from community names in config, not user input |
| Data exposure | PASS | Shows community name on badges; this is public information already visible in URLs |

### 5. `app/page_routes.py` — Face overlay CSS changes (UX-211)

| Check | Result | Notes |
|-------|--------|-------|
| XSS | N/A | CSS-only changes (minimum button sizes), no user content |

### 6. `scripts/compare_ml_embeddings.py` — `--url` flag

| Check | Result | Notes |
|-------|--------|-------|
| Auth | PASS | Script is CLI-only (not web-exposed). Uses `requests.post()` to admin endpoint which requires auth cookies. Would need admin session cookies to authenticate |
| SSRF | N/A | URL is user-specified CLI argument, not derived from untrusted web input |

### 7. `docs/prds/053_face_compare_realtime.md`

| Check | Result | Notes |
|-------|--------|-------|
| N/A | PASS | Documentation only, no code |

---

## Summary

**Overall: CLEAN** — No security issues found. All new endpoints have proper admin auth guards. Temp files are cleaned up. No raw SQL, no user-controlled HTML rendering, no unvalidated redirects.
