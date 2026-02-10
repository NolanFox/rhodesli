# Role Permissions Matrix

**Last updated:** 2026-02-10

Principle: **Contributors suggest, admins decide.** No exceptions for V1.

---

## Role Assignment

| Role | How Assigned |
|------|-------------|
| Viewer | Default for any logged-in user |
| Contributor | Email in `CONTRIBUTOR_EMAILS` env var |
| Trusted Contributor | `is_trusted_contributor()` — 5+ approved annotations (utility only, no route-level effect in V1) |
| Admin | Email in `ADMIN_EMAILS` env var |

---

## Permission Matrix

| Action | Viewer | Contributor | Trusted Contributor | Admin |
|--------|--------|-------------|---------------------|-------|
| Browse photos/identities | Yes | Yes | Yes | Yes |
| Search | Yes | Yes | Yes | Yes |
| View photo context | Yes | Yes | Yes | Yes |
| Submit annotations | No | Yes | Yes (future: badged) | Yes (direct) |
| Upload photos | No | Yes (moderated) | Yes (future: unmoderated) | Yes |
| View /my-contributions | No | Yes | Yes | Yes |
| Merge identities | No | No | No | Yes |
| Confirm identity | No | No | No | Yes |
| Reject identity | No | No | No | Yes |
| Skip/defer faces | No | No | No | Yes |
| Approve/reject annotations | No | No | No | Yes |
| Undo merges | No | No | No | Yes |
| Rename identity | No | No | No | Yes |
| Detach face | No | No | No | Yes |
| View ML dashboard | No | No | No | Yes |
| Manage pending uploads | No | No | No | Yes |
| Admin data export | No | No | No | Yes |

---

## Implementation Notes

- All admin-only routes use `_check_admin(sess)` which returns 401/403
- Login-required routes use `_check_login(sess)` — any logged-in user, regardless of role
- `_check_contributor(sess)` exists but is **not used by any route** in V1
- `is_trusted_contributor()` is a utility function, **not wired into any route guard** in V1
- When auth is disabled (local dev), all permission checks pass through

## Future Plans (Post-V1)

- Trusted contributor badge on annotations for admin prioritization
- Trusted contributor bypass of upload moderation queue
- `_check_contributor` will guard annotation submission (currently any login works)
- ML similarity suggestions visible to contributors on skipped faces
