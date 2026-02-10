# Rhodesli: Comprehensive Project Backlog & Improvement Plan

**Version**: 5.2 — February 10, 2026
**Status**: 1152 tests passing, v0.17.2, 148 photos, 23 confirmed identities, 181 faces, 33 proposals ready
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). Auth is complete with Google OAuth, invite codes, and a locked-down permission model (public=view, admin=everything else). Seven sessions have delivered deployment, auth, core UX, ML pipeline, stabilization (Phase A complete), share-ready polish (Phase B mostly complete), ML validation, sync infrastructure, and 900 tests.

---

## 1. BUGS

**Status**: All P0 bugs resolved. No active P0 bugs as of v0.14.1.

### BUG-001: Lightbox Arrow Buttons Disappear After First Photo — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — event delegation pattern, 16 regression tests
**Root cause**: JS event handlers bound directly to DOM nodes that HTMX swapped out. Fix: global event delegation via `data-action` attributes on `document`.

### BUG-002: Face Count Label Incorrect in Photo View — FIXED
**Fixed**: 2026-02-08 (v0.11.0)
**Root cause**: Count read from raw detection results, not filtered/displayed faces. Fix: count matches visible face boxes.

### BUG-003: Merge Direction Bug — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — `resolve_merge_direction()` with 18 direction-specific tests
**Root cause**: Already fixed in code before investigation. Tests confirmed auto-correction working.

### BUG-004: Collection Stats Inconsistency — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — canonical `_compute_sidebar_counts()`, 11 regression tests
**Root cause**: 4 inline computations with inconsistent logic. Fix: single canonical function.

### BUG-005: Face Count Badges Wildly Wrong — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — filter to registered faces from photo_index.json, 5 tests
**Root cause**: Badge denominator used raw embedding count (63 for a 3-person newspaper photo).

### BUG-006: Photo Navigation Dies After Few Clicks — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — removed duplicate keydown handler, 6 tests

### BUG-007: Logo Doesn't Link Home — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — wrapped in `<a href="/">`, 2 tests

### BUG-008: Client-Side Fuzzy Search Not Working — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — JS Levenshtein distance added, 4 tests

---

## 2. FRONT-END / UX

### 2.1 Navigation & Lightbox (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-001 | Fix lightbox arrows (BUG-001) | DONE | Fixed 2026-02-08 via event delegation + 16 regression tests |
| FE-002 | Keyboard arrow navigation in Match Mode | DONE | Y/N/S for same/different/skip (2026-02-08) |
| FE-003 | Universal keyboard shortcuts | DONE | Consolidated global handler for all views (2026-02-08) |
| FE-004 | Consistent lightbox across all sections | DONE | Consolidated #photo-lightbox into #photo-modal (2026-02-08) |
| FE-005 | Swipe navigation on mobile | IMPLEMENTED | Phase 3 (commit d1d14c8). Needs real-device testing. |

### 2.2 Mobile Experience (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-010 | Mobile sidebar — hamburger menu or slide-over | DONE | Fixed 2026-02-06 |
| FE-011 | Bottom tab navigation on mobile | DONE | Photos/Confirmed/Inbox/Search tabs, 6 tests (2026-02-08) |
| FE-012 | Touch targets ≥44px | IMPLEMENTED | Phase 3. Needs real-device verification. |
| FE-013 | Mobile-optimized face cards | IMPLEMENTED | Stacked layout. Needs testing. |
| FE-014 | Responsive photo grid | DONE | 2-col mobile, 4-col desktop (2026-02-06) |
| FE-015 | Mobile match mode — vertical stacking with swipe | DONE | 2026-02-06 |

### 2.3 Face Tagging & Overlays (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-020 | Face overlay color system | IMPLEMENTED | Green=confirmed, indigo=proposed, amber=skipped, red=rejected, dashed=unreviewed (commit 905441e). |
| FE-021 | Photo completion badges on gallery thumbnails | IMPLEMENTED | Green "✓ N", amber "M/N", red "N ⚠" (commit 905441e). |
| FE-022 | Inline confirm/skip/reject from photo view | DONE | Hover-visible icon buttons on face overlays, 17 tests (2026-02-08) |
| FE-023 | Single tag dropdown (no multiple simultaneous) | DONE | Commit bf6a99c. |
| FE-024 | "+ Create New Identity" in autocomplete | DONE | Commit bf6a99c. |
| FE-025 | Face count label bug (BUG-002) | DONE | Fixed 2026-02-08, count matches visible boxes |

