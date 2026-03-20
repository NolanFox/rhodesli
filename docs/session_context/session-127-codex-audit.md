# Session 127 Codex Audit Results

Audited all 28 Python files in `app/`. Read-only analysis of security, accessibility, and dead code.

## Security Findings

### P0 (Critical)

1. **Pickle deserialization of user-controlled paths** — `compare_routes.py:4366`, `compare_routes.py:3277`, `match_facecompare_routes.py:1626`. The `upload_id` parameter comes from URL query params (user-controlled) and is interpolated directly into a file path: `Path("uploads/compare") / f"{upload_id}_faces.pkl"`. Then `pickle.loads()` is called on the file contents. An attacker could craft `upload_id=../../some/other/file` to load an arbitrary pickle file, achieving **remote code execution**. The `upload_id` is NOT validated as a UUID before use.
   - Files: `app/compare_routes.py` (lines 3277, 4366), `app/match_facecompare_routes.py` (line 1626)
   - Fix: Validate `upload_id` matches `^[a-f0-9-]+$` before constructing paths. Consider replacing pickle with JSON for face data serialization.

2. **Session secret defaults to hardcoded value** — `app/auth.py:19`: `SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-in-production")`. If SESSION_SECRET is not set in production, all session cookies are signed with a known secret, allowing session forgery and admin impersonation. This is likely set in production, but the fallback is dangerous.
   - Fix: Raise an error at startup if SESSION_SECRET is the default value and RAILWAY_ENVIRONMENT is set.

### P1 (High)

3. **No CSRF protection on any POST routes** — Zero CSRF tokens found in the entire codebase. All POST routes rely solely on session cookies. An attacker could craft a page that submits forms to admin-only endpoints (merge identities, approve uploads, delete data). The session cookie will be sent automatically by the browser. FastHTML/Starlette does not provide CSRF middleware by default.
   - Fix: Add CSRF token middleware or use SameSite=Strict cookies (partial mitigation). At minimum, check Origin/Referer headers on state-changing POST requests.

4. **Multiple public POST routes that write data without authentication**:
   - `/api/compare/upload` (compare_routes.py:1561) — Uploads and persists photos to the archive. Any anonymous user can upload files that get saved to R2 and processed.
   - `/api/compare/upload-multiple` (compare_routes.py:3004) — Same, up to 5 photos per request.
   - `/api/compare/pair/upload` (compare_routes.py:4170) — Face detection on uploaded photo, no auth.
   - `/api/facecompare/upload` (match_facecompare_routes.py:1312) — Face detection on upload, no auth.
   - `/api/upload/stream` (page_routes.py:9654) — SSE upload processing, no auth.
   - `/api/estimate/upload` (estimate_routes.py:680) — Photo upload for date estimation, no auth.
   - These are intentionally public tools, but they accept file uploads with no rate limiting, enabling storage abuse and potential DoS via large upload volumes. The compare upload routes persist photos to R2 (permanent storage).
   - Fix: Add rate limiting (IP-based) to all public upload endpoints. Consider a file count/size daily cap per IP.

5. **`/api/compare/result/{result_id}/respond`** (compare_routes.py:3838) — Writes to comparison results JSON with no authentication and no rate limiting. Any anonymous user can flood results with responses.
   - Fix: Add rate limiting similar to the comment and match-respond endpoints.

6. **Duplicate route definition** — Both `browse_routes.py:1520` and `identity_routes.py:398` define `POST /api/identity/{identity_id}/reject-match/{neighbor_id}`. Both have auth checks but use slightly different patterns. The one that "wins" depends on import order. This creates unpredictable behavior.
   - Fix: Remove the duplicate in `browse_routes.py`.

### P2 (Medium)

7. **`exec_sql` RPC endpoint** (admin_routes.py:201) — The `/api/admin/run-migrations` endpoint calls `sb.rpc("exec_sql", {"query": sql})` with hardcoded SQL. Currently safe because the SQL is hardcoded, but the existence of an `exec_sql` Supabase function that accepts arbitrary SQL is a latent risk. If any other code path calls it with user input, it becomes SQL injection.
   - Fix: Use specific migration functions instead of a generic `exec_sql` RPC. Or remove the `exec_sql` function from Supabase and run migrations via the Supabase dashboard.

8. **Upload filename sanitization is incomplete** — `upload_routes.py:659`: `safe_filename = f.filename.replace(" ", "_").replace("/", "_")`. This only replaces spaces and forward slashes. Does not handle `..`, backslashes, null bytes, or other path traversal characters. On some systems, `../` after replacing `/` with `_` would still leave `..` which could be problematic with certain Path join behaviors.
   - Fix: Use `pathlib.PurePosixPath(filename).name` or a whitelist regex to strip everything except alphanumeric, hyphens, underscores, and dots.

9. **Gemini API key exposed in client-side error messages** — `estimate_routes.py` and `photo_routes.py` check for `os.getenv("GEMINI_API_KEY")` and return error messages about its absence, but the key itself is never exposed. However, the pattern of checking in request handlers (not at startup) means a misconfigured production deploy will expose "API key not configured" errors to public users, revealing infrastructure details.

10. **`ML_SERVICE_TOKEN` defaults to `"dev-token"`** — `compare_routes.py:5906`, `admin_routes.py:57`. If `ML_SERVICE_TOKEN` env var is not set, ML service auth uses a hardcoded token.
    - Fix: Fail loudly if ML_SERVICE_URL is set but ML_SERVICE_TOKEN is the default.

