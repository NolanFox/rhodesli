# Session 51B Log — Production Bug Fixes
Started: 2026-02-19
Prompt: docs/prompts/session_51B_prompt.md

## Phase Checklist
- [ ] Phase 0: Orient + Diagnose all 5 bugs
- [ ] Phase 1: Fix Compare Upload Pipeline (P0)
- [ ] Phase 2: Verify "Name These Faces" button (P0/Auth)
- [ ] Phase 3: Remove Estimate tab from /compare (P1)
- [ ] Phase 4: Supabase keepalive + auth warning (P0)
- [ ] Phase 5: Email notification audit (P2)
- [ ] Phase 6: Verification Gate
- [ ] Phase 7: Docs + Push

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- [ ] All tests pass

## Diagnosis Notes

### BUG 1: Compare Upload (P0)
- **Root cause**: InsightFace NOT installed on Railway (not in requirements.txt, Dockerfile excludes ML modules)
- **Flow**: Upload saves file to R2 with `status="awaiting_analysis"`, `faces=[]`, `results=[]`
- **Problem**: Shows "Photo saved! Check back soon" but no backend job ever processes it
- **Fix**: Change messaging to be honest — explain comparison requires local processing or pull-to-local workflow
- **Key code**: app/main.py lines 13722-13755 (has_insightface check + R2 fallback)

### BUG 2: Name These Faces (NOT A BUG)
- **Root cause**: Button is correctly admin-only (AD-104, Session 51 design)
- **Condition**: `is_admin and len(unidentified_face_ids) >= 2 and not seq_mode`
- **Tests exist**: test_button_hidden_non_admin, test_button_shown_admin, test_button_hidden_single_unidentified
- **Verdict**: Working as designed. Tester was not logged in as admin.

### BUG 3: Estimate Tab Duplication (P1)
- **Root cause**: /compare (line 13320-13332) and /estimate (line 14464-14469) both have tab switchers
- **Problem**: Since Session 50 added /estimate as standalone nav item, tabs are redundant
- **Fix**: Remove tab navigation from both pages

### BUG 4: Supabase Keepalive (P0)
- **Root cause**: /health endpoint (line 6484-6506) only checks local data, NOT Supabase
- **Railway health check**: Configured in railway.toml (every 30s), Docker HEALTHCHECK (every 30s)
- **Problem**: Supabase free tier pauses after inactivity. No API calls = project pauses = auth breaks silently
- **Fix**: Add Supabase ping to /health endpoint

### BUG 5: Email Notifications (P2 — known missing)
- **Status**: Email code exists (Resend API in `_notify_admin_upload()` line 1429)
- **Gated**: Behind RESEND_API_KEY env var — logs "skipping email" when not set
- **User-facing**: No misleading text shown to users. Backend-only admin notification.
- **Verdict**: No UI changes needed. Document OPS-001 status clearly.

## Fix Log
(filled during implementation)
