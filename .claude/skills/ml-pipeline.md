---
description: "Protocol for modifying ML code. Use whenever editing rhodesli_ml/ or core/*.py files that affect ML behavior."
---
# ML Code Modification Protocol

## Before making changes:
1. Read the relevant section of ALGORITHMIC_DECISIONS.md
2. Read any referenced PRDs (docs/prds/)
3. Understand the current behavior and why it exists

## After making changes:
1. Update ALGORITHMIC_DECISIONS.md with new AD entry:
   - Decision title
   - What was decided
   - What alternatives were considered and rejected
   - Why this approach was chosen
   - Source/breadcrumb to prior decisions
2. Run: `pytest rhodesli_ml/tests/ -v`
3. Run: `pytest tests/ -x -q --ignore=tests/e2e/`
4. If tests fail, fix before proceeding

## Invariants:
- Gatekeeper pattern: ML outputs are PROPOSALS until admin accepts
- Confirmed data feeds back as ground truth anchors
- Never overwrite user-entered data with ML predictions
