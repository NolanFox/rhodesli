# Rhodesli — Consolidated Prioritized Improvements (March 2026)

This is the unified synthesis document requested: one ranked list that combines overlapping ideas, preserves distinct proposals, and turns them into implementation-ready initiatives.

## Method + source breadcrumbs

This ranking was synthesized from feedback, UX/design research, roadmap/backlog status, ML decisions, session context, and ops docs.

Primary breadcrumbs:
- `docs/feedback/FEEDBACK_INDEX.md`, `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`
- `docs/design/DISCOVERY_UX_RESEARCH.md`, `docs/design/UX_PRINCIPLES.md`
- `ROADMAP.md`, `docs/BACKLOG.md`, `docs/roadmap/FEATURE_STATUS.md`, `docs/roadmap/ML_ROADMAP.md`
- `docs/design/ML_FEEDBACK.md`, `docs/ml/ALGORITHMIC_DECISIONS.md`, `docs/ml/PHOTO_ENHANCEMENT_RESEARCH.md`
- `docs/session_context/session_81_location_ux_research.md`
- `docs/ops/OPS_DECISIONS.md`, `docs/DEPLOYMENT_GUIDE.md`, `docs/MANUAL_TEST_CHECKLIST.md`

## Prioritization criteria

1. **Adoption impact** (new/returning community participation)
2. **Identification throughput** (more accepted, high-quality identifications)
3. **Trust + historical accuracy** (provenance, gatekeeping, reversibility)
4. **Feasibility** (AD-110 constraints, current stack)
5. **Compounding value** (enables other roadmap items)

---

## Final ranked initiatives (consolidated)

| Rank | Initiative (merged where relevant) | Priority rationale |
|---|---|---|
| 1 | Identification Funnel 2.0 + Stateful Help Identify | Highest friction point from direct user feedback; biggest near-term conversion lift. |
| 2 | Contributor Trust Layer (submission timeline + notifications + status clarity) | Prevents silent-drop frustration and drives repeat contributions. |
| 3 | Context-First Identification UX (photo context, co-occurrence, evidence cards) | Improves decision quality and confidence, especially for non-technical users. |
| 4 | Upload-to-Insight Automation (date/location/summary + review queue) | Reduces admin toil and shortens time-to-value after upload. |
| 5 | Mobile + Accessibility Hardening Sprint | Core demographic is mobile-heavy; removes immediate usability blockers. |
| 6 | Match Quality Program (golden-set expansion + active learning + recalibration) | Safe ML quality gains under current invariants. |
| 7 | Provenance + Confidence Language System (public + admin surfaces) | Increases trust and discourages overclaiming uncertain outputs. |
| 8 | Compare Tier 2 Productization (shared engine + archive handoff) | Converts compare from feature to acquisition/onboarding channel. |
| 9 | Surname Onboarding + Personalized Discovery Feed + Digest | Directly matches documented community behavior. |
| 10 | Photo-Back Intelligence (transcription search + evidence linking) | Unique heritage differentiator with strong user pull. |
| 11 | Ops Reliability Pack (CI/CD, smoke gates, observability, runbooks) | Protects contributor trust by reducing production regressions. |
| 12 | Community Moderation Scale-Up (rate limiting, triage queues, abuse controls) | Needed as participation volume grows. |
| 13 | Public Trust UX for “Unidentified” + correction workflow | Addresses explicit confusion from recent feedback rounds. |
| 14 | Data/Knowledge Layer Expansion (events, places, relationship graph UX) | Increases archive meaning beyond face-only interactions. |
| 15 | Institutional Partnership Mode (curator workflows + governed exhibits) | Strategic growth channel and credibility multiplier. |
| 16 | Future Product Bets (NL archive query + standalone tools) | High upside, but dependency-heavy; stage behind reliability + UX wins. |

---

## Initiative details

### 1) Identification Funnel 2.0 + Stateful Help Identify
**Includes merged ideas:** persistent submissions, guided “I know this person,” clearer CTA sequencing, refresh-safe state.

- **Value:** Largest near-term gain in successful submissions and user confidence.
- **Tradeoffs:** More state complexity; must avoid nudging low-quality guesses.
- **Implementation work:**
  1. Persist draft + submission state per user/session in Supabase.
  2. Build shared “identify helper” component across `/help`, `/photo`, `/person`.
  3. Add funnel telemetry: viewed -> started -> submitted -> accepted/rejected.
- **Breadcrumbs:** `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/feedback/FEEDBACK_INDEX.md`, `docs/design/UX_PRINCIPLES.md`.

### 2) Contributor Trust Layer
**Includes merged ideas:** “My Contributions,” processing timeline, branded notifications, moderation transparency.

- **Value:** Directly combats contributor drop-off.
- **Tradeoffs:** Notification operations overhead; messaging quality matters.
- **Implementation work:**
  1. Append-only contribution events model.
  2. Dashboard timeline with clear statuses and timestamps.
  3. Email/web notifications for key state transitions (OPS-001 dependent).
