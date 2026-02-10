# Rhodesli Project Backlog

Last updated: 2026-02-10 (Session 6 — Sync Infrastructure)

## Active Bugs
- (none — all P0 bugs fixed through v0.12.1)

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
- [x] Build token-authenticated sync API (2026-02-10)
- [x] Build reliable sync script (2026-02-10)
- [ ] Re-run validation after sync to check if admin tagging created signal
- [ ] End-to-end test pending upload flow (upload via web -> process_pending.py -> verify)
- [ ] Test new UX features on real phone (mobile responsive, touch swipe, keyboard shortcuts)
- [ ] Share with 2-3 family members for initial feedback

## Near-Term (Next 1-2 Weeks)
- [ ] Verify Resend email notifications fire on pending upload
- [ ] UX verification: Find Similar auto-scroll, bulk merge/not-same, no-reload HTMX actions
- [ ] Collect 50+ admin-validated clustering proposals for re-calibration
- [ ] Re-run calibration after batch 2 upload (more diverse data)

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
- [x] Bug fix: multi-merge form (HTMX formaction + checkbox toggle)
- [x] Bug fix: carousel count static after Focus mode actions
- [x] Bug fix: main face image not clickable in Focus mode
- [x] Photo navigation: keyboard arrows, prev/next buttons, lightbox
- [x] Match mode redesign: larger faces, confidence bar, clickable, logging
- [x] Face tagging: Instagram-style tag dropdown with autocomplete + merge
- [x] Identity notes system (add/view notes with author tracking)
- [x] Proposed matches system (propose/list/accept/reject)
- [x] Collection stats cards and reassignment endpoint
- [x] Clustering dry-run report (35 matches, Betty Capeluto collection)
- [x] v0.10.0: Face overlay status colors + completion badges
- [x] v0.10.0: Single tag dropdown + Create identity from tag
- [x] v0.10.0: Keyboard shortcuts (C/S/R/F) in focus mode
- [x] v0.10.0: Proposals admin page + sidebar link
- [x] v0.10.0: AD-001 fix in cluster_new_faces.py (multi-anchor)
- [x] v0.10.0: Multi-merge bug fix (list[str] annotation)
- [x] v0.10.0: Lightbox arrow navigation fix (photoNavTo)
- [x] v0.10.0: Collection stats filtered subtitle fix
- [x] v0.10.0: Mobile responsive pass (touch swipe, stacking, 44px targets)
- [x] v0.10.0: Golden set rebuild + threshold analysis (1.00=100% precision)
- [x] v0.10.0: AD-004 rejection memory verified working
- [x] v0.12.0: Identity-context photo navigation (arrows from face cards/search)
- [x] v0.12.0: FE-011 — Mobile bottom tab navigation
- [x] v0.12.0: FE-053 — Progress dashboard with identification bar
- [x] v0.12.0: FE-033 — Fuzzy name search (Levenshtein) + match highlighting
- [x] v0.12.0: Inline face actions (hover confirm/skip/reject on overlays)
