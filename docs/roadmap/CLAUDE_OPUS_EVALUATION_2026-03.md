# Rhodesli — Claude Opus Independent Evaluation (March 2026)

**Evaluator**: Claude Opus 4.6
**Date**: 2026-03-04
**Methodology**: Full codebase read (35K+ lines app code, 3985 tests, 188 AD entries, all feedback docs, all session logs, live production site review, ops infrastructure audit, ML pipeline audit)
**Codex evaluation**: [PRIORITIZED_IMPROVEMENTS_2026-03.md](PRIORITIZED_IMPROVEMENTS_2026-03.md) — merged from PR #4

---

## Part 1: Assessment of Codex's Evaluation

### What Codex Got Right

Codex's 16-initiative ranking is **directionally correct** on priorities 1-5. The identification funnel, contributor trust, context-first UX, upload automation, and mobile hardening are indeed the highest-leverage improvements. The wave-based execution model (A/B/C) is sensible.

### Where Codex's Evaluation Falls Short

1. **Too abstract, not actionable enough.** Each initiative reads like a strategy consulting deliverable — broad themes with bullet-point work items. Compare "Reusable context component and card schema" to the actual implementation reality: `app/main.py` is a 35,797-line monolith where 14+ inline face card renderers need consolidation (UX-204). Codex doesn't engage with the **actual codebase constraints** that determine what's feasible in 1-2 sessions vs. what requires architectural changes.

2. **Misses the monolith problem entirely.** The single biggest blocker to velocity is `app/main.py` at 35K lines. Parallel worktree sessions — the project's primary scaling mechanism — are bottlenecked because every UI change touches this file. Codex's evaluation doesn't mention this at all. See: Lesson 88 (`tasks/lessons/harness-lessons.md`).

3. **Underweights the broken things.** Real users (Claude Benatar) have reported specific, concrete bugs that remain unfixed:
   - Merge direction loses named data (UX-037, reported twice, metadata lost twice)
   - Person page is an admin dead-end (UX-039)
   - Estimate upload is broken (UX-053-057)
   - Compare loading feedback missing (UX-045-046)
   These aren't "initiatives" — they're P1 bugs blocking the core workflow. Fix these before building new systems.

4. **Overweights futures that don't have user pull yet.** "Institutional Partnership Mode" (#15), "Future Product Bets" (#16), and even "Community Moderation Scale-Up" (#12) are solutions looking for problems. The archive has 3 active identifiers and 274 photos. The constraint isn't moderation scale — it's getting the **first 10 contributors** through the funnel without hitting bugs.

