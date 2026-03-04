---
description: "Run automated verification loop: test, fix, test (max 3 iterations)"
---
# Verify

Automated build-test-fix loop. Inspired by everything-claude-code verification-loop pattern (HD-024).

## Workflow

1. Run `scripts/test-gate.sh fast` (app tests)
2. If tests fail:
   - Read the failure output
   - Fix the root cause (not just the symptom)
   - Run `scripts/test-gate.sh fast` again
3. If still failing after **3 iterations**: STOP and report what's broken
4. Once app tests pass, run `scripts/test-gate.sh ml` (ML tests)
5. If ML tests fail: same fix loop (max 3 iterations)
6. Report final status:
   - App tests: PASS/FAIL (count)
   - ML tests: PASS/FAIL (count)
   - Total iterations used

## When to Use
- After any implementation phase before committing
- After merging branches
- When unsure if recent changes broke anything
- As part of /session-review

## Key Rules
- Never skip ML tests (dual test suite rule)
- Never use --no-verify to bypass
- If a test fails consistently, investigate — don't just delete the test
