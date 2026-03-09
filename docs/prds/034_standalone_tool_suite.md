# PRD-034: Standalone Tool Suite — Community-Agnostic Heritage Tools

**Author:** Session 94 (consolidated from PRODUCT-001 through PRODUCT-006)
**Date:** 2026-03-08
**Status:** Planning
**References:** AD-131/132/133, PRD-031/032/033, ROADMAP.md

---

## Vision

Rhodesli has built three genuinely novel ML capabilities that have no good
automated equivalent anywhere:

1. **Face Comparison** — Upload two photos, detect faces, compare with calibrated
   confidence scores (InsightFace + isotonic regression, AUC 0.9577)
2. **Historical Photo Date Estimation** — Upload an old photo, get a decade-level
   date range with visual evidence (Gemini vision + GEDCOM cross-referencing)
3. **Historical Photo Location Estimation** — Upload a photo, get a geographic
   estimate with confidence (Gemini vision + GEDCOM biographical data)

These engines are production-proven on 299 photos with community-validated results.
Today they are wired exclusively into the Rhodesli archive. The standalone tool
suite makes them available to anyone — genealogists, archivists, antique dealers,
history enthusiasts — without needing to know about the Rhodes community.

**Strategic role:** These tools are the top of the funnel. Someone discovers the
standalone tool, uses it, gets value, then learns about the archive. They serve
as both portfolio pieces and potential revenue products.

---

## Design Principle: "Front Door for Strangers" (AD-131)

> `/facecompare` = "front door for strangers" (entry point for discovery)
> `/compare` = "tool for residents" (archive members)

This principle from Session 59 applies to all three tools. Each has two modes:

| Mode | Audience | Data Source | Example URL |
|------|----------|-------------|-------------|
| **Standalone** | Anyone on the internet | User's upload only | `/facecompare`, `/dateaphoto`, `/locateaphoto` |
| **Archive-integrated** | Community members | Rhodesli archive + user upload | `/compare`, `/estimate` |

Both modes share the same ML engine. The standalone versions use
community-agnostic language ("historical archive" per AD-132).

---

## Three Tools — Current State

### Tool 1: Face Compare

| Aspect | Status | Details |
|--------|--------|---------|
| **Engine** | Production | InsightFace buffalo_l + isotonic calibration (AUC 0.9577) |
| **Archive version** | Shipped | `/compare` — two-slot design, archive face search, multi-target (Session 85c) |
| **Standalone version** | Partially shipped | `/facecompare` — routes exist (`app/match_facecompare_routes.py`), 34+ tests, but limited to pre-computed archive embeddings |
| **Real-time compare** | Blocked | Cannot embed uploaded photos on-the-fly without ONNX export (AD-110, PRD-031) |
| **PRDs** | PRD-026 (workspace), PRD-031 (Tier 2 architecture) |
| **Key decisions** | AD-131 (standalone separation), AD-132 (community-agnostic language), AD-133 (three ML systems), AD-117 (tier architecture) |
| **Blocker** | ONNX export of InsightFace buffalo_l for CPU inference on Railway |
| **Stub deployed** | `/api/v2/compare/status` returns 501 not_implemented (`app/compare_v2_routes.py`) |

**What's needed to unblock:**
1. Export InsightFace buffalo_l to ONNX (~200MB model)
2. Validate embedding consistency (cosine similarity > 0.999 vs PyTorch)
3. Benchmark CPU inference time (target: <3s per photo)
4. Wire ONNX into `/facecompare` upload flow
5. Add isotonic calibration to real-time results

**Alternative path:** ML service extraction (see `docs/architecture/ML_SERVICE.md`)
— run InsightFace on a separate Railway service or GPU provider, web app calls
it via HTTP. Estimated cost: $10-20/month (Railway internal) or $0.01-0.05/call
(serverless).

### Tool 2: Historical Photo Date Estimation

| Aspect | Status | Details |
|--------|--------|---------|
| **Engine** | Production | Gemini 3.1 Pro vision analysis, 296 photos processed |
| **Archive version** | Shipped | `/estimate` — upload photo, get evidence cards (Session 61+) |
| **Standalone version** | PRD written | PRD-033, extraction plan complete, code identified |
| **Blocker** | None — engine works, Gemini API cost is $0.01-0.05/photo |
| **PRD** | PRD-033 (`docs/prds/033_date_estimator_standalone.md`) |
| **Key decisions** | AD-139 (Gemini 3.1 Pro), AD-142 (evidence card UX), AD-211 (batch reanalysis) |

