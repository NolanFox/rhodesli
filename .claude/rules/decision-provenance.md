---
paths:
  - "app/main.py"
  - "core/registry.py"
  - "core/photo_registry.py"
  - "core/grouping.py"
  - "docs/DECISIONS.md"
---

# Decision Provenance Rule

Every user-visible behavior change needs a documented decision trail.

1. **Before changing search, tagging, merge, or display behavior**: Check if the current behavior was an intentional decision. Read `docs/DECISIONS.md` and `docs/ml/ALGORITHMIC_DECISIONS.md` for prior decisions.

2. **When adding new behavior**: Document the decision with context (what problem it solves, what alternatives were considered, why this approach). Add to `docs/DECISIONS.md` for UI/UX decisions or `docs/ml/ALGORITHMIC_DECISIONS.md` for ML decisions.

3. **When fixing a bug vs changing behavior**: Distinguish between "this code is broken" (bug fix, no decision needed) and "this code works but should work differently" (behavior change, needs decision entry). If users have already adapted to the current behavior, changing it is a behavior change.

4. **Surname variant groups** (`data/surname_variants.json`): Changes to variant groups affect search results for all users. Adding a new group is low-risk. Removing or restructuring groups needs a decision entry.
