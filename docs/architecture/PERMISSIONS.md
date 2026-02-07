# Rhodesli Permission Model

**Last updated:** 2026-02-06

The current permission model is binary: public browsing for everyone, admin-only for all data modifications. There are no intermediate contributor roles yet.

---

## Auth Configuration

Auth is enabled when both `SUPABASE_URL` and `SUPABASE_ANON_KEY` environment variables are set. When auth is disabled (local development), all permission checks pass through.

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Legacy JWT anon key (must start with `eyJ...`) |
| `ADMIN_EMAILS` | Comma-separated list of admin emails |
| `SESSION_SECRET` | Cookie signing secret |

**Admin email:** `NolanFox@gmail.com` (configured via `ADMIN_EMAILS` env var)

---

## Auth Methods

- **Google OAuth** -- via Supabase, enabled in production
- **Email/password** -- via Supabase Auth REST API
- **Invite codes** -- required for signup (configured via `INVITE_CODES` env var)

Sessions are stored in httpOnly cookies. The `User` dataclass in `app/auth.py` has fields: `id`, `email`, `is_admin`.

---

## Current Permission Matrix

| Action | Anonymous | Logged-in User | Admin |
|--------|-----------|----------------|-------|
| Browse photos | Yes | Yes | Yes |
| View identities | Yes | Yes | Yes |
| Search | Yes | Yes | Yes |
| View photo context | Yes | Yes | Yes |
| Upload photos | No | No | Yes |
| Confirm identity | No | No | Yes |
| Reject identity | No | No | Yes |
| Merge identities | No | No | Yes |
| Rename identity | No | No | Yes |
| Detach face | No | No | Yes |
| Skip identity | No | No | Yes |
| Manage pending uploads | No | No | Yes |

All POST routes that modify data use `_check_admin(sess)`. The only exception is viewing pending upload status, which uses `_check_login(sess)`.

---

## Auth Guard Functions

Defined in `app/main.py`:

**`_check_admin(sess)`** -- Returns 401 (unauthenticated) or 403 (not admin), or `None` (allowed). When auth is disabled, always returns `None`.

**`_check_login(sess)`** -- Returns 401 (unauthenticated) or `None` (allowed). When auth is disabled, always returns `None`.

Both return HTTP 401 (not 303 redirect) so that HTMX `beforeSwap` handlers can intercept the response and show a login modal instead of replacing page content with a redirect target.

---

## HTMX Auth Pattern

Protected HTMX endpoints must return 401 status codes, not 303 redirects. HTMX silently follows redirects, which would cause the login page HTML to be swapped into the target element.

The client-side `htmx:beforeSwap` handler intercepts 401 responses and displays a login modal.

---

## Future Plans

Contributor and viewer roles are designed but not yet implemented. See `docs/design/FUTURE_COMMUNITY.md` for the planned three-tier permission model (viewer, contributor, admin).
