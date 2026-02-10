---
paths:
  - "app/auth.py"
  - "app/main.py"
  - "docs/ROLES.md"
  - "docs/architecture/PERMISSIONS.md"
---

# Auth & Permission Rules

Before modifying auth or permission logic, read docs/ROLES.md.

Key principles:
1. **Contributors suggest, admins decide** — no exceptions for V1
2. All data-modifying actions are **admin-only** (`_check_admin`)
3. `_check_contributor` exists but is NOT used by any route in V1
4. HTMX auth failures return 401, not 303 (Lesson #11)
5. When auth is disabled (local dev), all permission checks pass through

After any permission change, verify the matrix in docs/ROLES.md matches the code.
Run the permission matrix tests: `pytest tests/test_permissions.py -v`