- **Breadcrumbs:** `docs/design/FUTURE_COMMUNITY.md`, `ROADMAP.md`, `docs/roadmap/FEATURE_STATUS.md`.

### 3) Context-First Identification UX
**Includes merged ideas:** full-photo context panel, co-occurrence hints, standardized evidence cards, no crop-only dead ends.

- **Value:** Better identifications with less cognitive load.
- **Tradeoffs:** Risk of UI density; needs strong mobile collapse patterns.
- **Implementation work:**
  1. Reusable context component and card schema.
  2. Precompute co-occurrence stats for fast display.
  3. Evidence card parity across compare/help/identify screens.
- **Breadcrumbs:** `docs/design/UX_PRINCIPLES.md`, `docs/design/DISCOVERY_UX_RESEARCH.md`, `docs/prds/022_photo_detective_ux.md`.

### 4) Upload-to-Insight Automation
**Includes merged ideas:** auto-run ML-051/052/053, low-confidence review queue, identity summary updates.

- **Value:** Faster archive enrichment and lower manual backlog.
- **Tradeoffs:** Queue/idempotency complexity; API-cost governance required.
- **Implementation work:**
  1. Hook upload acceptance to async labeling pipeline.
  2. Retry-safe task orchestration with job states.
  3. Admin review inbox for low-confidence outputs.
- **Breadcrumbs:** `docs/roadmap/ML_ROADMAP.md`, `ROADMAP.md`, `docs/ml/ALGORITHMIC_DECISIONS.md`.

### 5) Mobile + Accessibility Hardening Sprint
**Includes merged ideas:** overflow fixes, touch-target standards, contrast/focus/semantics audit.

- **Value:** Removes practical blockers for core user base.
- **Tradeoffs:** CSS refactor risk; requires visual regression discipline.
- **Implementation work:**
  1. Resolve known issues (including mobile overflow backlog).
  2. Enforce 44px touch targets and standardized mobile nav behavior.
  3. Add accessibility verification checklist + browser checks.
- **Breadcrumbs:** `docs/BACKLOG.md`, `docs/MANUAL_TEST_CHECKLIST.md`, `docs/UX_AUDIT_SESSION_18.md`.

### 6) Match Quality Program
**Includes merged ideas:** golden-set expansion, ambiguity queue, active-learning loop, recalibration schedule.

- **Value:** Better ML utility with forensic safety.
- **Tradeoffs:** Requires careful sampling to avoid bias toward frequent families.
- **Implementation work:**
  1. Expand golden set coverage (identities, age/pose/quality diversity).
  2. Generate high-ambiguity review queue for human adjudication.
  3. Scheduled calibration jobs + dashboard.
- **Breadcrumbs:** `docs/design/ML_FEEDBACK.md`, `docs/roadmap/ML_ROADMAP.md`, `docs/ml/current_ml_audit.md`.

### 7) Provenance + Confidence Language System
**Includes merged ideas:** badges (AI/community/admin), explanation snippets, confidence phrasing, correction path.

- **Value:** Makes decisions understandable and trusted.
- **Tradeoffs:** Too much nuance can overwhelm; copywriting quality is critical.
- **Implementation work:**
  1. Normalize provenance metadata across objects.
  2. Add badge/rationale components for public and admin views.
  3. Add “submit correction” to moderation queue.
- **Breadcrumbs:** `docs/design/UX_PRINCIPLES.md`, `docs/canonical/UX_PRINCIPLES.md`, `docs/roadmap/FEATURE_STATUS.md`.

### 8) Compare Tier 2 Productization
**Includes merged ideas:** shared comparison backend, archive handoff, persistent workspace, share-safe links.

- **Value:** Strong acquisition + engagement vector.
- **Tradeoffs:** Must separate disposable compare flows from canonical data writes.
- **Implementation work:**
  1. Define shared compare service contract.
  2. Build handoff state machine into moderated archive path.
  3. Add abuse/rate controls for public uploads.
- **Breadcrumbs:** `ROADMAP.md`, `docs/BACKLOG.md`, `docs/prds/021_multi_photo_compare.md`, `docs/sessions/SESSION_085.md`.

### 9) Surname Onboarding + Personalized Discovery Feed + Digest
**Includes merged ideas:** first-run surname selector, relevance feed, weekly updates.

- **Value:** Faster “I recognize this” moment and better retention.
- **Tradeoffs:** Cold-start and preference-quality challenges.
- **Implementation work:**
  1. Store interest preferences (surnames/collections).
  2. Rank feed sections: new discoveries, can-you-help, highlights.
  3. Optional digest with opt-in controls.
- **Breadcrumbs:** `docs/design/DISCOVERY_UX_RESEARCH.md`, `docs/feedback/FEEDBACK_INDEX.md`.

### 10) Photo-Back Intelligence
**Includes merged ideas:** transcription indexing, back-side evidence chips, correction workflows.