**This is the lowest-hanging fruit.** The engine is fully functional, there are no
GPU/ONNX blockers, and the Gemini API cost is pennies per photo.

**Code to extract from Rhodesli:**

| Module | Source Location | Standalone Version |
|--------|----------------|-------------------|
| Gemini prompt engineering | `rhodesli_ml/gemini_config.py` | `date_estimator/prompts.py` |
| Response parsing + extraction | `rhodesli_ml/gemini_extraction.py` | `date_estimator/parser.py` |
| Evidence card UI | `app/estimate_routes.py` | `date_estimator/ui/cards.py` |
| API call logging | Supabase `gemini_api_calls` table | `date_estimator/logging.py` |

**Revenue model (from PRD-033):**

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | 3 photos/month, basic date range |
| Pro | $9.99/month | 50 photos/month, detailed evidence cards |
| API | $0.10/photo | Programmatic access, bulk processing |
| Enterprise | Custom | Volume pricing, custom models |

**Unit economics:** Gemini cost $0.01-0.05/photo → 80-90% gross margin at $0.10/photo.

**Premium upsell:** "Upload your family tree (GEDCOM) for better results" — the
pipeline is uniquely powerful when biographical constraints are available.

### Tool 3: Historical Photo Location Estimation

| Aspect | Status | Details |
|--------|--------|---------|
| **Engine** | Production | Gemini vision + GEDCOM biographical context |
| **Archive version** | Shipped | `/estimate` location tab — Leaflet maps, confidence badges (Session 81) |
| **Standalone version** | No PRD yet | Same Gemini pipeline, needs extraction |
| **Blocker** | None — same engine as date estimation |
| **Key decisions** | AD-192 (GEDCOM-enriched location), AD-201 (unified Gemini prompt) |

**Shares infrastructure with Tool 2.** The Gemini prompt already analyzes both
date AND location in a single API call. Standalone location estimation is
essentially a different UI on the same response payload.