### 2.4 Search & Discoverability (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-030 | Global search improvements | DONE | Client-side instant name search with 150ms debounce (2026-02-08) |
| FE-031 | Fast name lookup with typeahead | DONE | Instant-filter in sidebar (2026-02-08) |
| FE-032 | Search result navigation | DONE | Hash fragment scroll + 2s highlight animation (2026-02-08) |
| FE-033 | Fuzzy name search | DONE | Levenshtein edit distance, "Capeluto" finds "Capelouto", 11 tests (2026-02-08) |
| FE-034 | Search results highlighting | DONE | Matched portion highlighted in amber (2026-02-08) |

### 2.5 Skipped Faces Workflow (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-040 | Surface skipped faces to other users | OPEN | After first-pass admin review, skipped faces should be visible to logged-in users for identification. |
| FE-041 | "Help Identify" mode for non-admin users | OPEN | Browse skipped faces, propose names. Admin reviews proposals. |
| FE-042 | Re-surface skips when new photos/faces are added | OPEN | If new photo processing clusters a face near a skipped identity, surface that skip with new context. |
| FE-043 | Skipped section should show ML suggestions | OPEN | If the system has any similar confirmed identities for a skipped face, show those as hints. |

### 2.6 Landing Page & Onboarding (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-050 | Welcome/about landing page | DONE | Heritage photos, community explanation (2026-02-06) |
| FE-051 | Interactive hero with real archive photos | DONE | Carousel with real archive photos (2026-02-06) |
| FE-052 | First-time user welcome modal | DONE | Session-based welcome modal with archive overview and "Got it" dismiss (2026-02-10) |
| FE-053 | Progress dashboard | DONE | "X of Y faces identified" with percentage and help CTA, 5 tests (2026-02-08) |

### 2.7 Workflow Speed & First-Time Value (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-060 | Time-to-first-value for new users | OPEN | A new visitor should be able to do something meaningful (browse, identify a face they recognize) within 30 seconds. |
| FE-061 | Quick Compare from Find Similar | OPEN | Side-by-side view with [Merge] [Not Same] buttons. Currently too many clicks. |
| FE-062 | Batch confirmation for obvious matches | OPEN | When ML is >95% confident across multiple matches, show them as a reviewable batch. |
| FE-063 | Browser performance audit | OPEN | Use Claude Code with browser plugin to stress test page load, navigation speed, HTMX swap latency. |
| FE-064 | Preload adjacent photos in gallery | PARTIAL | Implemented in Phase 2. Verify it's actually improving perceived performance. |

### 2.8 User Analytics & Logging (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-070 | Client-side event logging | OPEN | Track page views, click targets, time-on-page, navigation patterns for all users (logged in or not). |
| FE-071 | Session recording / heatmaps | OPEN | Consider lightweight analytics (Plausible, PostHog, or custom). Privacy-respecting — no PII. |
| FE-072 | Admin analytics dashboard | OPEN | How many people visited, how long they stayed, what they clicked, conversion (view → identify). |
| FE-073 | Action logging for admin review | PARTIAL | Decision logging with timestamps exists (Phase 3). Needs admin UI to review audit trail. |

---

## 3. BACKEND / DATA ARCHITECTURE

### 3.1 Merge System Redesign (CRITICAL)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-001 | Direction-aware merge | DONE | `resolve_merge_direction()` + 18 direction tests (2026-02-08) |
| BE-002 | Non-destructive merge history | DONE | Every merge creates reversible record with full audit trail (2026-02-10) |
| BE-003 | Detach with full restoration | DONE | Undo restores pre-merge state from merge history (2026-02-10) |
| BE-004 | Named conflict resolution | DONE | resolve_merge_direction() handles named→named with auto-correction (2026-02-10) |
| BE-005 | Merge audit log | DONE | source_snapshot + target_snapshot_before in merge_history entries (2026-02-10) |
| BE-006 | Extensible merge architecture | DONE | _merge_annotations() retargets annotations on merge (2026-02-10) |

