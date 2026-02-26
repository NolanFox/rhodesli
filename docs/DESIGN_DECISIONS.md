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
