# Admin Auth Verification — Session 49B Final

## Auth Mechanism

| Component | Implementation |
|-----------|---------------|
| User model | `User(id, email, is_admin, role)` in `app/auth.py` |
| Admin check | Email in `ADMIN_EMAILS` env var (case-insensitive) |
| Route guard | `_check_admin(sess)` returns `None` (allowed), `401` (unauth), `403` (forbidden) |
| Session | Cookie-based via FastHTML, user data in `sess["auth"]` |
| OAuth | Google OAuth via Supabase |
| HTMX compat | Returns 401 (not 303 redirect) so `htmx:beforeSwap` shows login modal |

## Admin Email
- Configured: `NolanFox@gmail.com` via `ADMIN_EMAILS` environment variable
- Production: set on Railway
- Local: documented in `.env.example`

## Admin-Only Features (Verified in Code)

### Identity Management (POST routes, all use `_check_admin`)
- `/confirm/{id}`, `/reject/{id}`, `/api/identity/{id}/merge/{id}`
- `/api/identity/{id}/rename`, `/api/face/{id}/detach`, `/api/identity/{id}/skip`
- `/api/identity/{id}/bulk-merge`, `/api/identity/{id}/undo-merge`

### Data Editing (POST routes, all use `_check_admin`)
- `/api/photo/{id}/collection`, `/api/photo/{id}/source`, `/api/photo/{id}/source-url`
- `/api/photo/{id}/correct-date`

### ML Review (POST, admin-only)
- `/api/ml-review/birth-year/{id}/accept`, `/api/ml-review/birth-year/{id}/reject`

### Admin Dashboard Pages (GET, admin content conditional)
- `/admin/proposals`, `/admin/approvals`, `/admin/audit`, `/admin/review-queue`
- Admin dashboard banner on landing page (conditional on `user_is_admin`)

### Admin-Only UI Elements
- Birth year ML estimates with Accept/Reject buttons
- Edit buttons on identity names
- Action buttons (Confirm, Reject, Merge, Detach, Skip)
- Quality score display
- Comments moderation (hide action)

## Playwright Admin Auth Status

**NOT CONFIGURED** — Playwright e2e tests run with auth disabled:
- `conftest.py` strips `SUPABASE_URL` and `SUPABASE_ANON_KEY` from subprocess env
- No `.auth/` directory or persisted auth state
- All routes accessible without authentication in tests
- Unit tests (`tests/`) handle auth scenarios via mocking

### Why this is acceptable for now
- Unit tests verify permission enforcement (60+ admin route tests, return 401/403)
- E2e tests verify DOM structure and HTMX behavior without auth
- Auth mechanism is simple (email-in-set check), thoroughly tested

## Gaps Identified

1. **No e2e test for admin-only UI visibility** — Cannot verify admin features render correctly in a real browser with auth enabled
2. **No stored Playwright auth state** — Would need OAuth login automation or manual cookie capture
3. **No test for the full OAuth → session → admin check flow** — Unit tests mock individual pieces

## Recommendation for Future Admin E2e Testing

Priority: MEDIUM (unit tests cover permission logic; e2e tests would catch rendering issues)

Options:
1. **Manual cookie capture**: Log in via browser, extract session cookie, save as Playwright auth state
2. **Supabase service role**: Use admin API to create a test session programmatically
3. **Auth bypass for testing**: Add a `TEST_ADMIN_SESSION` env var that creates an admin session without OAuth

Option 1 is simplest and sufficient for a single-admin system.
