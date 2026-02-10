---
paths:
  - "app/main.py"
---

# About Page & Landing Page Content Rules

When modifying landing page stats, /about page, or any user-facing documentation:
- Stats must be computed dynamically from data files, never hardcoded
- Verify accuracy: photo count from photo_index, identity counts from identities.json
- The "awaiting identification" count must include INBOX + PROPOSED + SKIPPED faces
- Update docs/ABOUT_CONTENT.md if any user-facing copy changes