### 3.2 Data Model Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-010 | Structured identity names | DONE | `rename_identity()` auto-parses first_name/last_name from display name (2026-02-10) |
| BE-011 | Identity metadata | DONE | `set_metadata()` with allowlisted keys (birth_year, death_year, birth_place, maiden_name, bio, etc.) + API endpoint (2026-02-10) |
| BE-012 | Photo metadata | DONE | PhotoRegistry set_metadata/get_metadata, display on photo view, admin endpoint (2026-02-10) |
| BE-013 | EXIF extraction | DONE | core/exif.py — extract_exif() for date, camera, GPS with deferred PIL imports (2026-02-10) |
| BE-014 | Canonical name registry | OPEN | Backend table mapping variant spellings to canonical forms: `{capeluto, capelouto, capelluto} → Capeluto`. Same for first names: `{joseph, giuseppe, jose, joe} → Joseph`. |
| BE-015 | Geographic data model | OPEN | Locations as structured data: `{city, region, country, coordinates}` with fuzzy matching. "Rhodesli" = Rhodes, Greece. "Salonika" = Thessaloniki, Greece. |
| BE-016 | Temporal data handling | OPEN | Support approximate dates: "circa 1945", "1950s", "between 1948-1952". Not just ISO dates. |

### 3.3 Data Sync & Export (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-020 | Admin data export endpoint | DONE | Token-authenticated sync API `/api/sync/*` (2026-02-10, v0.14.0) |
| BE-021 | Production → Local sync script | DONE | `scripts/sync_from_production.py` with --dry-run, auto-backup, diff summary (2026-02-10) |
| BE-022 | Staged upload download pipeline | DONE | `GET /api/sync/staged`, download/{path}, `POST clear`. `scripts/download_staged.py`, `scripts/process_uploads.sh` (2026-02-10, v0.15.0) |
| BE-023 | Backup automation | DONE | `scripts/backup_production.sh` — timestamped backups, auto-cleans to last 10 (2026-02-10) |

### 3.4 Photo Upload Pipeline (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-030 | Upload currently admin-only | DONE | Locked down in session. TODO: revert when moderation queue exists. |
| BE-031 | Upload moderation queue | OPEN | Admin approval before photos enter the archive. File size limits, rate limiting. |
| BE-032 | Web-based ML processing | OPEN | Currently ML runs locally only. Eventually: upload → background queue → processing → notification. |
| BE-033 | Batch upload | OPEN | Upload multiple photos at once with shared collection assignment. |
| BE-034 | Duplicate detection | OPEN | Hash-based detection to prevent uploading the same photo twice. |

### 3.5 Database Migration (LONG-TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-040 | PostgreSQL migration | PLANNED | JSON files won't scale past ~500 photos. Move to Supabase Postgres. |
| BE-041 | Schema design | OPEN | Tables: identities, faces, photos, collections, merge_history, annotations, name_variants, actions_log. |
| BE-042 | Migration script | OPEN | Zero-downtime migration from JSON to Postgres with data validation. |

---

## 4. ML / DATA SCIENCE

### 4.1 ML Feedback Loop (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-001 | User actions don't improve predictions | OPEN | Merges, rejects, confirms generate no signal back to the ML pipeline. The system generates embeddings once and never learns from human corrections. |
| ML-002 | Rejection memory (AD-004) | VERIFIED | "Not Same" pairs are stored and excluded from future suggestions. Commit 8042c85 verified working. |
| ML-003 | Confirmed matches → golden set | PARTIAL | Golden set exists but needs automated rebuild when new confirmations happen. |
| ML-004 | Dynamic threshold calibration | DONE | AD-013: four-tier system (VERY_HIGH/HIGH/MODERATE/LOW) from golden set evaluation (2026-02-09) |
| ML-005 | Post-merge re-evaluation | DONE | After merge, nearby HIGH+ faces shown inline for immediate review (2026-02-10) |
| ML-006 | Ambiguity detection | DONE | Margin-based flagging when top two matches within 15% distance. Family resemblance surfaced as ambiguous (2026-02-10) |

