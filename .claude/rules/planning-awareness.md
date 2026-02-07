---
paths:
  - "app/main.py"
  - "core/*.py"
  - "scripts/*.py"
---

# Future Planning Awareness

Before making significant changes, check tasks/todo.md for related planned work.
When implementing a feature, consider whether the implementation supports or conflicts with planned future work.

Key upcoming changes that affect current code:
- Postgres migration planned: don't add new JSON file dependencies without considering migration path
- Contributor roles planned: permission checks may need to support viewer/contributor/admin (not just admin)
- Auto-ML pipeline planned: face detection code should be callable without local-only dependencies

If your change conflicts with planned work, note the conflict in a code comment and flag to the user.