## Accessibility Findings

### Quick Wins (< 5 min each)

1. **~18 images missing `alt` text** — 148 `Img()` calls but only ~130 have `alt=` attributes. Face crop images and thumbnails in compare results, cluster review cards, and discovery panels lack alt text. Screen readers will read the image URL instead.
   - Fix: Add `alt=f"Face crop of {name}"` or `alt="Face thumbnail"` to all Img() calls.

2. **~300+ buttons missing `aria-label`** — 340 `Button()` calls across the app, but only 34 total `aria-label` or `role=` attributes. Icon-only buttons (reject, skip, merge, compare) have no accessible names. Examples: X close buttons on modals, arrow navigation, action buttons with only SVG icons.
   - Fix: Add `aria_label="Close"`, `aria_label="Reject match"`, etc. to icon-only buttons.

3. **Only 1 `tabindex` in entire app** — Keyboard users cannot navigate to most interactive elements. Modals, dropdowns, and action panels are mouse-only.
   - Fix: Add `tabindex="0"` to custom interactive elements. Ensure modal focus trapping.

4. **No `<label>` for many form inputs** — 180 `Input()`/`Textarea()`/`Select()` elements but only 73 `Label()` elements. Search inputs, filter inputs, name inputs in speed-run mode, and date correction fields lack associated labels.
   - Fix: Add `Label()` or `aria_label=` to all form inputs. Use `htmlFor` to associate labels with inputs.

5. **No skip-to-content link** — No mechanism for keyboard users to bypass the navigation bar (which appears on every page with 5-8 links).
   - Fix: Add a visually hidden "Skip to main content" link as the first focusable element.

### Needs Design

6. **Color contrast on slate backgrounds** — 371 occurrences of `text-slate-300`/`text-slate-400`/`text-slate-500` on `bg-slate-800`/`bg-slate-900` backgrounds. Slate-500 on slate-900 has a contrast ratio of approximately 4.5:1, which barely meets WCAG AA for normal text. Slate-400 on slate-800 may fail for smaller text sizes.
   - Fix: Audit with a contrast checker. Consider using slate-300 minimum for body text on dark backgrounds.

7. **Focus indicators not visible** — No custom focus styles defined. The browser default focus ring may be invisible on the dark slate backgrounds.
   - Fix: Add `focus:ring-2 focus:ring-indigo-400 focus:outline-none` to interactive elements.

8. **Modals lack focus trapping** — 424 modal/overlay references but keyboard escape handling (56 occurrences) covers only a subset. Users can tab out of open modals into background content.
   - Fix: Use `role="dialog"`, `aria-modal="true"`, and JavaScript focus trapping for all modals.

9. **No `<main>` landmark on most pages** — Only the tools hub and a few pages use `<Main>`. Screen readers cannot identify the primary content region on most pages.

## Dead Code

1. **`compare_v2_routes.py`** — Entire file is stub endpoints returning 501 Not Implemented. Three routes (`/api/v2/compare/status`, `/api/v2/compare/embed`, `/api/v2/compare`) that do nothing. Not linked from any navigation or UI.
   - Fix: Remove file or add a note about when it will be implemented.

2. **`app/audit_notes.md`** and **`app/ui_spec.md`** — Non-code files in the app directory. `audit_notes.md` (2971 bytes) and `ui_spec.md` (5828 bytes) are documentation that belong in `docs/`, not `app/`.
   - Fix: Move to `docs/` or remove if superseded.

3. **Duplicate route: `/api/identity/{identity_id}/reject-match/{neighbor_id}`** — Defined in both `browse_routes.py:1519` and `identity_routes.py:398`. One will shadow the other.
   - Fix: Remove the duplicate.

4. **Duplicate route: `/api/photo/{photo_id}/correct-date`** — Defined in both `photo_routes.py:141` and `page_routes.py:3342`. Both have the same auth logic.
   - Fix: Remove the duplicate in `page_routes.py`.

5. **Duplicate route: `/api/face-alignment/{photo_id}`** — Defined in both `photo_routes.py:230` and `page_routes.py:3433`. Both are admin-only.
   - Fix: Remove the duplicate in `page_routes.py`.

6. **`CONTRIBUTOR_EMAILS` env var** — Defined in `auth.py:26` but never referenced in any route file via `CONTRIBUTOR_EMAILS` directly. The contributor role check uses `_check_contributor()` which checks `user.role`, which IS set from `CONTRIBUTOR_EMAILS` in `User.from_session()`. So the env var works, but there's no documentation of what emails to set or evidence it's actually used in production.

7. **`TRUSTED_CONTRIBUTOR_THRESHOLD` env var** — Defined in `auth.py:30` with default 5. The `is_trusted_contributor()` function that uses it (auth.py:104) is only called from `annotations` loading, but the actual trusted-contributor auto-promotion pathway may not be wired end-to-end.

8. **Stale `sys.path` insertion** — `main.py` inserts the project root into `sys.path` twice (lines 24 and 60). The second insertion is redundant.

## Summary
- Total findings: 26
- Security: 10 (P0: 2, P1: 4, P2: 4)
- Accessibility: 9 (Quick wins: 5, Needs design: 4)
- Dead code: 8