### 4.2 Golden Set & Evaluation (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-010 | Golden set rebuild | DONE | 90 mappings, 23 identities (2026-02-09) |
| ML-011 | Golden set diversity | DONE | scripts/analyze_golden_set.py + dashboard section showing identity distribution, collection coverage (2026-02-10) |
| ML-012 | Golden set evaluation | DONE | 4005 pairwise comparisons, distance sweep 0.50-2.00 (2026-02-09) |
| ML-013 | Evaluation metrics dashboard | DONE | `/admin/ml-dashboard` — identity stats, golden set results, calibrated thresholds, recent actions (2026-02-10) |

### 4.3 Clustering & Matching (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-020 | AD-001 violation fixed | DONE | `cluster_new_faces.py` now uses multi-anchor (commit b792859). |
| ML-021 | Confidence labeling | DONE | Four-tier calibrated labels: VERY_HIGH/HIGH/MODERATE/LOW (2026-02-09, AD-013) |
| ML-022 | Temporal priors | EXISTS | Code has temporal priors but undocumented. Need AD entry and validation. |
| ML-023 | Age-aware matching | OPEN | Same person as child vs adult is the hardest case in heritage archives. Consider embedding augmentation or age-estimation preprocessing. |
| ML-024 | Photo quality weighting | EXISTS | PFE sigma handles quality automatically (AD-010). Verify it's working as expected on damaged/faded photos. |

### 4.4 Model Evaluation (LONG-TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-030 | ArcFace comparison | OPEN | Evaluate ArcFace against current AdaFace PFE using golden set. May improve on old/damaged photos. |
| ML-031 | Ensemble approach | OPEN | Run multiple models and combine scores. Higher accuracy but slower. Only worth it if single-model accuracy plateaus. |
| ML-032 | Fine-tuning feasibility | OPEN | With enough confirmed identities (~100+), could fine-tune on this specific archive's characteristics. |

---

## 5. ANNOTATION ENGINE

### 5.1 Photo-Level Annotations (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-001 | Annotation system core | DONE | Submit/review/approve/reject workflow with name suggestions and confidence levels (2026-02-10) |
| AN-002 | Date metadata | DONE | Photo annotation type "date" in _photo_annotations_section() (2026-02-10) |
| AN-003 | Location metadata | DONE | Photo annotation type "location" in _photo_annotations_section() (2026-02-10) |
| AN-004 | Event/occasion | DONE | Photo metadata "occasion" field + annotation support (2026-02-10) |
| AN-005 | Source/donor attribution | DONE | Photo annotation type "source" + metadata "donor" field (2026-02-10) |
| AN-006 | Story/narrative | DONE | Photo annotation type "story" with textarea input (2026-02-10) |
| AN-007 | Photo notes (admin) | IMPLEMENTED | Notes field exists (commit 7d28042). Needs expansion. |

### 5.2 Identity-Level Annotations (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-010 | Structured name fields | DONE | See BE-010 (2026-02-10) |
| AN-011 | Birth/death dates and places | DONE | See BE-011 (2026-02-10) |
| AN-012 | Biographical notes | DONE | _identity_metadata_display() shows bio, birth/death, birthplace on identity cards (2026-02-10) |
| AN-013 | Relationships | DONE | _identity_annotations_section() with relationship annotation type + display (2026-02-10) |
| AN-014 | Generation tracking | DONE | Annotation + metadata system supports generation via relationship_notes (2026-02-10) |

### 5.3 Genealogical Data (LONG-TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-020 | Family tree integration | PLANNED | Visual tree display linking identities by relationships. |
| AN-021 | GEDCOM import/export | PLANNED | Standard genealogy interchange format. |
| AN-022 | Cross-reference with genealogy databases | OPEN | Link to Ancestry, FamilySearch, JewishGen records. |
| AN-023 | Timeline view | OPEN | Show photos chronologically, with identity appearances marked. |

---

## 6. INFRASTRUCTURE & OPS

