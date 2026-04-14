---
name: Audit logging is critical — user can't distinguish own actions from automated
description: Investigation of Person 4063 revealed zero provenance for merges. User needs to know what they did vs what was automated. AUDIT-001 is now P0.
type: feedback
---

During a hands-on investigation of Person 4063 (potential mismatch), the user could not determine whether they manually merged two identities or whether it was done automatically. The system has zero audit trail for merges.

**Why:** The user is actively triaging 1300+ pending identities. With speed-run, match mode, cross-batch proposals, and auto-clustering all operating, the user needs to distinguish their own decisions from automated ones — especially when reviewing potential mistakes weeks later.

**What's missing today:**
- `registry.merge_identities()` writes no audit_log entry
- No record of: who initiated, what distance was shown, what UI route was used
- Confirm, reject, skip, rename, detach — none of these log to audit_log either
- The audit_log table exists but only has "approved" actions (upload approvals)

**How to apply:**
- AUDIT-001 is now P0, not backlog
- Every call to `merge_identities()`, `confirm_identity()`, `reject_face()`, `skip_identity()`, `rename_identity()`, `detach_face()` must write an audit_log row
- Each row needs: action, entity_id, user_email (or "system"/"claude"), old_value, new_value, metadata (route, distance, session)
- Cross-batch proposals that get auto-applied need "system" as actor
- This is ~50 lines of code spread across identity_routes.py — straightforward but important

**Case study:** Person 4063 (f1fa51b2) had 2 identities merged into it on 2026-03-17 at 05:00. No audit_log entries exist. User cannot determine if they did it in speed-run or if it was automated. Embedding analysis shows the merges were probably correct (distance 0.89) but one face is borderline (1.25). Without provenance, can't evaluate the decision quality.
