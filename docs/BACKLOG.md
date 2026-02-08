# Rhodesli: Comprehensive Project Backlog & Improvement Plan

**Version**: 2.0 — February 8, 2026
**Status**: 663 tests passing, v0.10.0, 148 photos, 23 confirmed identities, 181 total faces
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). Auth is complete with Google OAuth, invite codes, and a locked-down permission model (public=view, admin=everything else). Two overnight Claude Code sessions have delivered the core UX, ML pipeline, and testing infrastructure.

---

## 1. ACTIVE BUGS (Fix Immediately)

### BUG-001: Lightbox Arrow Buttons Disappear After First Photo
**Reported**: Sessions 10, 11 (twice)
**Status**: Claimed fixed in Phase 2 (commit 55fea1e) and again in Phase 1 (commit 50e5dc4), but still broken per user testing today
**Symptom**: First photo in gallery shows right arrow. All subsequent photos lack left/right arrows for mouse navigation. Only keyboard arrows (← →) work.
**Impact**: HIGH — mouse users (older family members especially) have no way to navigate between photos after the first one.
**Root cause hypothesis**: The lightbox JS likely binds arrow buttons to the initial photo element but fails to re-render or re-bind after HTMX swaps the photo content. Needs investigation of the `photoNavTo` function and HTMX swap lifecycle.

### BUG-002: Face Count Label Incorrect in Photo View
**Reported**: This session (Feb 8)
**Screenshot evidence**: Photo `603575393.720025.jpg` shows "6 faces detected" but only 2 face boxes are visible, and user has confirmed all faces are tagged.
**Impact**: MEDIUM — confusing label undermines trust in the system
**Root cause hypothesis**: The face count is likely reading from the original detection results (which may have found 6 low-confidence faces) rather than the number of faces actually displayed after filtering. The display filters by detection confidence, but the count label doesn't apply the same filter.

### BUG-003: Merge Direction Bug (Unidentified → Named Overwrites Named Data)
**Reported**: Session 10, confirmed still present
**Status**: Discussed extensively but never fixed
**Symptom**: When merging from Focus Mode (which always starts with an unidentified person), doing Find Similar → Merge to a named identity overwrites the named person's data with the unidentified person's data. This makes Focus Mode effectively broken for its primary use case.
**Impact**: CRITICAL — makes the primary tagging workflow destructive
**Required fix**: Merge must always preserve the richer identity's data. When merging A into B, the result should keep whichever has a name, more faces, more metadata. If both have names, prompt for conflict resolution.

### BUG-004: Collection Stats Inconsistency
**Reported**: Sessions 10, 11 (three times)
**Status**: Claimed fixed but persists
**Symptom**: Photo gallery shows inconsistent collection statistics — denominator mismatches, incorrect photo counts.

---

## 2. FRONT-END / UX

### 2.1 Navigation & Lightbox (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-001 | Fix lightbox arrows (BUG-001) | OPEN | Third attempt needed. Write 5 regression tests BEFORE fixing. |
| FE-002 | Keyboard arrow navigation in Match Mode | OPEN | Should switch between the two photos being compared. Currently only works in photo gallery. |
| FE-003 | Universal keyboard shortcuts | PARTIAL | C/S/R/F work in Focus Mode. Need ← → everywhere photos appear (Match, Focus, Photo view, Inbox face cards). |
| FE-004 | Consistent lightbox across all sections | PARTIAL | Photos section has it. Inbox face cards, Focus Mode, Match Mode need the same component. |
| FE-005 | Swipe navigation on mobile | IMPLEMENTED | Phase 3 (commit d1d14c8). Needs real-device testing. |