### 6.1 Deployment & DevOps (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| OPS-001 | Custom SMTP for email | OPEN | Emails come from "Supabase Auth". Need Resend/SendGrid for branded "Rhodesli" sender. Template update script exists (`scripts/update_email_templates.sh`). |
| OPS-002 | CI/CD pipeline | OPEN | Automated tests on push, staging environment, deploy previews. |
| OPS-003 | Health monitoring | PARTIAL | `/health` endpoint exists. Need uptime monitoring (UptimeRobot or similar). |
| OPS-004 | Error tracking | OPEN | Sentry or similar for catching production errors. |
| OPS-005 | Railway volume backups | OPEN | Automated backup of `data/` from Railway volume. |

### 6.2 Performance (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| OPS-010 | Page load speed audit | OPEN | Measure TTFB, LCP, CLS on key pages. R2 serves images directly (OD-004) which helps. |
| OPS-011 | Image optimization | OPEN | Serve appropriately sized thumbnails for gallery (not full-res). Currently loading full images for grid view. |
| OPS-012 | HTMX swap performance | OPEN | Measure swap latency on lightbox transitions, face card loads, merge operations. |
| OPS-013 | Caching strategy | OPEN | Static assets, photo metadata, identity data — what can be cached and for how long? |

---

## 7. TESTING & QUALITY

### 7.1 Current Test Coverage

1032 tests passing (v0.17.0) across:
- `tests/test_auth.py` — auth flow tests
- `tests/test_permissions.py` — permission matrix tests
- `tests/test_ui_elements.py` — UI content tests
- `tests/test_photo_context.py` — photo display tests
- `tests/test_regression.py` — regression guards
- `tests/test_lightbox.py` — 16 lightbox regression tests (BUG-001)
- `tests/test_merge_direction.py` — 18 merge direction tests (BUG-003)
- `tests/test_face_count.py` — face count accuracy tests (BUG-002, BUG-005)
- `tests/test_skipped_faces.py` — 9 skipped face tests (v0.14.1)
- `tests/test_sync_api.py` — 12 sync API permission matrix tests (v0.14.0)
- `tests/e2e/` — Playwright E2E tests (19 critical path tests)
- Plus many more across ~30 test files

### 7.2 Testing Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| QA-001 | Lightbox regression tests | DONE | 16 tests covering arrow rendering, HTMX swaps, event delegation (2026-02-08) |
| QA-002 | Merge direction tests | DONE | 18 tests: unnamed→named, named→unnamed, named→named (2026-02-08) |
| QA-003 | Face count accuracy tests | DONE | Count matches visible boxes, not raw detection (2026-02-08) |
| QA-004 | End-to-end browser tests | DONE | Playwright + Chromium, 19 critical path tests (2026-02-08) |
| QA-005 | Mobile viewport tests | OPEN | Test at 375px, 414px, 768px widths. Verify sidebar hidden, bottom tabs visible, touch targets adequate. |
| QA-006 | Claude Code UX walkthrough | OPEN | Use Claude Code with browser plugin to simulate user workflows and identify friction. |
| QA-007 | Performance benchmarking | OPEN | Automate page load measurements, set thresholds, fail tests if degraded. |

### 7.3 Meta: Reducing Bug Recurrence (PROCESS)

We've been battling the same bugs repeatedly (lightbox arrows fixed 3 times, multi-merge fixed 3 times, collection stats fixed 3 times). Root causes:

1. **Tests are server-side only** — they test HTTP responses but not the actual browser behavior (HTMX swaps, JS event handlers, CSS rendering). A test can pass while the feature is visually broken.
2. **HTMX lifecycle is tricky** — elements that work on initial page load break after HTMX swaps because JS event handlers aren't re-bound. Need a pattern for HTMX-aware JS initialization.
3. **No visual regression testing** — CSS changes and responsive behavior can't be caught by server-side tests.

**Recommended mitigations**:
- Add Playwright E2E tests for critical workflows (photo navigation, merge, Focus mode)
- Use HTMX's `htmx:afterSwap` event consistently for JS re-initialization
- Add a "smoke test" script that Claude Code runs after each change: load key pages in a headless browser and screenshot them
- Before declaring any bug "fixed," require: (a) a test that reproduces the bug, (b) the fix, (c) the test passes, (d) manual verification on the live site

