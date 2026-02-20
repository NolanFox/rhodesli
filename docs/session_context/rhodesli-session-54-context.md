# Session 54 Context — ML Architecture Research + UX Prioritization

**Source:** Claude (Opus 4.6) conversation with Nolan, Feb 20 2026.
**Purpose:** Preserve research, reasoning, and decisions so Claude Code has full context.
**Breadcrumbs:** This conversation followed Session 53 (comprehensive production audit).

---

## Why This Session Exists

Session 53 ran a comprehensive production audit (35 routes, all healthy) and made compare upload fixes. However, it left several items incomplete:
1. Resize went to 1024px instead of the specified 640px
2. buffalo_sc model investigation was skipped
3. No actual upload testing with real photos was performed
4. The deeper question of ML architecture wasn't addressed

Nolan flagged that the ML processing architecture has been drifting without a coherent plan since Session 4. This session documents the architecture decision and completes the unfinished work.

---

## ML Architecture Research Summary

### How Immich Handles It (gold standard for self-hosted photo apps)
Source: docs.immich.app/developer/architecture/

- **Separate ML container** (immich-machine-learning): Python/FastAPI microservice
- **Job queue**: Redis/BullMQ with chained jobs: thumbnail → face detection → facial recognition
- **Upload is instant**: File saved, background job queued, UI updates when processing completes
- **Remote ML**: ML container can run on a different machine (even your laptop)
- **ONNX models**: Same format Rhodesli uses
- **Incremental clustering**: Modified DBSCAN that preserves previous clusters when adding new faces
- **Nightly reconciliation**: Unassigned faces get a second pass overnight

### How Facebook Did Photo Tagging
Source: HowStuffWorks, Science.org

- Upload → photo visible instantly → face boxes appear 1-2 seconds → tag suggestions
- User NEVER waits for ML processing
- Tag Suggestions auto-fill "Who is this?" boxes for identified faces
- DeepFace (2014): 97.35% accuracy, processed 400M photos/day at peak
- Key UX: **immediate visual feedback, ML enrichment arrives progressively**

### How PhotoPrism Does It
Source: docs.photoprism.app

- Multi-stage pipeline: detect → generate embeddings → cluster
- Processing happens during library "scan" (batch), NOT during upload
- ONNX engine (SCRFD model) with configurable similarity distance (0.60-0.70)
- Known weakness: face detection quality (Pigo engine is poor, ONNX/SCRFD better)

### Universal Pattern Across All Tools
1. Upload = instant (save file, show it, return 200)
2. ML = background (queue job, process async, update UI when done)
3. Interactive features use pre-computed data (search embeddings, not run models)
4. Batch operations are separate from the serving path

---

## Rhodesli Architecture Evolution (How We Got Here)

### Phase 1: Sessions 1-8 — Local Only
- All ML processing on Nolan's Mac
- Web app was read-only display
- `PROCESSING_ENABLED=false` on Railway
- Docker image ~200MB (lightweight FastHTML)

### Phase 2: Sessions 9-32 — Local + Staging
- Upload flow added but ML still local
- Photos staged on Railway, pulled to local for processing
- Results pushed back via sync scripts
- This was the "correct" architecture per early discussions

### Phase 3: Sessions 33-51 — Feature Creep
- Compare feature needed real-time face detection → pressure to add ML to server
- Estimate needed Gemini API → cloud API calls added
- InsightFace availability was inconsistent → graceful degradation added piecemeal
- Architecture became confused: sometimes ML available, sometimes not

### Phase 4: Session 52 — ML to Cloud (the pivot)
- InsightFace + ONNX Runtime added to Docker image with buffalo_l pre-downloaded
- `PROCESSING_ENABLED=true`
- Docker image ballooned to ~3-4GB
- Compare works but takes 65 seconds on Railway shared CPU
- This broke the original "clean Vercel" principle from CLAUDE.md

---

## The Hybrid Architecture Decision (AD-110) — Serving Path Contract

**The Non-Negotiable Invariant:** The user-facing request path MUST NEVER run heavy ML.
This is the missing principle that explains all the architectural drift. Once named, 
architecture decisions become obvious.

