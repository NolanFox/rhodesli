# Production Verification Rule

## When to verify
- After ANY code change that affects UI, uploads, or routes
- After ANY deployment (git push or railway up)
- At the END of every session that modifies app/main.py or core/

## How to verify
1. Run `python scripts/production_smoke_test.py --url [target]`
2. For upload-affecting changes: actually upload a test photo via curl
3. Log results in the session log with timing data

## What to verify
- Health endpoint returns 200 with expected fields
- Landing page loads with photos
- Compare page accepts file upload and returns results
- Estimate page accepts file upload and returns results
- Person detail pages return 200 for valid IDs, 404 for invalid
- No console errors in HTMX responses

## Failure protocol
- If smoke test fails: fix before completing session
- If fix is not possible: document in session log with BLOCKER tag
- Never mark a session complete if smoke test has critical failures

See: docs/HARNESS_DECISIONS.md HD-010
