# Rhodesli — Cumulative Development Summary

**As of:** Session 9, v0.17.0, 2026-02-10
**Total Tests:** 1032
**Total Photos:** 148 across 4 collections
**Confirmed Identities:** 23 of 292
**Live Site:** https://rhodesli.nolanandrewfox.com

---

## Session History

| Session | Date | Version | Tests | Key Deliverables |
|---------|------|---------|-------|------------------|
| 1 | 2026-02-05 | v0.1–v0.5 | ~300 | Initial deployment, Supabase auth, Railway, R2 |
| 2 | 2026-02-05 | v0.6 | ~450 | Permission model, auth polish, testing harness |
| 3 | 2026-02-06 | v0.8 | ~560 | Landing page, mobile responsive, admin export |
| 4 | 2026-02-06 | v0.9 | ~630 | ML algorithmic decisions (AD-001–AD-012) |
| 5 | 2026-02-07 | v0.10 | 663 | Harness buildout, proposals page, multi-merge |
| 6 | 2026-02-08 | v0.12 | 847 | Phase A stabilization, 4 P0 bugs, search, mobile tabs |
| 7 | 2026-02-09 | v0.13 | 879 | ML validation, golden set, threshold calibration |
| 7b | 2026-02-10 | v0.15 | 943 | Sync infrastructure, upload pipeline, skipped faces |
| 8 | 2026-02-10 | v0.16 | 969 | ML pipeline, annotation engine, activity feed |
| 9 | 2026-02-10 | v0.17 | 1032 | Merge safety, photo/identity annotations, EXIF, contributor roles |

---

## Features Shipped (Production-Ready)

### Authentication & Permissions
- Google OAuth + email/password via Supabase
- Invite code system for signup
- Binary permission model: public (view) + admin (everything)
- Contributor role system with auto-promotion (ROLE-002/003)
- Session cookie management, HTMX 401 pattern

### Photo Archive
- 148 photos across 4 collections (Vida Capeluto NYC, Betty Capeluto Miami, Nace Capeluto Tampa, Newspapers.com)
- Cloudflare R2 storage with local/R2 dual mode
- Photo metadata storage and display (date, location, caption, occasion, donor, camera)
- EXIF extraction utility (date, camera, GPS)
- Photo dimension caching for R2 mode

### Face Detection & Matching
- InsightFace/AdaFace PFE with 512-dim embeddings
- MLS distance metric (AD-002)
- Multi-anchor matching (AD-001)
- Dynamic threshold calibration with 4-tier confidence labels (AD-013)
- Golden set evaluation (125 mappings, 23 identities, 698 same-person pairs)
- Golden set diversity analysis (ML-011)
- Rejection memory in clustering (AD-004)
- Post-merge re-evaluation with inline suggestions
- Ambiguity detection (margin-based flagging)

### Identity Management
- Full CRUD: confirm, reject, skip, merge, detach, rename
- Non-destructive merge system with full audit trail (BE-001–BE-006)
- Merge undo with state restoration
- Direction-aware merging (unnamed→named auto-correction)
- Structured names (first_name/last_name auto-parsing)
- Identity metadata (birth/death years, birthplace, maiden name, bio)
- Identity annotations (bio, relationships, stories)
- 292 identities (23 confirmed, 181 proposed, 88 inbox)

### Annotation System
- Submit/review/approve/reject workflow
- Photo-level annotations (captions, dates, locations, stories, source)
- Identity-level annotations (bio, relationships, stories)
- Contributor submissions with confidence levels
- Admin approval queue (`/admin/approvals`)
- User contribution tracking (`/my-contributions`)
- Annotation merging on identity merge (BE-006)

### User Experience
- Responsive design (2-col mobile, 4-col desktop grid)
- Mobile bottom tab navigation
- Hamburger menu sidebar
- Lightbox photo viewer with keyboard navigation
- Face overlay system with color-coded states
- Inline confirm/skip/reject from photo overlays
- Global search with fuzzy matching (Levenshtein distance)
- Typeahead name lookup
- Focus mode for identity review
- Progress dashboard ("23 of 215 faces identified")
- Welcome modal for first-time visitors
- Activity feed

