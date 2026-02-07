# Rhodesli Project Backlog

Last updated: 2026-02-07

## Active Bugs
- [ ] AD-001 VIOLATION: `scripts/cluster_new_faces.py` uses centroid averaging (line 124). Must fix with golden set testing before and after.

## Immediate (This Weekend)
- [ ] End-to-end test pending upload flow (upload via web -> process_pending.py -> verify)
- [ ] Run golden set evaluation locally: `scripts/evaluate_golden_set.py`
- [ ] Run golden set builder locally: `scripts/build_golden_set.py`
- [ ] Test new UX features (merge undo, sidebar collapse, face carousel, comparison view, Match mode)
- [ ] Share with 2-3 family members for initial feedback

## Near-Term (Next 1-2 Weeks)
- [ ] ML calibration: tune distance thresholds using golden set precision/recall
- [ ] Fix AD-001 violation in cluster_new_faces.py (multi-anchor, not centroid)
- [ ] UX verification: Find Similar auto-scroll, bulk merge/not-same, no-reload HTMX actions, toast notifications
- [ ] Rejection memory implementation (AD-004 — partially implemented)
- [ ] Sync production->local script using admin export endpoints
- [ ] Mobile polish pass (test on real phone)
- [ ] Verify Resend email notifications fire on pending upload

## Medium-Term (Next Month)
- [ ] Better face detection evaluation (compare current vs alternatives — golden set comparison)
- [ ] Embedding model evaluation (compare alternatives — golden set comparison)
- [ ] Postgres migration (identities + photo_index -> Supabase)
- [ ] Contributor roles (see docs/design/FUTURE_COMMUNITY.md)
- [ ] Annotation engine (captions, dates, locations, stories)
- [ ] Upload moderation queue with file size limits and rate limiting

## Long-Term (Quarter+)
- [ ] Family tree integration (GEDCOM, relationships)
- [ ] Auto-processing pipeline (ML on Railway, no local step)
- [ ] Age-invariant face recognition research
- [ ] Multi-tenant architecture (other communities)
- [ ] CI/CD pipeline (automated tests, staging, deploy previews)

## Completed
- [x] Phase A: Railway deployment with Docker + persistent volume
- [x] Phase B: Supabase authentication (Google OAuth + email/password)
- [x] Role-based permissions with public browsing, admin-only modifications
- [x] Password recovery, OAuth social login, email templates
- [x] Login modal for protected actions, styled confirmation dialog
- [x] Google Sign-In branding, email inline styles
- [x] Regression test suite + testing requirements
- [x] Landing page, admin export, mobile CSS, docs overhaul
- [x] UX overhaul: merge system, sidebar, face cards, inbox workflow
- [x] Pending upload queue with admin moderation
- [x] ML clustering pipeline: golden set, evaluation, face matching
- [x] Photo storage consolidation to single raw_photos/ path
- [x] R2 photo serving (uploaded photos + inbox photos)
- [x] Photo source lookup fix for inbox-style photo IDs
- [x] Doc restructure: split SYSTEM_DESIGN_WEB.md into focused docs
- [x] ML algorithmic decision capture system with path-scoped rules
- [x] Find Similar 500 error fix in production