### 2.2 Mobile Experience (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-010 | Sidebar hidden in mobile portrait | REPORTED | Session 10 — no hamburger menu or slide-over. |
| FE-011 | Bottom tab navigation on mobile | OPEN | Replace sidebar with bottom tabs: Inbox, Photos, Confirmed, Search. |
| FE-012 | Touch targets ≥44px | IMPLEMENTED | Phase 3. Needs real-device verification. |
| FE-013 | Mobile-optimized face cards | IMPLEMENTED | Stacked layout. Needs testing. |
| FE-014 | Responsive photo grid | OPEN | 2-column on mobile, 4-column on desktop. Currently shrinks desktop grid. |
| FE-015 | Mobile match mode | OPEN | Side-by-side comparison doesn't work on narrow screens. Stack vertically with swipe. |

### 2.3 Face Tagging & Overlays (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-020 | Face overlay color system | IMPLEMENTED | Green=confirmed, indigo=proposed, amber=skipped, red=rejected, dashed=unreviewed (commit 905441e). |
| FE-021 | Photo completion badges on gallery thumbnails | IMPLEMENTED | Green "✓ N", amber "M/N", red "N ⚠" (commit 905441e). |
| FE-022 | Inline confirm/skip/reject from photo view | OPEN | Currently must go to face card. Should be able to act directly on face overlays. |
| FE-023 | Single tag dropdown (no multiple simultaneous) | IMPLEMENTED | Commit bf6a99c. |
| FE-024 | "+ Create New Identity" in autocomplete | IMPLEMENTED | Commit bf6a99c. |
| FE-025 | Face count label bug (BUG-002) | OPEN | Shows detection count, not displayed/tagged count. |

### 2.4 Search & Discoverability (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-030 | Global search across all surfaces | PARTIAL | "Search names..." exists in sidebar but behavior unclear across sections. |
| FE-031 | Fast name lookup in Confirmed section | OPEN | Need instant-filter / typeahead. With 23 identities it's manageable; at 100+ it's critical. |
| FE-032 | Search by collection, date, location | OPEN | Currently only filter by collection in Photos URL params. |
| FE-033 | Fuzzy name search | OPEN | "Capeluto" should match "Capelouto", "Capelluto". "Joseph" should match "Giuseppe", "Jose", "Joe". Requires canonical name backend (see DATA-010). |
| FE-034 | Search results highlighting | OPEN | Show which part of the name matched and why. |

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
| FE-050 | Welcome/about landing page | OPEN | Currently dumps users into Inbox. Needs a page explaining what Rhodesli is, showing sample photos, and guiding users to start. |
| FE-051 | Creative use of heritage photos | OPEN | Interactive hero with real archive photos — carousel, fade transitions, or mosaic. Make the landing emotionally compelling. |
| FE-052 | First-time user guided tour | OPEN | Step-by-step overlay highlighting: browse photos, see faces, help identify, upload your own. |
| FE-053 | Progress dashboard | OPEN | "23 of 181 faces identified" is buried in footer. Make it a prominent community progress indicator. |

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
| BE-001 | Direction-aware merge | OPEN | Always preserve richer identity. Never overwrite named with unnamed. See BUG-003. |
| BE-002 | Non-destructive merge history | OPEN | Every merge creates a reversible record: `{merged_from, merged_into, timestamp, actor, previous_state}`. |
| BE-003 | Detach with full restoration | OPEN | Undo a merge by restoring the pre-merge state from the merge history record. |
| BE-004 | Named conflict resolution | OPEN | When merging two named identities (e.g., "Leon Capeluto" + "Big Leon Capeluto"), show conflict UI: pick primary name, keep both as aliases. |
| BE-005 | Merge audit log | PARTIAL | Decision logging exists. Needs structured merge-specific events with before/after snapshots. |
| BE-006 | Extensible merge architecture | OPEN | As we add annotations (dates, locations, stories), merges must also merge those fields with conflict detection. Design the merge system to handle arbitrary metadata fields. |

