# Supabase Audit

**Last updated:** 2026-02-12

Rhodesli uses Supabase for authentication only. All data is stored locally (JSON on Railway volume, photos on Cloudflare R2). No vendor lock-in.

---

## Services Used

| Service | Purpose | API Endpoint |
|---------|---------|--------------|
| Google OAuth | User authentication | `/auth/v1/authorize` |
| Email/password signup | User registration | `/auth/v1/signup` |
| Email/password login | User authentication | `/auth/v1/token` |
| Password recovery | Reset flow | `/auth/v1/recover` |
| Token validation | Session verification | `/auth/v1/user` |

**Implementation:** Raw httpx calls in `app/auth.py` (no Supabase SDK). Tests use mocks, no real Supabase calls.

---

## Services NOT Used

- **Database** — identities.json, photo_index.json, proposals.json on Railway volume
- **Storage** — photos and crops on Cloudflare R2
- **Realtime** — no real-time sync features
- **Edge Functions** — all processing on Railway app server

---

## Failure Modes

| Scenario | Impact | User Experience |
|----------|--------|-----------------|
| Supabase down during login | Users cannot sign in | Login page shows error; browsing continues normally |
| Supabase down for logged-in users | None — sessions are self-contained | Full site access (no new logins) |
| Emergency bypass | Enable auth-disabled mode | Set `SUPABASE_URL=""` to make everyone admin |

---

## Code Locations

- `app/auth.py` — All Supabase API calls
- `app/main.py` — Permission checks via `is_auth_enabled()`
- `tests/conftest.py` — Auth state fixtures and mocks

---

## Future

**Phase F (PostgreSQL migration, BE-040–042):** Would add Supabase Database as a dependency. Currently, zero vendor lock-in — authentication can be switched to any OAuth provider.