**Cloud (Railway):**
- Serve pages, auth, data management
- Compare: pre-computed embeddings for matching (0.4s) + buffalo_sc + 640px for detection (<15s target)
- Estimate: Gemini API calls (already working)
- Upload: save to R2 immediately, show photo, no ML blocking

**Local (Nolan's Mac):**
- Batch face detection with buffalo_l
- Embedding generation, clustering, quality scoring
- Batch Gemini enrichment
- Ground truth pipeline

**Future (Session 56+):**
- Client-side face detection in browser (MediaPipe Face Detection — NOT face-api.js, which is abandoned)
- Server only does embedding comparison (numpy, no InsightFace)
- Docker image returns to ~200MB
- Face lifecycle states (AD-111) — implement with Postgres migration
- Serverless GPU (Modal) — revisit at community scale (50+ users, 2000+ photos)

---

## UX Prioritization Reasoning

### Tier 1 (Fix Now) — These prevent core use cases
- **640px resize**: Single biggest performance lever. InsightFace runs detection at 640x640 internally. Sending 1024px just wastes compute.
- **Real upload testing**: The "tests pass but production broken" pattern. Must actually test uploads.
- **buffalo_sc**: 3-5x faster detection. But must verify embedding compatibility first.
- **Upload persistence**: If photos vanish on Railway restart, the feature is useless.
- **"Try Another" flow**: Users get stuck after first comparison.

### Tier 2 (Fix Soon) — Important for growth
- **Lazy loading**: 271 images load fine but at 500+ this will break mobile
- **Bounding boxes**: Multi-face selection is confusing without visual indicators
- **Activity feed**: Only 2 entries makes the app feel dead
- **Landing page**: First impression matters for the community sharing use case
- **404 semantics**: Proper HTTP helps with SEO and link sharing

### Tier 3 (Later) — Nice to have
- **Breadcrumbs**: Helpful but not blocking anyone
- **Infinite scroll**: Needed at scale, not yet
- **Progressive processing**: Nice UX but spinner + good messaging is sufficient

### Rejected
- **Service worker / offline**: Heritage archive is inherently an online experience. Users browse photos over the internet. Offline capability adds complexity for almost zero user benefit at this scale.
- **Full Redis/BullMQ job queue**: Overkill for 271 photos and single admin. The simple hybrid (cloud lightweight + local heavy) is sufficient. Revisit at 1000+ photos or multi-user.
- **Modal/Serverless GPU now (Session 56)**: Scale mismatch. Adds distributed systems complexity (API keys, networking, cold starts, cost monitoring) for 3 community users. Revisit at 50+ users.
- **Face lifecycle state model + job table now**: Requires data layer changes incompatible with JSON files. Save for Postgres migration (Phase F).
- **Remove ML from serving path immediately**: Breaks compare today. Need buffalo_sc + 640px intermediate step first.

---

## Nolan's Feedback From This Conversation

Key quotes and requirements:
- "I have absolutely no faith that any part of it works at this point" — trust deficit from repeated "tests pass, production broken" pattern
- "If we don't have those instantaneous responses to uploads and on site interactions it is hard for this to scale beyond a personal tool" — the interactive UX is make-or-break
- "I think this is a solved problem" — referring to the ML architecture question
- "We do not want to reinvent the wheel" — look at existing tools (Facebook, Immich, PhotoPrism) and adopt their patterns
- "I think we've been kind of just poking around here without coming up with a clear consistent plan" — the architecture drift is the core problem
- Wants every UX issue tracked with clear disposition
- Wants context engineering best practices applied (breadcrumbs, lineage, harness updates)
- Interactive session (49B) is overdue and needs to be scheduled

---

## External Review Evaluation (Post-Session Research)

Two external reviewers (Nolan's assistant and an independent expert) evaluated the Session 54 plan and proposed alternative architectures. Their ideas were critically assessed, with some adopted and others rejected.

### What We're Adopting

| Idea | Source | Why |
|------|--------|-----|
| **Serving Path Contract** as named invariant | Expert | This is the missing principle that explains all the drift. Core of AD-110. The web request path MUST NEVER run heavy ML. |
| **Face Lifecycle States** as a design concept | Expert | Excellent model (UPLOADED → DETECTED → EMBEDDED → IDENTIFIED → VERIFIED), but document as future design, not implement tonight on JSON files. Requires Postgres. |
| **MediaPipe over face-api.js** | Both | MediaPipe is actively maintained, better models, lower overhead. face-api.js is essentially abandoned. |
| **Processing Timeline UI** | Expert | Trust restoration — show per-photo status ("Uploaded ✔ → Faces detected ⏳"). Add to Tier 2 / Session 55. |
| **Modal/Serverless GPU** as documented long-term path | Assistant | Right evolution after client-side detection, wrong to implement now. |
| **Confidence scores per identification** | Expert | Great genealogy-specific product idea — add to backlog. |
| **Identity voting / community verification** | Expert | "Wikipedia for historical faces" — add to backlog. |
| **Observability > tests** framing | Expert | Test pyramid is inverted. 2480 unit tests but production failures are cross-service and UX-timing. Add to context. |

### What We're Rejecting

| Idea | Source | Why |
|------|--------|-----|
| **Implement Modal in Session 56** | Assistant | Scale mismatch. 271 photos, 3 users, single admin. Too much distributed systems complexity too early. |
| **Implement state model + job table NOW** | Expert | Requires data layer changes incompatible with JSON files. Save for Postgres migration (Phase F). |
| **Skip buffalo_sc / 640px optimization** | Expert | Getting compare from 65s to 10s is the single most impactful trust move this week. |
| **Skip lazy loading** | Expert | Timeline is already 443KB. This is a real UX issue, not premature optimization. |
| **Remove ML entirely from serving path NOW** | Expert | Breaks compare. Need the intermediate step first. |
| **Rewrite the entire prompt around Modal** | Assistant | Drops all operational work (testing, harness, UX tracker). |

### Key Insight From the Expert

The expert's most valuable contribution: "You are not blocked by ML speed. You are blocked by lack of a serving-path contract." This reframes the entire architectural drift as a missing invariant, not a missing technology. Once you name the contract ("web requests NEVER run heavy ML"), architecture decisions become obvious and the trust returns.

The expert also correctly identified that the test pyramid is inverted — 2480 tests proving data logic works in isolation, while actual failures are cross-service, async, environment, and UX-timing issues. Future sessions should shift testing investment toward observability and integration coverage.

---

## Files To Update (Checklist)

- [ ] ALGORITHMIC_DECISIONS.md → AD-110 (hybrid ML architecture with Serving Path Contract)
- [ ] ALGORITHMIC_DECISIONS.md → AD-111 (face lifecycle states — future design)
- [ ] ALGORITHMIC_DECISIONS.md → AD-112 (Modal/serverless GPU — rejected for now)
- [ ] ALGORITHMIC_DECISIONS.md → AD-113 (remove ML from serving path — rejected as premature)
- [ ] CLAUDE.md → ML Architecture summary rule (with Serving Path Contract invariant)
- [ ] ROADMAP.md → Updated session plan (54, 49B, 55 with Processing Timeline UI, 56 with MediaPipe)
- [ ] BACKLOG.md → New items from UX audit + architecture + external review (confidence scores, identity voting, processing timeline, observability)
- [ ] docs/HARNESS_DECISIONS.md → Any new process decisions
- [ ] docs/ux_audit/UX_ISSUE_TRACKER.md → NEW: master list of all issues
- [ ] docs/ux_audit/UX_AUDIT_README.md → NEW: how to use the audit framework
- [ ] docs/ux_audit/PROPOSALS.md → Updated with new prioritization
- [ ] docs/ux_audit/FIX_LOG.md → Add Session 54 fixes
- [ ] docs/session_context/session_54_log.md → Session log
- [ ] docs/session_context/session_54_prompt.md → This prompt (amended with external review)
- [ ] docs/session_context/session_54_context.md → This context file (amended with external review)
