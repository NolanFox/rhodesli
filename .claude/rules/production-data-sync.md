---
paths:
  - "data/**"
  - "core/**"
  - "app/main.py"
  - "scripts/**"
---

# Production Data Sync Rule

Before writing ANY code that touches identity/photo/face data:

1. Run `python scripts/sync_from_production.py` to get fresh production data
2. Verify counts match expectations (confirmed, proposed, inbox, skipped)
3. Only then begin coding

If sync fails → STOP. Do not proceed with stale data. Admin may have been
merging, detaching, or confirming faces on production since last session.

After session → push with merge-aware strategy:
- `python scripts/push_to_production.py` (uses perform_merge — production wins conflicts)
- NEVER use `--no-merge` unless you know local data is a clean superset of production

This prevents blind overwrites of admin triage work (Lesson 56).
