# Design Decisions Log

Product and UX design decisions for Rhodesli. Each entry uses DD-NNN format
with full provenance, following the same pattern as ALGORITHMIC_DECISIONS.md
(AD-NNN) and HARNESS_DECISIONS.md (HD-NNN).

For earlier design decisions (D1-D4), see: `docs/design-decisions.md`
For ML decisions, see: `docs/ml/ALGORITHMIC_DECISIONS.md`
For harness decisions, see: `docs/HARNESS_DECISIONS.md`
For ops decisions, see: `docs/ops/OPS_DECISIONS.md`

---

## DD-001: Archival Aesthetic Direction

- **Date:** 2026-02-25
- **Session:** 69 (Subagent A)
- **Status:** Decided

**What:** Playfair Display serif font for all display headings and identity names.
Warm amber/parchment color palette for card backgrounds and borders.
Three custom CSS classes for archival card styling.

**Why:** Heritage archive for a 100+ year old community deserves museum-quality
editorial feel (Lesson 84). Cold slate developer-tool aesthetic does not match
the emotional weight of the content.

**Alternatives rejected:**
- System serif (Georgia) -- lacks character
- Cormorant Garamond -- too thin at small sizes
- Full cream background -- clashed with existing dark mode

See `docs/design-decisions.md` DD-001 for full rationale.

---

## DD-002: Face Card Layout Improvements

- **Date:** 2026-02-25
- **Session:** 69 (Subagent A)
- **Status:** Decided

**What:** Compact face cards (reduced padding, denser grid), warm gradient
backgrounds, lighter sepia filter, archival border styling.

