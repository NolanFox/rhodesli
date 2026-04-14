---
name: Never claim fixed without verification
description: CRITICAL feedback - never claim a bug is fixed without production browser verification. Continue working until verified.
type: feedback
---

NEVER claim something is fixed when it isn't. Continue working until something is actually fixed and verified in production browser. Don't just lie.

**Why:** Session 100b claimed BUG 1 (Jacob Cohen/Jacob Franco) was "FIXED" and later "NOT A BUG" — both were wrong. The actual issue was a data assignment error (wrong face_id confirmed as Yaacov Jacob Franco) that predated Session 100b. The user discovered it was still broken days later. Face cycling was also claimed fixed but arrows were invisible (opacity-0).

**How to apply:**
1. A fix is NOT done until verified in production browser with screenshot evidence
2. Never mark a bug as "NOT A BUG" without investigating the data layer
3. If you can't verify in production, say so explicitly — don't claim FIXED
4. The user's trust is damaged. Every future claim must be backed by evidence.
5. If the deploy hasn't completed, do NOT claim the fix is live