### 3.2 Data Model Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-010 | Structured identity names | OPEN | Currently single `name` string. Need: `{first_name, last_name, display_name, aliases[], canonical_last_name}`. |
| BE-011 | Identity metadata | OPEN | Birth date/place, death date/place, maiden name, relationships, generation. |
| BE-012 | Photo metadata | OPEN | Date taken (exact or estimated range), location, occasion/event, photographer, original source/donor, caption, story/notes. |
| BE-013 | EXIF extraction | OPEN | Auto-extract date, camera, GPS from uploaded photos where available. |
| BE-014 | Canonical name registry | OPEN | Backend table mapping variant spellings to canonical forms: `{capeluto, capelouto, capelluto} → Capeluto`. Same for first names: `{joseph, giuseppe, jose, joe} → Joseph`. |
| BE-015 | Geographic data model | OPEN | Locations as structured data: `{city, region, country, coordinates}` with fuzzy matching. "Rhodesli" = Rhodes, Greece. "Salonika" = Thessaloniki, Greece. |
| BE-016 | Temporal data handling | OPEN | Support approximate dates: "circa 1945", "1950s", "between 1948-1952". Not just ISO dates. |

### 3.3 Data Sync & Export (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-020 | Admin data export endpoint | OPEN | GET /admin/export → download current identities.json, photo_index.json. Required for local backup and sync. |
| BE-021 | Production → Local sync script | OPEN | `python scripts/sync_from_production.py` — downloads current data files from Railway. |
| BE-022 | Local → Production sync (data seeding) | EXISTS | `railway up` pushes data. But needs conflict detection if production data has diverged. |
| BE-023 | Backup automation | OPEN | Scheduled daily backup of production data to R2 or local. |

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
| ML-004 | Dynamic threshold calibration | OPEN | As more matches are confirmed/rejected, the system should learn the optimal MLS distance threshold for this specific archive (family resemblance is high). |
| ML-005 | Reclustering after merges | OPEN | When identities are merged, the new multi-anchor representation should trigger re-evaluation of nearby unidentified faces. |
| ML-006 | Family resemblance handling | OPEN | Capelutos matching other Capelutos is a known problem. Consider relative distance (is face A closer to identity X than to any other identity?) rather than absolute threshold. |

### 4.2 Golden Set & Evaluation (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-010 | Expand golden set beyond Big Leon | OPEN | Currently built from identities with ≥3 confirmed faces. As confirmations grow, the golden set should be richer and more representative. |
| ML-011 | Golden set diversity | OPEN | Need representation across: ages (child vs adult), photo quality (sharp vs blurry), decades (1940s vs 1970s), lighting conditions. |
| ML-012 | Automated golden set rebuild | PARTIAL | `scripts/build_golden_set.py` exists. Should run automatically after N new confirmations. |
| ML-013 | Evaluation metrics dashboard | OPEN | After each golden set rebuild, report: precision, recall, F1 by distance band. Track over time to catch regressions. |

### 4.3 Clustering & Matching (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-020 | AD-001 violation fixed | DONE | `cluster_new_faces.py` now uses multi-anchor (commit b792859). |
| ML-021 | Confidence labeling | OPEN | Clustering report marks everything [HIGH]. Need calibrated labels: [VERY HIGH] <0.70, [HIGH] 0.70-0.80, [MODERATE] 0.80-0.90, [LOW] 0.90-1.00. |
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
| AN-001 | Photo captions | OPEN | Free-text caption field on each photo. |
| AN-002 | Date metadata | OPEN | Date taken, with support for approximate dates ("circa 1945", "1950s"). |
| AN-003 | Location metadata | OPEN | Where the photo was taken. Structured + free-text. |
| AN-004 | Event/occasion | OPEN | "Wedding", "Passover Seder", "Beach outing", etc. |
| AN-005 | Source/donor attribution | OPEN | Who contributed this photo to the archive. |
| AN-006 | Story/narrative | OPEN | Longer-form stories attached to photos — "This was taken at Uncle Moise's house the summer before they moved to Miami..." |
| AN-007 | Photo notes (admin) | IMPLEMENTED | Notes field exists (commit 7d28042). Needs expansion. |

