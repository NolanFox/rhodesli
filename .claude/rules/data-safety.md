---
paths:
  - "tests/**"
  - "data/**"
  - "scripts/**"
---

# Data Safety Rules

## Tests
- NEVER write to production data files (data/*.json, data/*.npy) in tests
- Use unittest.mock.patch for all external service calls (Supabase, R2, etc.)
- Test fixtures must use obviously fake IDs (prefix "test-") or UUID-style
- ALL tests that POST to data-modifying routes MUST mock both load and save functions
- Verify: `grep -rn "\.write\|supabase.*insert" tests/` should show only mocked calls
- `test_no_test_data_in_production` in test_data_integrity.py guards against regression

## Deployments
- Production is LIVE with real users
- Database schema changes must be backwards-compatible
- Add new fields with defaults — never remove or rename existing fields
- Railway deploys are rolling — app must work during deploy transition

## Data Integrity
- Run `python scripts/check_data_integrity.py` before and after any data changes
- Never modify identity data without audit trail
- Annotations are user-generated content — treat as sacred
- `scripts/clean_test_data.py` exists for emergency cleanup (always --dry-run first)