### Admin Tools
- ML evaluation dashboard (`/admin/ml-dashboard`)
- Proposals review page
- Data export (token-authenticated sync API)
- Production-to-local sync script
- Staged upload download and processing pipeline
- Backup automation

### Infrastructure
- Railway deployment with Docker + persistent volume
- Cloudflare R2 for photo storage
- Token-authenticated sync API
- End-to-end upload processing pipeline
- 19 Playwright E2E browser tests

---

## Test Coverage Breakdown

1032 tests across ~35 test files:
- **Auth & Permissions**: test_auth, test_permissions (~80 tests)
- **UI Elements**: test_ui_elements, test_lightbox, test_smoke (~60 tests)
- **Face Operations**: test_face_count, test_merge_direction, test_skipped_faces (~45 tests)
- **Photo Operations**: test_photo_context, test_photo_metadata, test_photo_annotations (~35 tests)
- **Identity Operations**: test_identity_annotations, test_merge_enhancements (~25 tests)
- **ML Pipeline**: test_cluster_new_faces, test_ml_dashboard, test_post_merge (~30 tests)
- **Annotation System**: test_annotations, test_contributor_roles (~30 tests)
- **Infrastructure**: test_sync_api, test_staged_sync, test_docs_sync (~40 tests)
- **Core Libraries**: test_crop, test_neighbors, test_registry (~100 tests)
- **E2E**: 19 Playwright critical path tests
- **Plus**: regression tests, unicode boundary, metadata, activity feed, search, keyboard shortcuts

---

## Architecture Summary

```
app/main.py          ~10,000 lines  FastHTML web app (all routes + UI)
app/auth.py          ~300 lines     Supabase auth, User model, roles
core/registry.py     ~1,100 lines   IdentityRegistry (JSON CRUD + merge)
core/photo_registry.py ~200 lines   PhotoRegistry (photo_index.json)
core/neighbors.py    ~200 lines     Neighbor search (FROZEN)
core/storage.py      ~100 lines     Photo/crop URL generation
core/exif.py         ~100 lines     EXIF extraction utility
scripts/             14 scripts     Sync, analyze, process, migrate
tests/               ~35 files      1032 tests
data/                JSON + NumPy   Read-only for web app
```

---

## What Remains

### High Priority (Next Sessions)
- BE-014: Canonical name registry (variant spellings)
- FE-041: "Help Identify" mode for non-admin users
- ML-001: User actions feed back to ML predictions
- BE-031: Upload moderation queue

### Medium Priority
- OPS-001: Custom SMTP for branded email
- OPS-002: CI/CD pipeline
- FE-060–FE-063: Workflow speed improvements
- FE-070–FE-073: Analytics dashboard

### Long Term
- BE-040–BE-042: PostgreSQL migration
- AN-020–AN-023: Family tree integration
- ML-030–ML-032: Model evaluation (ArcFace, ensemble)
- GEN-001+: Multi-tenant architecture

---

## Key Technical Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| AD-001 | Multi-anchor matching | More robust than centroid averaging for varied faces |
| AD-002 | MLS distance metric | Leverages PFE quality estimates, better than cosine |
| AD-004 | Rejection memory | Prevents re-suggesting rejected pairs |
| AD-013 | 4-tier confidence | VERY_HIGH/HIGH/MODERATE/LOW from golden set calibration |
| OD-001 | Railway + R2 | Persistent volume + no egress fees |
| OD-004 | R2 direct serving | No proxy needed, public bucket |
| ROLE-002 | Contributor role | 3-tier: admin/contributor/viewer with env var assignment |
| ROLE-003 | Trusted contributor | Auto-promote after 5+ approved annotations |