- **Value:** Unique archival moat; directly aligned with user requests.
- **Tradeoffs:** Handwriting OCR quality variance and moderation burden.
- **Implementation work:**
  1. Index back transcriptions for search/filter.
  2. Add correction/annotation flow for transcriptions.
  3. Surface “back evidence” in person/photo decision contexts.
- **Breadcrumbs:** `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/PHOTO_WORKFLOW.md`, `docs/roadmap/FEATURE_STATUS.md`.

### 11) Ops Reliability Pack
**Includes merged ideas:** CI gates, production smoke tests, Sentry, rollback docs.

- **Value:** Fewer outages/regressions, stronger contributor trust.
- **Tradeoffs:** Initial setup + alert tuning cost.
- **Implementation work:**
  1. CI pipeline running both test suites + key browser checks.
  2. Deploy health gates and rollback playbook.
  3. Error/performance observability on critical flows.
- **Breadcrumbs:** `docs/ops/OPS_DECISIONS.md`, `docs/DEPLOYMENT_GUIDE.md`, `ROADMAP.md`.

### 12) Community Moderation Scale-Up
**Includes merged ideas:** pending-queue ergonomics, rate limiting, duplicate suppression, reviewer tooling.

- **Value:** Maintains quality while participation grows.
- **Tradeoffs:** Potential reviewer fatigue; requires triage UX excellence.
- **Implementation work:**
  1. Prioritized queue scoring (impact/confidence/novelty).
  2. Rate limits + anti-spam heuristics.
  3. Batch review tools with strong undo/provenance.
- **Breadcrumbs:** `docs/BACKLOG.md`, `docs/design/FUTURE_COMMUNITY.md`, `docs/ROLES.md`.

### 13) Public Trust UX for “Unidentified” + correction workflow
**Includes merged ideas:** label clarification, contextual messaging, explicit “help improve this” pathways.

- **Value:** Resolves known confusion and increases constructive participation.
- **Tradeoffs:** Messaging needs cultural sensitivity and precision.
- **Implementation work:**
  1. Replace ambiguous labels with explanatory copy.
  2. Attach evidence/provenance context inline.
  3. Add lightweight public correction submission.
- **Breadcrumbs:** `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/feedback/FEEDBACK_INDEX.md`.

### 14) Data/Knowledge Layer Expansion
**Includes merged ideas:** life events, places timeline, graph-style context for relationships.

- **Value:** Moves product from face-matcher to heritage knowledge system.
- **Tradeoffs:** Data model complexity; quality depends on curation depth.
- **Implementation work:**
  1. Event/place schema and linkage to people/photos.
  2. Timeline and map UX integration.
  3. Lightweight graph exploration for relationships/co-appearance.
- **Breadcrumbs:** `docs/prds/011_life_events_context_graph.md` (referenced in roadmap), `docs/roadmap/FEATURE_STATUS.md`, `docs/roadmap/ML_ROADMAP.md`.

### 15) Institutional Partnership Mode
**Includes merged ideas:** curator permissions, provenance governance, public exhibits.

- **Value:** Strategic adoption and credibility channel.
- **Tradeoffs:** Longer cycle time; legal/governance requirements.
- **Implementation work:**
  1. Partner collection model + role extensions.
  2. Curator moderation/audit/export workflows.
  3. Exhibit templates with controlled publish settings.
- **Breadcrumbs:** `docs/design/FUTURE_COMMUNITY.md`, `docs/OPERATIONS.md`, `docs/ROLES.md`.

### 16) Future Product Bets
**Includes merged ideas:** NL archive query, standalone date estimator, additional external tools.

- **Value:** Potentially high upside and discoverability.
- **Tradeoffs:** Dependency-heavy and should follow core reliability/UX work.
- **Implementation work:**
  1. Prerequisite checklists (quality, latency, safety).
  2. MVP pilots with clear kill criteria.
  3. Shared service interfaces for reuse across products.
- **Breadcrumbs:** `docs/BACKLOG.md` (PRODUCT-003/004), `ROADMAP.md`, `docs/roadmap/ML_ROADMAP.md`.

---

## Execution recommendation (sequenced)

### Wave A (now: 2–4 sessions)
1. Identification Funnel 2.0
2. Contributor Trust Layer
3. Mobile + Accessibility Hardening
4. Public Trust UX for “Unidentified”

### Wave B (next: 3–6 sessions)
5. Context-First UX
6. Upload-to-Insight Automation
7. Provenance + Confidence System
8. Community Moderation Scale-Up

### Wave C (strategic: 6+ sessions)
9. Match Quality Program
10. Compare Tier 2 Productization
11. Surname/Feed/Digest personalization
12. Photo-Back Intelligence
13. Ops Reliability Pack (parallelizable)
14. Data/Knowledge Layer Expansion
15. Institutional Partnership Mode
16. Future Product Bets

## Success metrics to track across all waves

- Time to first successful contribution
- Accepted identifications per active contributor
- 7-day and 30-day contributor return rate
- Median moderation turnaround time
- % of public entries with explicit provenance
- Mobile task success rate on key flows
- Regression incidents per release
