# Session 94 Context: Housekeeping + Fox Family Planning

Predecessor: [Session 93 Context](session-93-context.md)

## Background

Session 94 follows an ad-hoc planning conversation (2026-03-09) that produced:
- PRD-034: Standalone Tool Suite (consolidated PRODUCT-001 through PRODUCT-006)
- ML_SERVICE.md rewrite: reframed as operational necessity (laptop SPOF)
- Pipeline audit: local ML pipeline has run only 6 times in 4 months
- TOOLS-001 through TOOLS-005 tracking items
- Updated ROADMAP, BACKLOG, todo.md to current state

## Session Goals

### Interactive Track (Main Thread): Fox Family Collection Deep Planning
Nolan wants to flesh out the PRD/SDD for the Fox family photo collection — the
second collection to be onboarded to Rhodesli. This is an interactive planning
session where we iterate on:
- What a great MVP looks like
- What can be reused from existing infrastructure
- UX, data structure, and pipeline considerations
- What needs to be built new vs adapted

**Nolan will provide a brain dump** at session start. Claude should ask
clarifying questions, then iterate on the plan.

### Background Tracks (Parallel Worktrees): Housekeeping
While the planning conversation happens, background subagents handle:

| Track | Branch | Scope | Independent? |
|-------|--------|-------|-------------|
| A: UX Fixes | `session-94/ux-fixes` | UX-042, UX-134 (P1 bugs) | Yes |
| B: Branch Cleanup | `session-94/branch-cleanup` | Merge or close 82c branch | Yes |
| C: CI Verification | `session-94/ci-verify` | Verify GitHub Actions running | Yes |
| D: Doc Sync | `session-94/doc-sync` | BACKLOG/ROADMAP header freshness | Yes |

**Merge order:** D (docs) → C (CI) → A (UX) → B (branch cleanup)

## Technical Context

### Fox Family — What Exists Already
1. **Prep doc:** `docs/collections/fox_family_prep.md` — integration steps, challenges, rollback
2. **Multi-collection PRD:** `docs/prds/030_multi_collection.md` — schema, acceptance criteria
3. **Multi-tenant architecture:** `docs/architecture/MULTI_TENANT.md` — GlobalPersonID, R2 org
4. **AD-206:** GlobalPersonID schema decided, tables created in Supabase
5. **communities table:** Seeded with Rhodes as first entry (Session 91)
6. **community_id columns:** Added to identities/photos tables

### Fox Family — What Does NOT Exist
1. **Fox family GEDCOM file** — Nolan needs to provide or export
2. **Fox family photos** — not scanned/organized yet
3. **Collection-scoped browsing UX** — filter exists for source, not collection
4. **Per-community admin permissions** — not scoped
5. **Cross-community search** — not built
6. **R2 per-community prefixes** — designed but not implemented

### Key Questions for Nolan (Brain Dump Prompts)
1. How many photos do you estimate? What format (physical, digital, mixed)?
2. Do you have a GEDCOM file for the Fox family? What software?
3. Are there people who appear in BOTH the Fox and Capeluto/Rhodes collections?
4. Who is the target audience? Same community or different?
5. What's the geographic scope? (Rhodes collections = Mediterranean/US diaspora)
6. What date range do the Fox photos span?
7. Do you want Fox photos on the same domain or a separate instance?
8. Are there sub-collections within Fox (e.g., different branches)?
9. What metadata exists? (names written on backs, dates, locations)
10. What's the priority: getting photos online fast, or getting identifications right?

### UX-042: Shareable Identity Page Missing Source Photo Link
- **Location:** `/identify/{id}` shareable pages
- **Bug:** No link back to the source photo — critical for community onboarding
- **Files:** `app/page_routes.py` (identity page rendering)
- **Fix:** Add source photo thumbnail + link to each face on the identity page

### UX-134: Mobile Landing Page Horizontal Overflow
- **Location:** Landing page at 375px viewport
- **Bug:** scrollWidth=780, clientWidth=375 → horizontal scroll
- **Files:** `app/page_routes.py` (landing page), CSS in templates
- **Tests:** `test_mobile_landing_page[chromium]` already fails

### Session 82c Branch Status
- Branch: `session-82c/gemini-rerun`
- 14 commits of Gemini enrichment pipeline work
- Blocked by: AD numbering conflict (branch AD-194 vs main AD-194)
- Decision needed: merge with conflict resolution, or close and cherry-pick what's valuable
- Most of the work has been re-done in later sessions (89, 92, 93)

### CI Status
- `.github/workflows/test.yml` created in Session 92
- Unknown if it's actually running on pushes
- Need to verify: `gh run list` or check GitHub Actions tab

## Infrastructure State (Post-Session 93)
- **v0.96.0** deployed on Railway
- **4283 tests** passing
- **299 photos**, 894 identities, 69 confirmed
- **Postgres** is source of truth (DATA_SOURCE=postgres on Railway)
- **Observability** verified: Sentry, PostHog, Resend
- **GEDCOM** batch reanalysis complete (67/72 photos)

## Standalone Tools Strategy (From Planning Session)

The Fox family collection planning should be informed by the standalone tools
vision (PRD-034). Key insight: tools like date estimation and face comparison
should work for ANY collection, not just Rhodes. The Fox collection is the
first test of this multi-collection capability.

**Prioritized order:**
1. TOOLS-001: Date + Location Estimator Standalone (zero blockers)
2. TOOLS-002: ML Service Extraction (removes laptop dependency)
3. TOOLS-003: Face Compare Real-Time (depends on TOOLS-002)
4. TOOLS-004: NL Query + Chatbot
5. Fox Family Collection (validates multi-collection)

## Risk Assessment
- **UX fixes:** Low risk — isolated route changes
- **Branch cleanup:** Low risk — 82c work largely superseded
- **CI verification:** Low risk — read-only check
- **Fox planning:** No code risk — planning only, produces PRD/SDD

## Deferred to Future Sessions
- TOOLS-001 through TOOLS-005 implementation
- ML service extraction (TOOLS-002)
- PERF-001 (test speed)
- OPS-001 (custom SMTP)