**What makes this unique:** No existing tool estimates where a historical photo
was taken from visual cues. The GEDCOM cross-referencing (e.g., "this person
was born in Rhodes and died in Tampa, so this photo was likely taken in one of
those places") is genuinely novel.

---

## Supporting Infrastructure

### ML Service Extraction (docs/architecture/ML_SERVICE.md)

The standalone tools benefit from — but don't require — ML service extraction:

```
Current:  [FastHTML + ML in one container]  →  2.5GB, 600MB RAM, 15s startup
Proposed: [FastHTML web] + [FastAPI ML]     →  500MB + 2GB, 150MB + 500MB RAM
```

**For Face Compare specifically**, ML service extraction provides an alternative
to ONNX export — run InsightFace natively on a GPU service instead of converting
to ONNX for CPU.

**For Date/Location estimation**, ML service extraction is not needed — the
Gemini API is already external.

**Critical finding (Session 94):** The ML pipeline has only been run end-to-end
**6 times in 4 months**. The local pipeline scripts are fully implemented but
almost never executed. Cloud ML eliminates this operational bottleneck. See
`docs/architecture/ML_SERVICE.md` for the full pipeline audit and reframed
problem statement.

### Multi-Collection Support (PRD-030)

The `communities` table and `global_person_links` schema (Session 91) enable:
- Multiple archives on one platform (Rhodes, Fox family, future communities)
- Cross-community person linking (same person in two archives)
- Community-scoped search and browsing

This is the foundation for the "archive marketplace" vision — standalone tools
drive traffic, archives provide context.

### Community-Agnostic Language (AD-132, Lesson 82)

All standalone tools already follow this principle:
- Use "historical archive" not community-specific names
- Collection name appears only in results
- Future: dropdown to select which archive to search against

---

## Natural Language Query (PRODUCT-003)

While not a standalone tool in the same sense as the three above, the NL query
capability (PRD-032) enables a fourth product surface: conversational archive
exploration.

| Aspect | Status |
|--------|--------|
| PRD | Written (`docs/prds/032_nl_archive_query.md`) |
| Parser | Prototype exists (`rhodesli_ml/nl_query/parse_query_intent()`) |
| Phase 1 | Rule-based intent parsing (6 intent categories, regex patterns) |
| Phase 2 | LLM-assisted parsing via Gemini Flash (~$0.001/query) |
| Blocker | Supabase query execution layer not yet built |

**Standalone potential:** A "chat with your archive" tool where any GEDCOM +
photo collection owner can upload their data and query it conversationally.
This is the PRODUCT-006 (Interactive Photo Chatbot) vision from Session 81.

---

## Interactive Photo Chatbot (PRODUCT-006)

Conversational interface for progressive photo analysis. Demonstrated in the
Asheville case study (Session 81):

> User: "This is my great-grandmother. She was born in 1900."
> System: Refines date estimate using biographical constraint.
> User: "The photo was taken at a wedding."
> System: Narrows location based on family wedding locations in GEDCOM.

Each user input becomes metadata that feeds back into the model. This is the
most ambitious standalone tool but has the highest differentiation.

---

## Extraction Readiness Matrix

| Tool | Engine Ready | UI Exists | PRD Written | Blocker | Sessions to MVP |
|------|-------------|-----------|-------------|---------|-----------------|
| Date Estimator | Yes | Yes (evidence cards) | Yes (PRD-033) | None | 2-3 |
| Location Estimator | Yes | Yes (Leaflet maps) | No — needs PRD | None | 2-3 (shares with date) |
| ML Service Extraction | Code exists | N/A | Yes (ML_SERVICE.md) | None (engineering work) | 3-4 |
| Face Compare | Partial | Yes (`/facecompare`) | Yes (PRD-031) | ML service (Phase 2) | 1-2 (after ML service) |
| NL Query | Prototype | No | Yes (PRD-032) | Supabase wiring | 3-4 |
| Photo Chatbot | Concept | No | No | LLM conversation loop | 5+ |

### Pipeline Automation Status

The local ML pipeline has **7 fully-implemented scripts** but has only been
run **6 times in 4 months** (git history of embeddings.npy). This is the
strongest argument for cloud ML — the infrastructure exists, it just never
runs because it requires manual execution on the admin's laptop.

| Pipeline Step | Automated? | Runs Where |
|--------------|------------|------------|
| Face detection on upload | Yes | Railway (PROCESSING_ENABLED=true) |
| Embedding extraction | Yes (with detection) | Railway |
| Clustering (match to identities) | **No — manual** | Nolan's laptop |
| Batch Gemini reanalysis | **No — manual** | Nolan's laptop (API calls) |
| Isotonic recalibration | **No — manual** | Nolan's laptop |
| Production sync | **No — manual** | Nolan's laptop |
| R2 crop upload | **No — manual** | Nolan's laptop |

---

## Recommended Implementation Order

### Phase 1: Date + Location Estimator Standalone (2-3 sessions)
**Why first:** Zero blockers, engine proven, highest novelty, revenue-ready.

1. Extract Gemini pipeline to standalone package
2. Build upload + results page (FastAPI or FastHTML)
3. Evidence cards for date + Leaflet map for location
4. Supabase auth + free tier rate limiting
5. Landing page with before/after examples from Rhodesli (with community consent)
6. Deploy on separate Railway service or subdomain

### Phase 2: ML Service Extraction + Automated Pipeline (3-4 sessions)
**Why second:** Removes laptop as single point of failure, unblocks Face Compare.
See `docs/architecture/ML_SERVICE.md` for full architecture.

1. Extract InsightFace into separate FastAPI service
2. Wire web app to call ML service (with local fallback)
3. Deploy as Railway internal service
4. Add automated pipeline: upload webhook → detect → embed → cluster → notify
5. Add scheduled batch: nightly recalibration + clustering

**This replaces the ONNX export approach.** Running InsightFace natively on a
dedicated service is simpler and more reliable than ONNX conversion, and it
also solves the operational dependency problem.

### Phase 3: Face Compare Real-Time (1-2 sessions, depends on Phase 2)
**Why third:** With ML service running, real-time compare is straightforward.

1. Web app sends uploaded photo to ML service for embedding
2. ML service returns 512-dim vector
3. Web app compares against cached archive embeddings
4. Calibrated scoring via isotonic regression (AD-149)
5. Shareable result pages with OG cards

### Phase 4: NL Query + Chatbot (3-5 sessions)
**Why fourth:** Depends on solid data layer + proven standalone patterns.

1. Wire `parse_query_intent()` to Supabase queries
2. Build conversational UI
3. GEDCOM upload for premium context
4. Progressive refinement loop

---

## Unified Product Identity

All standalone tools should share:

- **Domain:** A single tools domain (e.g., `tools.nolanandrewfox.com` or a
  dedicated product domain)
- **Design system:** Archival aesthetic (DD-001) with museum-quality evidence
  presentation (Lesson 84)
- **Auth:** Shared Supabase project for user accounts across all tools
- **Billing:** Shared Stripe integration (if monetized)
- **Analytics:** Shared PostHog project for cross-tool funnel analysis

### Portfolio Value

Each tool is a portfolio piece demonstrating:

| Tool | ML Capability Demonstrated |
|------|---------------------------|
| Face Compare | InsightFace detection + PFE embeddings + isotonic calibration |
| Date Estimator | Gemini vision prompt engineering + evidence extraction |
| Location Estimator | Gemini + GEDCOM cross-referencing + geographic inference |
| NL Query | Intent parsing + structured data retrieval |
| Photo Chatbot | Multi-turn LLM conversation + progressive refinement |

AD-133 captures this: "Upload a photo and my system detects faces, finds matches
with calibrated confidence, and estimates the decade — all on a $5/month server."

---

## Existing Code & Artifacts Index

| Artifact | Location | Description |
|----------|----------|-------------|
| Face Compare routes | `app/match_facecompare_routes.py` | Shipped standalone `/facecompare` (Tier 1) |
| Compare v2 stub | `app/compare_v2_routes.py` | 501 not_implemented endpoint |
| Compare tests | `tests/test_facecompare.py` (34+), `tests/test_compare.py` (99+) | Golden test suites |
| Date/Location engine | `rhodesli_ml/gemini_config.py`, `rhodesli_ml/gemini_extraction.py` | Gemini prompt + parsing |
| Evidence card UI | `app/estimate_routes.py` | Date + location result rendering |
| NL query parser | `rhodesli_ml/nl_query/` | Rule-based intent parsing prototype |
| ML service architecture | `docs/architecture/ML_SERVICE.md` | Service extraction plan + pipeline audit + reframed problem statement |
| Multi-collection schema | `docs/prds/030_multi_collection.md` | Community scoping + global person links |
| Face Compare Tier 2 PRD | `docs/prds/031_face_compare_tier2.md` | ONNX architecture + API specs |
| NL Query PRD | `docs/prds/032_nl_archive_query.md` | Intent categories + query pipeline |
| Date Estimator PRD | `docs/prds/033_date_estimator_standalone.md` | Revenue model + extraction plan |
| AD-131 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Standalone `/facecompare` separation |
| AD-132 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Community-agnostic language policy |
| AD-133 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Three ML systems in one flow |
| AD-110 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Serving Path Contract (no heavy ML in web) |
| AD-117 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Face Compare tier architecture |
| AD-139 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Gemini 3.1 Pro selection |
| AD-142 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Evidence card UX pattern |
| AD-149 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Isotonic similarity calibration |
| AD-192 | `docs/ml/ALGORITHMIC_DECISIONS.md` | GEDCOM-enriched location estimation |
| AD-201 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Unified Gemini prompt (date + location) |
| AD-211 | `docs/ml/ALGORITHMIC_DECISIONS.md` | Batch GEDCOM reanalysis |
| Lesson 81 | `tasks/lessons/ui-lessons.md` | Separate `/facecompare` from `/compare` |
| Lesson 82 | `tasks/lessons/ui-lessons.md` | Community-agnostic language for ML tools |
| Lesson 84 | `tasks/lessons/ui-lessons.md` | Museum-quality design for ML demos |
| DD-001 | `docs/DESIGN_DECISIONS.md` | Archival aesthetic direction |

---

## Success Metrics (Standalone Suite)

| Metric | Target (6 months post-launch) |
|--------|-------------------------------|
| Monthly active users (all tools) | 2,000 |
| Photos analyzed (date + location) | 10,000 |
| Face comparisons | 5,000 |
| Pro conversions | 5% of free users |
| Revenue (if monetized) | $500/month |
| Portfolio page views | 1,000/month |
| Archive referrals (standalone → Rhodesli) | 100/month |