**Key changes:**
- Face grid: 2/3/4 cols -> 3/4/5/6 cols (50% more faces visible)
- Face card padding: p-2 -> p-1.5
- Sepia filter: 0.3 -> 0.15 (more face detail)
- Card backgrounds: cold slate -> warm gradient (#2a241e -> #1e1a15)

See `docs/design-decisions.md` DD-002 for full rationale and component table.

---

## DD-003: Discovery Notification UX — Badge + One-Click Confirm View

- **Date:** 2026-02-25
- **Session:** 69 (planning)
- **Status:** Implemented

### Problem

The Gatekeeper pattern (AD-097) surfaces ML proposals for admin review,
but there is no mechanism to highlight high-confidence matches that
deserve immediate attention. The admin must manually browse through all
proposals to find the ones most likely to be correct. This creates two
failure modes:

1. **High-value matches sit unreviewed** because they are buried in a
   list of hundreds of proposals with no priority signal.
2. **Admin fatigue** from reviewing low-confidence matches discourages
   engagement with the review queue entirely.

With 221 positive pairs identified (Session 68 LoRA audit) and
similarity calibration live (AUC=0.9577, AD-149), the system now has
calibrated confidence scores that can power a notification layer.

### Decision

Add a discovery notification system with two components:

1. **Notification badge** on the admin dashboard showing count of
   high-confidence proposals (cosine distance < 1.0, corresponding to
   approximately P(match) > 0.85 per calibrated score).
   Updates when new proposals are generated or when calibration model
   is updated.

2. **One-click confirm view** accessible from the badge. Shows only
   the high-confidence proposals in a streamlined review interface:
   side-by-side face crops, calibrated confidence score, identity name,
   and Accept/Reject buttons. Designed for rapid batch confirmation.

### Rationale

- Calibrated scores (AD-149) give us reliable confidence ordering.
  P(match) > 0.85 corresponds to the high-confidence region of the
  isotonic regression model.
- The Gatekeeper pattern (AD-097) is preserved: notifications are
  advisory, not auto-confirmations. Admin still makes every decision.
- Reduces time-to-confirmation for obvious matches from "whenever
  admin happens to browse proposals" to "admin sees badge, clicks,
  confirms in seconds."
- Confirmed matches feed back as ground truth anchors, improving
  both the calibration model and future LoRA fine-tuning data.

### Alternatives Considered

- **Email notifications:** Valuable for non-admin contributors but
  requires custom SMTP (OPS-001, not yet deployed). Future addition,
  not replacement. Does not help with the batch-confirm workflow.
- **Activity feed:** Shows all system events (new proposals, uploads,
  confirmations). More general but less actionable than targeted
  high-confidence alerts. Future addition for Phase E collaboration.
- **Auto-confirm above threshold:** Rejected. Violates the Gatekeeper
  invariant (CLAUDE.md: "ML outputs use Gatekeeper pattern: proposals
  -> admin review -> confirmed"). Even at P(match) > 0.95, human
  confirmation is required. The heritage archive domain demands
  certainty — a wrong identification is worse than no identification.
- **Push notifications (browser/mobile):** Over-engineering for a
  single-admin system. Badge is sufficient until multi-user.

### Implementation Notes

- Badge count query: computed by `_compute_discoveries()` using
  `DISCOVERY_DISTANCE_THRESHOLD = 1.0` (cosine distance < 1.0)
- This distance threshold approximately maps to P(match) > 0.85
  per the isotonic calibration model (AD-149)
- Threshold configurable via `DISCOVERY_DISTANCE_THRESHOLD` constant
- Badge renders in `_admin_bar()` in app/main.py
- One-click view reuses existing proposal review components
- Must preserve all existing Gatekeeper guards (_check_admin)

### Dependencies

- Calibrated similarity scores in production (AD-149) -- DONE
- Proposals with calibrated scores attached -- needs wiring
- Admin dashboard (_admin_bar) -- exists

### Breadcrumbs

- AD-097: ML Gatekeeper Pattern
- AD-149: Isotonic Regression Calibration (AUC=0.9577)
- AD-150: Recalibration hooks
- FE-041: "Help Identify" mode for non-admin users (related)
- CAL-002: Active learning (surfaces uncertain pairs -- complement)

---

## DD-004: Family Tree Floating-Face Design

- **Date:** 2026-02-28
- **Session:** 80 continuation
- **Status:** Implemented

### Problem

User feedback: "Barely any of the screen is the faces." The original tree
used landscape cards (280x110px) with small 52px circular photos positioned
left-of-text. The cards competed with faces for visual attention. Gender
was not indicated. No way to collapse expanded branches. Profile links from
tree were broken (/people/ vs /person/).

### Decision

"Floating-face" design: faces ARE the tree, not data inside boxes.

1. **Portrait cards (144x190)** with 96px photo circles top-centered
2. **Nearly invisible card backgrounds** (25% opacity) that materialize
   on hover with glassmorphic rise + drop shadow
3. **Gender-coded photo rings**: blue (#60a5fa) = M, pink (#f9a8d4) = F,
   gray (#4b5e78) = U
4. **Photo drop shadows** for depth against dark background
5. **Collapse/expand toggle**: expanded branches show red minus button,
   clicking collapses that subtree
6. **Dashed gold couple connectors** with center dot
7. **Progressive detail**: dates/names hide at low zoom levels
8. **Keyboard shortcuts**: +/- zoom, 0 fit-to-content
9. **Deep background** (#080d1a) for maximum photo contrast

### Alternatives Rejected

- **Landscape cards with bigger photos**: Still puts data boxes first
- **Standard visible card backgrounds**: Competes with faces for attention
- **Branch color coding (MyHeritage style)**: Adds visual noise; gender
  rings already provide per-person color differentiation

### Research

Analyzed Geni, Ancestry, MyHeritage, FamilySearch, donatso/family-chart.
All use visible card boxes with photos as supplementary. The floating-face
approach is differentiated: faces are 90% of visual weight, cards only
appear on interaction. Follows 2025-2026 glassmorphism trend.

### Breadcrumbs

- AD-185: Original card-based tree layout
- Session 80 feedback: docs/session_context/session-80-tree-feedback.md
- Bug fix: /people/{id} -> /person/{id} (profile links from tree)

---

## DD-005: Photo-Dominant Identity Cards

- **Date:** 2026-02-28
- **Session:** 80 continuation
- **Status:** Implemented

### Problem

Previous card design had too much text and buttons visible. The face was
small relative to the card. Admin tools (confirm, reject, merge, rename,
detach, skip, reset) dominated the visual hierarchy. User feedback:
"cards broken/not to standard."

### Decision

Identity cards redesigned to be photo-dominant with the face as the hero
element. Compact pill buttons (Photos, Similar, Tree, Profile) provide
quick navigation. Admin tools are wrapped in a collapsible `<details>`
section -- clean cards by default, admin workflow available on demand.

### Rationale

Heritage archive is fundamentally visual -- the face IS the data. Admin
tools are needed for workflow but should not dominate the public-facing
card. Collapsible admin follows the progressive disclosure pattern:
show the most important content first, reveal complexity on request.

### Implementation

- `identity_card()` in `app/main.py`
- Hero face uses `get_best_face_id()` for highest quality crop
- Pills provide quick navigation without cluttering the card
- Face count badge shows multi-face identities at a glance

### Alternatives Rejected

1. **Tab-based cards** -- too complex for a browse grid
2. **Hover-reveal actions** -- not mobile-friendly
3. **Separate admin view** -- creates maintenance burden of two card layouts

### Breadcrumbs

- DD-002: Face Card Layout Improvements (earlier iteration)
- AD-189: Best-face selection for tree nodes (same `get_best_face_id` pattern)
- Session 80 feedback: docs/session_context/session-80-tree-feedback.md

---

## DD-007: Compare = Find Similar Variant (Unified Upload Pipeline)

- **Date**: 2026-03-03
- **Session**: 85
- **Status**: Shipped

**What:** Compare is "Find Similar where you manually searched the person." All uploads via Compare go through the same staging → process_directory pipeline as the Upload page. No separate `uploads/compare/` silo. Photos persist to archive with photo_index entries, INBOX identities, embeddings, and R2 crops.

**Why:** Compare uploads were invisible to the rest of the platform — photos never appeared in Photos, faces never got identities, embeddings were never stored. Users expected uploaded photos to persist (Claude Benatar use case). Unifying the pipeline means every photo enriches the archive regardless of entry point.

**Key additions:**
- `POST /api/compare/vs-person` — per-face distance against selected person's anchors
- `GET /api/compare/search-person` — autocomplete person search for targeted comparison
- `GET /api/compare/status/{job_id}` — HTMX polling for background ingest progress
- Enhanced result page with confidence bars (dual encoding), person/photo links

**Origin:** Claude Benatar feedback (2026-03-02): "see if you can find a match with this picture" against Isaac Cohen. Nolan direction: "Compare = Find Similar variant, same merge/reject."

---

## DD-006: Unified Face Cards + Full Find Similar Panel

- **Date**: 2026-03-02
- **Session**: 84
- **Status**: Shipped

### Problem

Face cards were inconsistent across admin sections. The New Matches browse view used `identity_card_compact()` which stripped Photos button, Share button, multi-face gallery, quality display, and the full Find Similar panel. Clicking "Similar" loaded a simplified inline panel (`/api/find-similar/{id}`) that lacked Select All, Merge Selected, Not Same Selected, Load More, Manual Search, and Rejected matches — all of which existed in the full `neighbors_sidebar()`.

### Decision

1. **One card component**: All admin sections use `identity_card()` with a new `show_triage: bool` param for browse-specific Confirm/Skip/Reject buttons
2. **Full Find Similar**: Admin Similar button targets `/api/identity/{id}/neighbors` (full `neighbors_sidebar()`) instead of simplified `/api/find-similar/{id}`
3. **container_id param**: `neighbors_sidebar()` accepts `container_id` to target either browse expansion panels (`expand-{css_id}`) or focus sidebar (`neighbors-{id}`)
4. **Share on all named**: Removed CONFIRMED-only restriction on share button
5. **Card animation**: `.find-similar-active` CSS class with gold border + subtle scale on Similar click

### Alternatives Rejected

1. **Keep two card components** — maintenance burden, feature divergence was the original problem
2. **Merge compact into full as a "mode"** — too many conditionals; cleaner to deprecate compact entirely
3. **Custom inline panel for browse** — duplicated all the bulk action, search, and pagination logic already in `neighbors_sidebar()`

### Breadcrumbs

- DD-005: Photo-Dominant Identity Cards (preserved in unified card)
- Session 84: docs/sessions/SESSION_084.md
- Tests: tests/test_inline_find_similar.py (25 tests)

---

## DD-016: Scoped Variants for Architectural UI Upgrades

- **Date:** 2026-03-11
- **Session:** 99
- **Status:** Proposed on PR #8 (not accepted on `main`)

### Context

The Modern UI upgrade (PR #7) mandated a strict "zero-regression" rollout. Deeply shared primitives like `section_header` and shared navigation builders are utilized across many administrative and public routes. A global CSS overhaul would invariably break out-of-scope dashboards.

### Decision

1. **Variant Injection**: Rather than changing CSS defaults on `app/main.py` builders, we introduced an optional `variant: str = None` parameter to the shared helpers actually needed by the in-scope routes (`sidebar`, `section_header`, `_admin_dashboard_banner`, `_public_nav_links`).
2. **Explicit Opt-in**: Targeted surfaces (e.g. Landing, Identify, Workstation root) pass `variant="session99"` down the DOM tree. 
3. **Internal Branches**: The builders check `if variant == "session99"` and apply the `ui99-*` archival CSS taxonomy, falling back to the legacy Tailwind classes otherwise.

### Alternatives Rejected

1. **Duplicating Functions**: (e.g., `face_card_v2`) — High maintenance burden and code duplication.
2. **Route-Specific CSS overrides**: Overly fragile; CSS specificity wars.
3. **Global Launch**: Unacceptable risk of regression on the complex GEDCOM and Administration panels.

### Breadcrumbs

- PR #7: Modern UI Audit
- Session 99: docs/session_logs/session-99-log.md
- Codex review: docs/assessments/session-99-codex-review.md

---

## DD-017: app/main.py Phased Refactoring Strategy

- **Date:** 2026-03-22
- **Session:** 135
- **Status:** Decided

### Context

`app/main.py` is 11,765 lines with 173 functions, creating the single largest
bottleneck for parallel worktree development (Lesson 88). Prior extraction sessions
(91b, 92) moved route handlers out but left 215 shared attributes accessed via
`_main_mod` pattern (1,997 total references across 19 route files).

### Decision

Three-phase extraction ordered by risk:
1. **Phase 1 (LOW):** Pure UI component functions -> `app/components/` package (~5,500 lines)
2. **Phase 2 (MEDIUM):** Helpers, proposals, community logic -> named modules (~1,700 lines)
3. **Phase 3 (HIGH):** Data layer, caches, middleware -> `app/data_access.py`, `app/cache.py` (~3,000 lines)

Each phase is independently shippable. Phase 1 unblocks parallel UX development
immediately without touching the `_main_mod` pattern. Phase 3 eliminates it entirely.

Migration uses re-export pattern: extracted functions are temporarily re-exported
from `app/main.py` to avoid big-bang import changes across 3,696+ tests.

### Alternatives Rejected

1. **Big-bang refactor** — Too risky; touching 19 route files + 3,696 tests simultaneously
2. **Leave as-is** — Parallel development remains blocked; every UX session serialized
3. **Dependency injection framework** — Overkill for FastHTML; adds complexity without proportional benefit
4. **Move to React/Next.js** — Framework migration trigger not yet met (HD-022)

### Breadcrumbs

- PRD: docs/prds/056_mainpy_refactoring.md
- Research: docs/session_context/session-135-research.md
- Lesson 88: tasks/lessons/harness-lessons.md
- BACKLOG: REFACTOR-001
