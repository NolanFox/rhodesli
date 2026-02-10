# Rhodesli Project Backlog

Last updated: 2026-02-10 (Session 10 — UX Overhaul + Content + Contributor Flow)

## Active Bugs
- (none)

## Setup Required (ONE TIME)
- [ ] Generate sync token: `python scripts/generate_sync_token.py`
- [ ] Set RHODESLI_SYNC_TOKEN on Railway: `railway variables set RHODESLI_SYNC_TOKEN=<token>`
- [ ] Set RHODESLI_SYNC_TOKEN in .env: `echo 'RHODESLI_SYNC_TOKEN=<token>' >> .env`
- [ ] Deploy (push to main or Railway auto-deploy)
- [ ] Test sync: `python scripts/sync_from_production.py --dry-run`

## Ready to Apply (after sync)
- [ ] Sync production data: `python scripts/sync_from_production.py`
- [ ] Re-run ML pipeline: `bash scripts/full_ml_refresh.sh`
- [ ] Apply 19 VERY_HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier very_high`
- [ ] Apply 33 HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier high`
- [ ] After applying, sync to production and confirm in web UI

## Immediate (This Weekend)
- [ ] Re-run validation after sync to check if admin tagging created signal
- [ ] Test new UX features on real phone (mobile responsive, touch swipe, keyboard shortcuts)
- [ ] Share with 2-3 family members for initial feedback
- [ ] Smoke test all fixes on live site

## Near-Term (Next 1-2 Weeks)
- [ ] BE-014: Canonical name registry (variant spellings)
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users

## Medium-Term (Next Month)
- [ ] FE-070–FE-073: Client-side analytics and admin dashboard
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [ ] ROLE-006: Email notifications for contributors
- [ ] Postgres migration (identities + photo_index -> Supabase)

## Long-Term (Quarter+)
- [ ] Family tree integration (GEDCOM, relationships)
- [ ] Auto-processing pipeline (ML on Railway, no local step)
- [ ] Age-invariant face recognition research
- [ ] Multi-tenant architecture (other communities)
- [ ] CI/CD pipeline (automated tests, staging, deploy previews)

## Completed
- [x] Phase A: Railway deployment + Supabase auth + permission model
- [x] Phase A stabilization: all 8 P0 bugs fixed, event delegation pattern
- [x] Phase B: Landing page, search, mobile, sync infrastructure
- [x] v0.10.0–v0.12.1: Face overlays, inline actions, fuzzy search, photo nav
- [x] v0.13.0: ML validation — threshold calibration, golden set, clustering validation
- [x] v0.14.0: Token-authenticated sync API + reliable sync script
- [x] v0.14.1: Skipped faces fix — clustering includes 192 skipped faces
- [x] v0.15.0: Upload processing pipeline — staged file sync API, download, orchestrator
- [x] v0.16.0: ML pipeline + annotation engine + collaboration (969 tests)
- [x] v0.17.0: Annotation engine + merge safety + contributor roles (1032 tests)
- [x] v0.17.1: Verification pass — golden set, permission tests, ROLES.md (1059 tests)
- [x] v0.17.2: Quality hardening — EXIF ingestion, error handling, permission tests (1152 tests)
- [x] v0.18.0: UX Overhaul + Contributor Flow (1221 tests)
  - Landing page rewrite with historical Rhodes content
  - Login prompt modals with action context
  - Section rename: Confirmed→People, Skipped→Needs Help
  - Button prominence: View All Photos + Find Similar
  - Compare faces UX: face/photo toggle, clickable names
  - Contributor merge suggestions with admin approval
  - Bulk photo select mode with collection reassignment