---

## 8. DOCUMENTATION & HARNESS

### 8.1 Internal Documentation (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| DOC-001 | CLAUDE.md audit | OPEN | Currently ~78 lines. Best practices say keep it short but ensure it's not bloated with rules Claude ignores. Prune regularly. |
| DOC-002 | Path-scoped rules review | DONE | `.claude/rules/` for ML, data, deployment, planning. |
| DOC-003 | ALGORITHMIC_DECISIONS.md up to date | PARTIAL | AD-001 through AD-012. AD-001 violation fixed. Need entries for temporal priors, detection threshold. |
| DOC-004 | OPS_DECISIONS.md up to date | DONE | OD-001 through OD-005. |
| DOC-005 | Auto-update documentation rule | DONE | CLAUDE.md now has dual-update rule for ROADMAP + BACKLOG + CHANGELOG (2026-02-10) |
| DOC-006 | Living lessons.md | DONE | 46+ lessons. Keep adding. |

### 8.2 User-Facing Documentation (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| DOC-010 | In-app help / FAQ | OPEN | "How do I identify someone?", "What does Skip mean?", "How does the matching work?" |
| DOC-011 | About page | OPEN | History of the Rhodesli community, purpose of the archive, how to contribute. |
| DOC-012 | Admin guide | OPEN | How to process uploads, run ML, review matches, manage identities. |
| DOC-013 | Contributor onboarding | OPEN | Instructions for family members: how to sign up, browse, help identify, upload. |

### 8.3 Harness Engineering Best Practices

Based on research of latest Claude Code patterns (Feb 2026):

- **CLAUDE.md should be concise** — frontier models can follow ~150-200 instructions. Our system prompt already uses ~50. Keep CLAUDE.md to only universally applicable rules.
- **Use @imports** for detailed docs: `See @docs/ml/ALGORITHMIC_DECISIONS.md for ML design decisions`
- **Path-scoped rules** load domain context only when relevant — zero token cost for unrelated work
- **Skills > CLAUDE.md** for domain-specific workflows that aren't always needed
- **Subagents for parallel work** — up to 10 parallel, each with own context window. Use Explore (read-only) for research, general-purpose for implementation.
- **Tasks for coordination** — dependency graphs, background execution, persistent state across sessions
- **Hooks for quality gates** — run linter/formatter/tests automatically after changes
- **Commit after every phase** — non-negotiable for overnight/unattended sessions

---

## 9. USER ROLES & COLLABORATION

### 9.1 Permission Model Evolution (MEDIUM-LONG TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ROLE-001 | Current: Public=view, Admin=all | DONE | Locked down. |
| ROLE-002 | Contributor role | DONE | User model has role field (admin/contributor/viewer), CONTRIBUTOR_EMAILS env var, _check_contributor() helper (2026-02-10) |
| ROLE-003 | Trusted contributor | DONE | is_trusted_contributor() auto-promotes users with 5+ approved annotations (2026-02-10) |
| ROLE-004 | Family member self-identification | OPEN | "That's me!" button on face cards. Special trust level for self-ID. |
| ROLE-005 | Activity feed | DONE | `/activity` route with action log + approved annotations (2026-02-10) |
| ROLE-006 | Email notifications | OPEN | "Someone identified a face in your uploaded photo", "New photos added to the archive." |

---

## 10. LONG-TERM VISION

### 10.1 Generalization (IF TRACTION)

| ID | Item | Notes |
|----|------|-------|
| GEN-001 | Multi-tenant architecture | Per-community isolation. Each community gets their own archive. |
| GEN-002 | Self-service community creation | "Start your own heritage archive" workflow. |
| GEN-003 | Cross-community discovery | Optional: "Someone in another archive might be related to this person." |
| GEN-004 | White-label / embedding | Let organizations embed the photo identification UI in their own sites. |

### 10.2 AI Enhancements