### 5.2 Identity-Level Annotations (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-010 | Structured name fields | OPEN | First, last, maiden, display name, aliases. See BE-010. |
| AN-011 | Birth/death dates and places | OPEN | See BE-011. |
| AN-012 | Biographical notes | OPEN | Free-text bio for each identity. |
| AN-013 | Relationships | OPEN | "Married to Victoria Cukran", "Father of Betty", etc. |
| AN-014 | Generation tracking | OPEN | Which generation in the family tree (for sorting/display). |

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

663 tests passing across:
- `tests/test_auth.py` — 23 auth flow tests
- `tests/test_permissions.py` — 19 permission matrix tests
- `tests/test_ui_elements.py` — 17 UI content tests
- `tests/test_photo_context.py` — photo display tests
- `tests/test_regression.py` — regression guards
- Plus ~585 tests across other files

### 7.2 Testing Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| QA-001 | Lightbox regression tests | OPEN | After 3 failed fixes, need comprehensive tests: arrow rendering on photo 1, photo 2, last photo. HTMX swap lifecycle. |
| QA-002 | Merge direction tests | OPEN | Test: unnamed→named preserves name. Named→unnamed preserves name. Named→named prompts conflict. |
| QA-003 | Face count accuracy tests | OPEN | Verify displayed count matches visible face boxes, not raw detection count. |
| QA-004 | End-to-end browser tests | OPEN | Playwright or Selenium for actual browser testing. Current tests are server-side only. |
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
| DOC-005 | Auto-update documentation rule | OPEN | Add to CLAUDE.md: "When any change affects user-facing behavior, update relevant docs (CHANGELOG, README, in-app help)." |
| DOC-006 | Living lessons.md | DONE | 33 lessons. Keep adding. |

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
| ROLE-002 | Contributor role | OPEN | Can propose identifications (admin reviews). Can add annotations. Cannot merge/detach. |
| ROLE-003 | Trusted contributor | OPEN | Can confirm identifications directly (no admin review). Earned after N correct proposals. |
| ROLE-004 | Family member self-identification | OPEN | "That's me!" button on face cards. Special trust level for self-ID. |
| ROLE-005 | Activity feed | OPEN | Show recent identifications, uploads, merges to encourage participation. |
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

### Phase A: Stabilization (Next Session — ~2-3 hours)
**Goal**: Fix all active bugs, get site stable enough to share.

1. BUG-001: Lightbox arrows (tests-first approach)
2. BUG-002: Face count label
3. BUG-003: Merge direction (CRITICAL — blocks Focus Mode workflow)
4. BUG-004: Collection stats
5. FE-001–FE-004: Navigation consistency
6. Smoke test all fixes on live site

### Phase B: Share-Ready Polish (Following Session — ~2-3 hours)
**Goal**: Landing page, search, mobile — make it ready for family members.

1. FE-050–FE-053: Landing page and onboarding
2. FE-030–FE-031: Search improvements
3. FE-010–FE-015: Mobile responsive polish
4. OPS-001: Branded email
5. BE-020–BE-021: Admin data export/sync

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
| `CLAUDE.md` | Claude Code harness (~78 lines) |
| `.claude/rules/*.md` | Path-scoped rules (ML, data, deployment, planning) |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-001 through AD-012 |
| `docs/ml/MODEL_INVENTORY.md` | Current model stack |
| `docs/ops/OPS_DECISIONS.md` | OD-001 through OD-005 |
| `tasks/todo.md` | Authoritative backlog (superseded by this document) |
| `tasks/lessons.md` | 33 accumulated lessons |
| `data/identities.json` | Identity data (Railway volume) |
| `data/photo_index.json` | Photo metadata |
| `data/embeddings.npy` | Face embeddings (547 faces) |
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
