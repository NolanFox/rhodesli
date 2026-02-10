# Rhodesli Project Backlog

Last updated: 2026-02-10 (Session 8 — ML Pipeline + Annotation Engine + Collaboration)

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
- [ ] BE-012: Photo metadata (date, location, occasion, source)
- [ ] BE-013: EXIF extraction from uploaded photos
- [ ] BE-014: Canonical name registry (variant spellings)
- [ ] AN-006: Photo-level annotations (captions, dates, locations, stories)
- [ ] AN-012–AN-014: Identity-level annotations (bio, relationships, generation)
- [ ] BE-001–BE-006: Non-destructive merge system verification/extension
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [ ] ML-011: Golden set diversity analysis (quality, temporal)

## Medium-Term (Next Month)
- [ ] ROLE-002: Contributor role (propose identifications, add annotations)
- [ ] ROLE-003: Trusted contributor (direct confirmation after N correct proposals)
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users
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
  - Post-merge suggestions, rejection memory in clustering, ambiguity detection
  - ML evaluation dashboard (/admin/ml-dashboard)
  - Annotation system (submit/approve/reject + my-contributions)
  - Structured names (BE-010), identity metadata (BE-011)
  - Activity feed (/activity), welcome modal (FE-052)