5. **Doesn't engage with the ML pipeline gaps.** The ML system has a **known open experiment** (AD-027: MLS vs Euclidean) that could improve matching by 5-10% for degraded heritage photos. The calibration model concentrates 94% of same-person pairs in the top 5 identities (AD-022). These are addressable, high-impact gaps that Codex's "Match Quality Program" (#6) hand-waves past.

6. **Missing key breadcrumbs.** Several of Codex's breadcrumbs point to files that don't exist or are misnamed (`docs/canonical/UX_PRINCIPLES.md`, `docs/sessions/SESSION_085.md`, `docs/ROLES.md`). This suggests the evaluation was generated from file listings rather than actual content reading.

### Rating: B-
Correct priorities at the strategic level, but too abstract to guide actual session work. Needs to be grounded in the codebase reality.

---

## Part 2: My Independent Evaluation — Top 12 Improvements

### Prioritization Criteria

1. **Unblock real users NOW** — Fix what Claude Benatar and Facebook community members actually hit
2. **Compound value** — Enable parallelism, reduce session cost, unlock future features
3. **Evidence-backed** — Supported by user feedback, test data, or production metrics
4. **Feasible** — Can ship in 1-2 focused sessions given the monolith constraint

---

### 1. Fix the 6 P1 UX Bugs (1 session, ~4 hours)

**What**: Fix UX-037 (merge direction), UX-039 (person page admin controls), UX-045/046 (compare loading), UX-053-057 (estimate upload flow), UX-092 (birth year race condition).

**Why first**: These are bugs that real users hit and reported. Claude Benatar's merge direction issue caused metadata loss **twice**. The estimate upload flow is completely broken for community-uploaded photos. Compare loading makes users think uploads failed. Every user who hits one of these bugs loses trust.

**Value**: Closes all P1 friction. Unblocks the identification funnel without building any new systems.

**Tradeoffs**: None meaningful. These are bugs, not features.

**Work**:
- UX-037: Reverse merge direction (named identity survives) + confirmation modal showing which identity persists. ~45 min.
- UX-039: Add admin action panel (rename, confirm, merge, detach, GEDCOM link) to `/person/{id}`. Reuse existing dashboard buttons. ~60 min.
- UX-045/046: Ensure spinner is visible during compare upload + auto-scroll to results. CSS + JS fix. ~30 min.
- UX-053-057: Unify estimate upload result layout with archive flow. Add photo preview, loading state, CTAs. ~90 min.
- UX-092: Fix birth year save/edit race condition. ~15 min.

**Breadcrumbs**: `docs/BACKLOG.md` §Active Bugs, `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/ux_audit/UX_ISSUE_TRACKER.md`

---

### 2. Split app/main.py (1-2 sessions, ~6 hours)

**What**: Extract the 35,797-line monolith into route modules: `app/routes/landing.py`, `app/routes/photos.py`, `app/routes/people.py`, `app/routes/compare.py`, `app/routes/admin.py`, `app/routes/api.py`, etc.

**Why second**: This is the **single biggest force multiplier** for development velocity. Currently:
- Every UI session touches `app/main.py` (Lesson 88)
- Parallel worktree sessions can't both edit `app/main.py` without merge conflicts
- Code navigation is painful (35K lines, 45+ routes interleaved)
- New contributors (human or AI) face a wall of context

**Value**: Enables 2-3x parallel session throughput. Makes every future session faster. Reduces merge conflicts from "always" to "sometimes."

**Tradeoffs**:
- Large refactor = risk of regressions → mitigated by 3985 tests
- Import circular dependency risk → mitigated by careful extraction order (shared components first, then routes)
- One-time cost, permanent benefit

**Work**:
1. Extract shared components (`identity_card()`, `face_card()`, `neighbors_sidebar()`, etc.) into `app/components.py`
2. Extract route groups by section into `app/routes/`
3. Keep `app/main.py` as the app factory that registers all routes
4. Run full test suite after each extraction
5. Verify production with browser

**Breadcrumbs**: `tasks/lessons/harness-lessons.md` Lesson 88, `docs/BACKLOG.md` §UX-204

---

### 3. Contributor Submission Flow Polish (1 session, ~3 hours)

**What**: End-to-end polish of the Help Identify → Submit → Admin Review → Notification flow.

**Why**: This is the growth loop. Session 83a fixed the critical bug (Help Identify submissions not reaching admin Approvals), but the flow still has gaps:
- No confirmation email/page after submission ("did my submission go through?")
- No "My Contributions" page showing submission status
- No admin notification when new submissions arrive
- Submission page lacks guidance for non-technical users

**Value**: Directly addresses contributor drop-off. Claude Benatar identified 8 people in his first session but struggled with the mechanics. Every improvement here compounds through the Facebook sharing loop.

**Tradeoffs**:
- Email notifications require OPS-001 (custom SMTP). Alternative: in-app notification badge.
- "My Contributions" page adds a new route but is simple (list user's annotation records from Supabase).

**Work**:
1. Add submission confirmation page with "Thank you" + status tracking link
2. Add `/my-contributions` page (filter annotations by user email, show status)
3. Add admin notification badge on dashboard when new submissions arrive (poll or Supabase realtime)
4. Add contextual guidance on `/identify/{id}` page ("How to help: look at the full photo, check who else is in it, think about family connections")

**Breadcrumbs**: `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`, `docs/feedback/2026-03-02-claude-benatar.md` (AD-196/197), `docs/design/FUTURE_COMMUNITY.md`

---

### 4. Connected Navigation ("One App, Not Six") (1 session, ~3 hours)

**What**: Ensure every entity page links to every relevant view. Photo→Tree→Map→Person→Photos should be one-click navigation everywhere.

**Why**: Nolan's Session 81 feedback was explicit: "Currently feels like separate apps, not connected views." The Tree page doesn't link to Photos. The Map page doesn't link to People. Photo pages don't link to Tree. Each view is an island.

**Value**: Transforms the experience from "a collection of tools" to "an interconnected archive." The "sitting with grandma" metaphor requires **following threads** — clicking from a face to their family to their photos to their locations.

**Tradeoffs**: Minimal. These are navigation links, not new features. The data connections already exist (GEDCOM links, photo-to-person mappings, geocoded locations).

**Work**:
1. Photo page: Add "View in Family Tree" button (if person has GEDCOM link)
2. Photo page: Add "View on Map" button (if photo has location)
3. Person page: Add "View in Family Tree" / "View on Timeline" links
4. Tree page: Add "View Photos" link on each person node
5. Map page: Add "View Person" link on each pin
6. Consistent "Related Views" section on all entity pages

**Breadcrumbs**: `docs/session_context/session_81_nolan_feedback.md`, `docs/design/UX_PRINCIPLES.md` Principle 2 (Bidirectional Navigation)

---

### 5. Face Labels + Identity Context on Photo Pages (1 session, ~2 hours)

**What**: Replace "Face 1", "Face 2" labels on photo overlays with actual identity names (clickable links to `/person/{id}`). Add "appears in N other photos" context.

**Why**: This was the #1 item from Nolan's Session 81 feedback. Faces on photo overlays currently show generic labels. When a face IS identified, the overlay should show the name. When it's unidentified, show "Unidentified — Help Identify?" with a link to the contribution flow.

**Value**: Makes every photo page a potential identification trigger. Community members scanning photos can immediately see who IS identified and who NEEDS identification, without leaving the photo context.

**Tradeoffs**: Minimal. The identity data is already loaded. This is a rendering change.

**Work**:
1. In photo overlay renderer: look up face_id → identity mapping
2. If identified: show name as clickable link to `/person/{id}`
3. If unidentified: show "Help Identify" link to `/identify/{face_id}`
4. Add "appears in N photos" subtitle
5. Adjust overlay positioning for longer text

**Breadcrumbs**: `docs/session_context/session_81_nolan_feedback.md` §Face Analysis Labels, Session 81 AD-193

---

### 6. MLS vs Euclidean Experiment (1 session, ~2 hours)

**What**: Run the golden set evaluation comparing MLS (Mutual Likelihood Score) vs Euclidean distance. The PFE uncertainty vectors (`sigma_sq`) are computed and stored for all 654 faces but **never used at runtime** (AD-027).

**Why**: This is a free accuracy improvement sitting on the shelf. MLS should theoretically improve matching for:
- Low-quality heritage photos (high sigma → down-weighted)
- Degraded newspaper scans (high uncertainty)
- Small/blurry faces (low det_score → high sigma)

The experiment takes ~2 hours and is completely reversible.

**Value**: Potential 5-10% improvement in matching accuracy for the hardest cases (which are the ones that matter most — the easy cases are already solved).

**Tradeoffs**: If MLS doesn't help (possible — the heritage photo distribution may not benefit), we've spent 2 hours and learned something. If it helps, it's a free upgrade that requires zero user-facing changes.

**Work**:
1. Add MLS distance function to golden set evaluation script
2. Run sweep on same threshold range (0.50-2.00)
3. Compare precision/recall/F1 curves
4. If better: update `core/neighbors.py` to use MLS (currently FROZEN per AD-001, but AD-027 explicitly authorizes this experiment)
5. Document results in AD-027 resolution

**Breadcrumbs**: `docs/ml/ALGORITHMIC_DECISIONS.md` AD-027, `core/pfe.py`, `docs/adr/adr_001_mls_math.md`, `docs/adr/adr_006_scalar_sigma_fix.md`

---

### 7. CI/CD Pipeline (1 session, ~2 hours)

**What**: GitHub Actions workflow that runs `make test-fast` on every PR and `make test-full` + smoke test on merge to main.

**Why**: Currently ALL testing is local and manual. The only gate is a git hook (`PreToolUse`) that runs `make test-fast` before commits — but this only applies when Claude Code is the committer. Direct git pushes, Codex sessions, and other contributors bypass all testing. The Session 82b Codex PR (#3) is a perfect example — it was never tested and would have introduced regressions.

**Value**: Prevents broken code from reaching production. Enables safe merging of external contributions (Codex, future contributors). Catches regressions that local test runs miss (environment differences).

**Tradeoffs**:
- GitHub Actions minutes cost (free for public repos, 2000 min/month for private)
- CI needs InsightFace models → use test mocks (already exist in test suite)
- First-time setup has a learning curve, but the project already has `Makefile` targets

**Work**:
1. Create `.github/workflows/test.yml` with test-fast on PR, test-full on merge
2. Cache pip dependencies and ONNX models
3. Add production smoke test step (runs after deploy via Railway webhook notification)
4. Badge on README

**Breadcrumbs**: `docs/BACKLOG.md` §OPS-002, `Makefile`, `docs/ops/OPS_DECISIONS.md`

---

### 8. Provenance Badges on All Public Pages (1 session, ~2 hours)

**What**: Show clear provenance indicators on every identification: "AI Suggested" (blue), "Community Submitted" (amber), "Admin Confirmed" (emerald), "Family Verified" (gold).

**Why**: This is Principle 5 of the UX design principles ("Show Provenance"). Trust comes from transparency. When a community member sees "Identified: Morris Franco," they should know whether that's:
- An AI suggestion (lower confidence)
- A community member's submission (medium confidence)
- An admin confirmation (high confidence)
- A family member verification (highest confidence)

Currently provenance is tracked internally but not surfaced to public-facing pages.

**Value**: Increases trust, encourages corrections ("I think this AI suggestion is wrong — that's actually David Franco"), and creates a quality signal visible to all users.

**Tradeoffs**: Visual complexity. Need to avoid badge overload. Solution: single subtle badge per identification, tooltip with details.

**Work**:
1. Define provenance badge component with 4 levels
2. Add to person page header
3. Add to face overlays on photo pages
4. Add to search results
5. Add to Help Identify results

**Breadcrumbs**: `docs/design/UX_PRINCIPLES.md` Principle 5, `docs/design/ML_FEEDBACK.md`, `docs/BACKLOG.md` §Confidence scores

---

### 9. Surname-Based Discovery + First-Run Experience (1 session, ~3 hours)

**What**: When a new visitor arrives, ask "What family name are you looking for?" and immediately surface relevant faces, photos, and connections. Show the archive through the lens of their family.

**Why**: The community is surname-driven. The 13 surname variant groups (Capeluto, Hasson, Franco, Benatar, etc.) cover most of the community. A visitor named "Franco" should immediately see all Franco-associated photos and identities, not a generic archive grid. This is the shortest path to the "I recognize this!" moment.

**Value**: Dramatically reduces time-to-first-identification. Leverages the unique property of the Rhodes community — dense interconnection where everyone knows everyone by surname.

**Tradeoffs**:
- Cold-start problem for surnames not in the archive → show "We don't have any [surname] photos yet — can you help?"
- Requires surname tagging on identities (partially exists via GEDCOM links)

**Work**:
1. Add "Find Your Family" input on landing page (prominent, above fold)
2. Search identities + GEDCOM records by surname (fuzzy match with Sephardic variant awareness)
3. Results page: "We found N people with the [surname] family name" with face grid
4. Each result links to person profile, source photos, family tree context
5. Store surname preference in session for return visits

**Breadcrumbs**: `docs/design/DISCOVERY_UX_RESEARCH.md`, `docs/feedback/FEEDBACK_INDEX.md`, `data/surname_variants.json`, `docs/session_context/session_49C_community_feedback.md`

---

### 10. Gemini Batch Re-Run with GEDCOM Context (1 session, ~3 hours + API cost)

**What**: Re-run Gemini 3.1 Pro analysis on all 274 photos with GEDCOM enrichment context. The combined pipeline exists (`scripts/run_combined_pipeline.py`) but only 127/274 photos have been processed with GEDCOM context. 144 were rate-limited and never retried.

**Why**: The Asheville case study (Session 81) proved that GEDCOM context dramatically improves Gemini's analysis — it identified exact addresses, named children, and narrowed dates from "1930s" to "September 1934." But this was manual. The automated pipeline has been sitting un-run.

**Value**: ~$10 in API costs to unlock dramatically better metadata for 147 unprocessed photos. This data feeds the date estimation model, location map, and identity enrichment — compound value across every feature.

**Tradeoffs**: ~$10 Gemini API cost. Worth it. 2 photos are blocked by Gemini content safety (known, documented).

**Work**:
1. Run `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`
2. Verify results in Supabase
3. Update `face_gemini_alignments` table with new results
4. Refresh date estimation model with new labels (if quality improves)
5. Verify location estimates populate on `/map`

**Breadcrumbs**: `docs/BACKLOG.md` §FA-001/DATA-004, `docs/session_context/session_81_nolan_feedback.md` §Asheville, `docs/ml/ALGORITHMIC_DECISIONS.md` AD-159

---

### 11. Photo-Back Intelligence (1-2 sessions, ~5 hours)

**What**: Support photo backs (the reverse side of physical photos, often with handwritten names, dates, locations). Upload as linked asset, OCR with Gemini, index for search.

**Why**: This is Claude Benatar's explicitly requested feature: "Need to post backs of photos." Photo backs are the #1 evidence source for heritage photo identification — they often have handwritten names, dates, and locations that definitively identify subjects. No competing product handles this.

**Value**: Unique heritage differentiator. Directly solves the identification problem for photos with written context. Creates a new evidence type that feeds into all existing ML pipelines.

**Tradeoffs**:
- Data model change: photos need a `back_photo_id` field linking front ↔ back
- OCR quality varies for handwriting → Gemini handles this well
- Moderation burden: handwritten text needs human verification

**Work**:
1. Add `back_photo_id` to photo schema (Supabase + JSON cache)
2. Upload flow: "Add Back of Photo" button on photo page (admin only initially)
3. Auto-run Gemini OCR on uploaded back → extract text, names, dates
4. Index extracted text for search (full-text search on `visible_text`)
5. Display "Back of Photo" section on photo page with transcription
6. Surface "back evidence" in identification context

**Breadcrumbs**: `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md` ("Need to post backs of photos"), `docs/BACKLOG.md` §Photo-Back, `docs/roadmap/PRIORITIZED_IMPROVEMENTS_2026-03.md` #10

---

### 12. Error Tracking + Production Observability (1 session, ~2 hours)

**What**: Add Sentry for error tracking. Add structured logging for key user flows. Add disk space alerting.

**Why**: The disk space crisis (Session 85b) went undetected for **months** because there was no alerting. The health endpoint reported root filesystem stats (3TB free) while the Railway volume (433MB) was 94.9% full. Production 500 errors are invisible until users report them.

**Value**: Catches production issues before users do. Provides data for prioritization (which errors are most common? which flows fail most?).

**Tradeoffs**: Sentry is $30-100/month (or free tier for low volume). Worth it for a production app with real users.

**Work**:
1. Add `sentry-sdk[fastapi]` to requirements
2. Initialize in app startup with DSN from env var
3. Configure error sampling (100% for 500s, 10% for performance)
4. Add disk space alerting: check volume free space on startup, warn if <50MB, alert if <20MB
5. Add structured logging for: upload completions, identification submissions, merge actions, compare requests

**Breadcrumbs**: `docs/BACKLOG.md` §OPS-004, `docs/ops/OPS_DECISIONS.md`, `docs/ops/VOLUME_INVESTIGATION_85b.md`

---

## Part 3: Comparison Matrix — Claude Opus vs Codex

| # | Codex Initiative | Opus Equivalent | Key Difference |
|---|------------------|-----------------|----------------|
| 1 | Identification Funnel 2.0 | #1 Fix P1 Bugs + #3 Submission Polish | Codex builds new; Opus fixes broken first |
| 2 | Contributor Trust Layer | #3 Submission Polish | Same goal, Opus is more specific |
| 3 | Context-First UX | #4 Connected Navigation + #5 Face Labels | Opus splits into concrete deliverables |
| 4 | Upload-to-Insight Automation | #10 Gemini Batch Re-Run | Codex abstracts; Opus points to specific script to run |
| 5 | Mobile + Accessibility | (Part of #1 bug fixes) | Opus doesn't separate this — mobile bugs are just bugs |
| 6 | Match Quality Program | #6 MLS Experiment | Opus is specific: run one experiment, measure result |
| 7 | Provenance System | #8 Provenance Badges | Same idea, Opus scopes to visual badges only |
| 8 | Compare Tier 2 | (Not in top 12) | Opus deprioritizes — compare already works, refinement can wait |
| 9 | Surname Discovery | #9 Surname Discovery | Agreement — high value |
| 10 | Photo-Back Intelligence | #11 Photo-Back Intelligence | Agreement — unique differentiator |
| 11 | Ops Reliability Pack | #7 CI/CD + #12 Sentry | Opus splits into two concrete sessions |
| — | (Not in Codex) | **#2 Split app/main.py** | **Opus's biggest addition** — the monolith is the bottleneck |

### Ideas NOT on Either List

1. **Offline Photo Archive Export** — Community members (especially elderly) may want a printed or PDF photo book. Export a person's photos + metadata as a printable document. Heritage use case: family reunion handouts.

2. **"This Week in History" Auto-Posts** — Generate weekly Facebook posts from the archive based on estimated dates. "On this week in 1937, the Capeluto family gathered at 33 Elizabeth Street, Asheville..." Auto-generates shareable content, drives the growth loop without manual effort.

3. **Voice-to-Identification** — Many elderly community members are more comfortable speaking than typing. Add a microphone button on the Help Identify page that uses Whisper/browser Speech API to transcribe spoken identifications. "That's my grandmother, Victoria Capeluto, she was born in 1920."

4. **Co-occurrence Network Visualization** — Show which unidentified people appear together most often. "These 3 unidentified faces appear in 7 photos together — they're likely from the same family." This leverages UX Principle 7 (Co-occurrence is Signal) and the dense community graph.

---

## Part 4: Recommended Next Session

### Session 86 Recommendation: "Fix Everything Broken"

**Scope**: Items #1 (P1 bugs) + #5 (face labels) + #4 (connected navigation links)

**Why this combination**:
- All are UX changes in the existing codebase (no new infrastructure)
- Total effort ~8 hours
- Directly addresses all real user complaints
- No ML dependencies, no API costs, no deployment risk
- Can be verified in browser session

**Expected outcome**: Every page in the app has working admin controls, connected navigation, and identity-aware face labels. No dead ends, no broken flows.

### Session 87 Recommendation: "Split the Monolith"

**Scope**: Item #2 (split app/main.py)

**Why next**: After Session 86 fixes the UX, this unblocks all future development velocity. Every session after this one is faster.

### Session 88 Recommendation: "ML + Pipeline"

**Scope**: Items #6 (MLS experiment) + #10 (Gemini batch re-run)

**Why**: These are high-value, low-risk improvements that can run in parallel (MLS is code-only, Gemini is API-only).

---

## Appendix: Data Supporting This Evaluation

### User Feedback Sources
- `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md` — Primary user (non-technical family member)
- `docs/feedback/2026-03-02-claude-benatar.md` — Most recent feedback round
- `docs/session_context/session_49C_community_feedback.md` — Facebook group test
- `docs/session_context/session_81_nolan_feedback.md` — Connected app vision
- `docs/session_context/session_80-tree-feedback.md` — Tree UX feedback

### ML Quality Evidence
- AUC: 0.9391 (calibrated MLP) vs 0.9493 (baseline Euclidean)
- F1: 0.60 (calibrated) vs 0.13 (baseline) — **4.8x improvement**
- Golden set: 4005 evaluation pairs, 0 confirmed pair breaks
- Signal inventory: 959 positive pairs, 510 rejections, 125 golden mappings

### Production Metrics
- 274 photos, 665 identities, 60 confirmed
- 3 active community identifiers (Facebook group)
- ~3985 tests passing
- Railway volume: 8.2% used (post-cleanup)
- Zero P0 production incidents in 90 days

### Architecture Constraints
- `app/main.py`: 35,797 lines (monolith, blocks parallel sessions)
- 45+ routes, 14+ inline face card renderers
- Railway: 512MB RAM, shared CPU, single dyno
- AD-110: No heavy ML on Railway (inference only)
