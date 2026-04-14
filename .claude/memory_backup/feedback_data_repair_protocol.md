---
name: Data repair protocol
description: Every data repair session must snapshot each step, have dry-run mode, restore script, and verify no CONFIRMED identity anchors changed. User explicitly wants reversibility and data preservation.
type: feedback
---

Every data repair session must follow this protocol:
1. **Per-step snapshots** — snapshot FULL identities table before EACH fix step, not once
2. **Dry-run first** — every script has `--dry-run` and `--execute` modes
3. **Restore script** — `restore_from_backup.py` can revert to any step's snapshot
4. **Verify CONFIRMED unchanged** — compare CONFIRMED anchor_ids before/after, alert if any changed
5. **Check embedding impact** — verify distances and centroids aren't affected by data changes
6. **Document everything** — resolution report with before/after counts, scripts used, rationale

**Why:** User said: "I don't have a lot of faith of us being able to do this correctly on the first try" and "anything that was previously merged should be something we should be able to repair." Data preservation is the #1 priority during repairs. Session 133 needed 7 fix steps (original plan was 6) because un-merging created secondary multi-claimed faces.

**How to apply:** Any session that modifies identity data directly (not through app routes) must follow this protocol. Never execute a batch fix without a per-step snapshot and dry-run.