| ID | Item | Notes |
|----|------|-------|
| AI-001 | Auto-caption generation | Use vision models to describe photo content: "Group of people at a formal dinner." |
| AI-002 | Photo era estimation | ML model to estimate decade from visual cues (clothing, film grain, color palette). |
| AI-003 | Photo restoration | AI-powered cleanup of damaged/faded photos. |
| AI-004 | Handwriting recognition | For photos with text on the back (common in old archives). |
| AI-005 | Story generation | Given a set of photos of the same person across decades, generate a biographical narrative draft. |

---

## 11. PRIORITIZED EXECUTION PLAN

### Phase A: Stabilization — COMPLETE (2026-02-08)
All 8 bugs fixed (BUG-001 through BUG-008). 103+ new tests. Event delegation pattern established.

### Phase B: Share-Ready Polish — MOSTLY COMPLETE (2026-02-06 → 2026-02-10)
**Done**: FE-050/051/053 (landing page), FE-030/031/033/034 (search), FE-010/011/014/015 (mobile), BE-020/021/022/023 (sync + staged upload pipeline).
**Remaining**: FE-052 (guided tour), OPS-001 (branded email).

### Phase C: Annotation Engine (2-3 sessions)
**Goal**: Make the archive meaningful beyond face matching.

1. BE-010–BE-016: Data model for names, dates, locations
2. AN-001–AN-007: Photo-level annotations
3. AN-010–AN-014: Identity-level annotations
4. BE-001–BE-006: Non-destructive merge system
5. FE-033: Fuzzy name search with canonical names

### Phase D: ML Feedback & Intelligence (1-2 sessions)
**Goal**: Make the system learn from user actions.

1. ML-001–ML-006: Feedback loop implementation
2. ML-010–ML-013: Golden set expansion and evaluation
3. ML-020–ML-024: Clustering improvements
4. FE-040–FE-043: Skipped faces workflow

### Phase E: Collaboration & Growth (2-3 sessions)
**Goal**: Enable family members to contribute, not just browse.

1. ROLE-002–ROLE-003: Contributor roles
2. FE-041: "Help Identify" mode
3. FE-070–FE-073: Analytics and logging
4. BE-031–BE-033: Upload moderation queue
5. ROLE-005–ROLE-006: Activity feed and notifications

### Phase F: Scale & Generalize (Ongoing)
1. BE-040–BE-042: PostgreSQL migration
2. AN-020–AN-023: Family tree / GEDCOM
3. OPS-002: CI/CD pipeline
4. ML-030–ML-032: Model evaluation and improvement
5. GEN-001+: Multi-tenant if traction

---

## Appendix: Key Files & References

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Claude Code harness (with dual-update rules) |
| `.claude/rules/*.md` | Path-scoped rules (ML, data, deployment, planning) |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-001 through AD-012 |
| `docs/ml/MODEL_INVENTORY.md` | Current model stack |
| `docs/ops/OPS_DECISIONS.md` | OD-001 through OD-005 |
| `tasks/todo.md` | Session-level task tracking |
| `tasks/lessons.md` | 46+ accumulated lessons |
| `data/identities.json` | Identity data (Railway volume) |
| `data/photo_index.json` | Photo metadata |
| `data/embeddings.npy` | Face embeddings (~550 faces) |
| `data/golden_set.json` | ML evaluation baseline |
| `data/clustering_report_2026-02-07.txt` | 35 proposed matches |

## Appendix: Lessons That Should Inform Future Work

1. **Every UX bug found in manual testing is a missing automated test.** Write the test that would have caught it.
2. **Permission regressions are the most dangerous bugs.** Always test the full route × auth-state matrix.
3. **HTMX endpoints behave differently than browser requests** (401 vs 303). Test both.
4. **Algorithmic decisions need structured logs** separate from operational lessons.
5. **Never average embeddings** (AD-001) — heritage archives span decades; centroids create ghost vectors.
6. **Default to admin-only for new data-modifying features.** Loosen permissions only when moderation/guardrails are in place.
7. **Path-scoped rules are free** when not triggered. Use them liberally for domain context.
8. **Commit after every phase** — non-negotiable for overnight/unattended sessions.
9. **JSON won't scale.** Plan the Postgres migration before hitting 500 photos.
10. **Family resemblance is the hardest problem.** Capelutos matching other Capelutos will require relative-distance scoring, not just absolute thresholds.
