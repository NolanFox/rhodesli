# Session 55 Planning Context — Similarity Calibration + P1 Polish

## Strategic Context

### Two Competing Goals
1. **Portfolio** — Demonstrate PyTorch, MLOps, and production ML skills for job search (TRM Labs, Merge, Valon, etc.)
2. **Adoption** — Make Rhodesli compelling enough for the Rhodes community to actually use (3 active identifiers on Facebook)

### Why This Session (Option C Hybrid)
Session 55 is the first of a 2-session hybrid sprint:
- **Session 55:** Similarity Calibration (ML portfolio crown jewel) + Backlog Audit
- **Session 56:** Landing Page Refresh + P1 UX Polish (product-ready demo)

This combination maximizes expected value: one strong portfolio piece you can discuss in interviews AND an app you can confidently share.

### Ground Truth State (Post-49B / Post-54F)
- 54 confirmed identities
- 28 accepted birth years (including Big Leon corrected to 1902)
- 19 GEDCOM relationships
- 271 photos in archive
- ~2520 tests

These ground truth anchors are the training data for similarity calibration. Session 49E is fixing blocking bugs (Name These Faces, compare/estimate upload) that prevented full interactive review.

---

## Similarity Calibration — Technical Brief

### What It Is
Train a learned calibration layer on top of frozen InsightFace embeddings using Rhodesli's ground truth data. This directly reduces false positives in the compare tool without retraining the base model.

### Why It's the #1 Portfolio Piece
Interview sentence: "I took frozen InsightFace embeddings and trained a learned calibration layer using 54 confirmed identities as ground truth, tracked with MLflow — improving precision by X% without retraining the base model."

This demonstrates: PyTorch fluency, transfer learning intuition, MLOps maturity, judgment to improve a system incrementally.

### Technical Approach (from ML_ROADMAP.md / AD-115)
1. **Data preparation:** Extract embedding pairs from ground truth — same-person pairs (positive) and different-person pairs (negative) from confirmed identities
2. **Model:** Lightweight calibration head (2-3 FC layers) on top of frozen 512-dim InsightFace embeddings
3. **Training:** PyTorch Lightning, binary cross-entropy or contrastive loss
4. **Evaluation:** Precision/recall at various thresholds, compared to raw cosine similarity baseline
5. **Tracking:** MLflow for experiment logging (AD-116)
6. **Serving:** Export calibrated model, integrate into compare pipeline

### Breadcrumbs
- `rhodesli_ml/` — ML code directory
- `ML_ROADMAP.md` — Overall ML plan (date estimation done → similarity cal → LoRA)
- `ALGORITHMIC_DECISIONS.md` AD-115 — Calibration approach decision
- `ALGORITHMIC_DECISIONS.md` AD-116 — MLflow recommendation
- `docs/session_context/session_54c_planning_context.md` — Research on MLflow + calibration

### Key Constraints (Serving Path Contract — AD-110)
- Training runs LOCAL on Mac (heavy ML)
- Inference/serving runs on Railway (lightweight ops only)
- The calibration model must be small enough to load on Railway
- Training script must be runnable offline, outputs a model artifact

---

## Multi-Session Roadmap (Option C Expanded to A+B)

### Immediate (Sessions 55-56)
| Session | Focus | Goal |
|---------|-------|------|
| **55** | Similarity Calibration + Backlog Audit | Portfolio (ML) |
| **56** | Landing Page Refresh + P1 Polish | Adoption (Product) |

### Near-Term (Sessions 57-59)
| Session | Focus | Goal |
|---------|-------|------|
| **57** | CORAL Date Estimation Model | Portfolio (ML) |
| **58** | MLflow Integration + Experiment Dashboard | Portfolio (MLOps) |
| **59** | Face Compare Standalone Tier 1 (PRODUCT-001) | Both |

### Medium-Term (Sessions 60+)
| Session | Focus | Goal |
|---------|-------|------|
| **60** | Gemini Progressive Refinement (PRD-015 Face Alignment) | Portfolio |
| **61** | Interactive Upload UX (SSE progressive loading) | Adoption |
| **62** | Admin/Public UX Unification | Adoption |
| **63+** | Infrastructure (Docker slim, PostgreSQL, CI/CD) | Scale |

---

## Items To Audit Into Backlog/Roadmap

These items were discussed in conversations but may not be tracked. Session 55 Phase 1 must verify each is in BACKLOG.md or ROADMAP.md:

### From "What's Next" Document
- Nancy Gormezano as beta tester (Session 49C community thread)
- DNA matching integration (Leo Di Leyo Facebook comment)
- Institutional partnership (museum, archives) — discussed, no action item
- Batch Gemini run on all 271 photos (Session 50 planning)
- KIN-001: Kinship recalibration post-GEDCOM (now actionable with 19 relationships)
- Session 43: Life Events & Context Graph (deferred)
- Admin/Public UX Unification (deferred from Session 50)
- Three-mode cognitive framing (explore/investigate/curate) — adopted, not built
- Serving Path Contract enforcement (AD-110) — needs harness rule
- 127 pre-existing test failures from state pollution (Session 49B-Deploy)
- Railway CLI enforcement for debugging (HD-014)
- Architecture optimization journey documentation (54F research)
- Progressive loading UX (SSE with HTMX) — researched in 54F, not implemented
- MLflow for experiment tracking (AD-116 created, not implemented)
- Face Comparison standalone product (PRODUCT-001, three-tier strategy)
- NL query system via LangChain (scoped, deferred)
- Silent ML model fallback lesson (54F root cause) — needs harness rule
- "Six Degrees" Connection Finder (novel graph feature)
- Geographic Migration Analysis (Gemini locations + GEDCOM)

### From Session 49E (verify after it lands)
- Name These Faces end-to-end fix status
- Compare/Estimate upload save-through-gatekeeper status
- Test count reconciliation results
- Pre-existing test failure resolution
- Compact hook infrastructure

---

## P1 Issues for Session 56 (Landing Page + Polish)

These are the remaining P1s from the UX tracker (post-49D/49E fixes):
- UX-037/038: Merge direction + silent 200s on merged IDs
- UX-039: Admin controls on /person/ page
- UX-073/074: Enter key submit + Create at top of dropdown
- UX-075: Skip button in Name These Faces
- UX-045/046/054/055: Loading indicators + auto-scroll
- UX-053/056: Photo preview + CTAs in estimate upload
- UX-007/018: Lazy loading for /timeline and /photos (blocks scale to 500+)
- UX-008: Activity feed enrichment
- UX-030: Landing page refresh with live-data entry points

---

## Harness Practices Reference

### Prompt Management
- Save prompt to `docs/prompts/session_NN_prompt.md` immediately
- Parse into phases, create `docs/session_context/session_NN_checkpoint.md`
- Install SessionStart compact hook for recovery
- Re-read prompt from disk at verification gate

### Phase Execution
- Read only the relevant phase from prompt file (preserve context)
- Commit atomically per phase
- Update session log after each phase
- If context above 60%, run /compact before next phase

### Verification Gate
- Re-read original prompt
- Check every phase against acceptance criteria
- Run both test suites: `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q`
- Browser verification for UI features (Chrome extension / Playwright)
- Deploy via git push, verify with `railway logs --tail 50`

### Documentation
- No doc over 300 lines
- CLAUDE.md under 80 lines
- Update ALGORITHMIC_DECISIONS.md for ML/architectural decisions
- Update HARNESS_DECISIONS.md for process/tooling decisions
- Session logs in `docs/session_logs/`
- PRDs in `docs/prds/` — write BEFORE coding complex features
