---
name: Every user interaction must be logged
description: All user interactions (proposals shown, actions taken, navigation) must be logged to Supabase audit_log
type: feedback
originSessionId: 27dd84b2-b7c4-4c48-8614-cb15d02f538c
---
Every user interaction must be logged to Supabase. Not just mutations — also what was shown and what the user navigated to.

**Why:** Person 4063 investigation — couldn't tell if a merge was user-initiated or system-initiated. Without audit trail, debugging identity issues requires guesswork. AUDIT-001 elevated to P0 after this.
**How to apply:** All identity mutations (merge, confirm, reject, skip, rename, detach) log to audit_log with actor, action, entity_id, metadata, timestamp. Phase 1 shipped in Session 113 (22 audit_log calls). Remaining: proposals shown, navigation paths, search queries.
