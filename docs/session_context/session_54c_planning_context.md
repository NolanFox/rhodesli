# Session 54c Planning Context: ML Tooling Evaluation, Face Compare Product, and Roadmap Integration

## Source
- **Date:** 2026-02-20
- **Origin:** Claude web conversation (Opus) — research session evaluating long-term memory tooling, MCP integrations, ML infrastructure, and product strategy
- **Previous session:** 54b (running concurrently)
- **Participants:** Nolan (human), Claude Opus (web), Nolan's assistant (ChatGPT), Nolan's expert advisor
- **Instagram source evaluated:** James Goldbach reel on NotebookLM MCP as Claude Code long-term memory

---

## PART 1: ML TOOLING & MEMORY INFRASTRUCTURE EVALUATION

### 1A: Problem Statement

As Rhodesli's ML pipeline grows (face detection, kinship calibration, date estimation, similarity calibration, future LoRA), the number of algorithmic decisions, experiment results, and architectural choices is increasing. Nolan wanted to evaluate whether external tooling (NotebookLM MCP, Mem0, Notion MCP, LangChain, MLflow) would improve:
- Decision recall and interview readiness
- Context preservation across Claude Code sessions
- Cross-project knowledge reuse
- Experiment tracking rigor

### 1B: Tools Evaluated

#### NotebookLM MCP Server — REJECTED as primary system
- **What it is:** Community-built MCP that uses browser automation (headless Chrome) to drive NotebookLM's interface. Multiple implementations exist (PleasePrompto, jacob-bd, roomi-fields, julianoczkowski).
- **How it works:** Claude Code queries NotebookLM via MCP tools → NotebookLM's internal RAG indexes your uploaded documents → returns grounded, citation-backed answers from Gemini.
- **Strengths:** Excellent at ingesting large unstructured corpora, conversational recall, research synthesis. Good as a "read-only explainer" — e.g., "explain Rhodesli's architecture to me before an interview."
- **Why rejected:**
  - Browser automation is fragile — session cookies expire every 2-4 weeks requiring re-authentication
  - Uses undocumented internal NotebookLM APIs (not a stable foundation)
  - One implementation provides 29 tools — massive context window cost just having it enabled
  - Not code-native — poor diffing, no version control, no CI/CD integration
  - Weak structured linking between decisions
  - Hard to treat as source of truth
- **Recommendation:** Use NotebookLM manually (upload ALGORITHMIC_DECISIONS.md etc.) for interview prep when needed. Zero setup cost, 90% of the benefit.
- **Revisit condition:** Google ships a proper NotebookLM API (not browser automation).

#### Mem0 / Vector Memory MCP — REJECTED
- **What it is:** Semantic memory layer that stores and retrieves memories via embeddings. Free tier: 10,000 memories, 1,000 retrieval calls/month. OpenMemory variant runs fully local.
- **How it works:** Claude Code saves observations → Mem0 indexes them → future sessions retrieve relevant memories via semantic search.
- **Strengths:** Automatic, low-effort memory accumulation. Good for implicit preferences ("always use functional components").
- **Why rejected:**
  - No explicit reasoning chain — can't audit WHY a decision was made
  - Terrible for interviews — you can't say "here's why we chose buffalo_l over SCRFD" because it's buried in embeddings
  - Our structured ALGORITHMIC_DECISIONS.md with context/alternatives/tradeoffs fields is MORE useful for both agent recall and interview prep
  - Adds API dependency and drift risk from canonical docs
- **Revisit condition:** Project grows to 5+ repositories where implicit cross-project preferences become valuable.

#### Notion MCP — REJECTED
- **What it is:** MCP that lets Claude query Notion databases and pages directly.
- **Strengths:** Structured, relational, human-readable. Nolan knows Notion's block architecture intimately from his time there.
- **Why rejected:**
  - Creates a second source of truth that drifts from the repo
  - Not close to code — changes in Notion don't get committed
  - Duplication risk with existing in-repo docs
- **Better use:** Product planning and research that doesn't need to be in the repo. Not for system memory.

#### LangChain — NOT APPLICABLE for dev workflow, but FUTURE PRODUCT FEATURE identified
- **What it is:** Orchestration framework for building LLM-powered applications — chatbots, RAG pipelines, multi-agent systems.
- **Why not applicable now:** LangChain solves "how do I build an AI-powered product." Rhodesli's current need is "how do I organize my development decisions." Different category entirely.
- **Where it adds significant complexity:** Extra processing steps vs direct API calls, frequent breaking changes, debugging difficulty, steep learning curve for memory/agent/chain abstractions.
- **FUTURE PRODUCT FEATURE IDENTIFIED:** Natural language photo archive queries.
  - Example: "Show me photos of people who look like my grandmother from the 1930s"
  - Chain: face detection → embedding search → date filtering → natural language response
  - Would chain together existing Rhodesli capabilities (InsightFace embeddings, CORAL date estimates, identity clusters) into a conversational interface
  - This is a genuinely differentiated product feature — no existing genealogy tool offers this
  - **Priority:** AFTER core ML (similarity calibration, LoRA) and UX stabilization
  - **Estimated effort for basic MVP:** 2-3 sessions once core ML is solid
  - **Portfolio value:** Very high — demonstrates end-to-end ML pipeline + LLM orchestration
  - See new BACKLOG entry: "NL Archive Query MVP"

#### MLflow — ACCEPTED for targeted integration
- **What it is:** Open-source experiment tracking and model lifecycle platform. Logs hyperparameters, metrics, model weights, artifacts per training run. Web UI for comparing runs.
- **When it's valuable:** When running dozens+ of experiment variations. Teams doing grid search over 200 hyperparameter combos.
- **When it's overkill:** <20 total experiments, solo developer, small dataset.
- **Our situation:** ~155 photos, probably 30-50 total experiment runs across all ML work. Manual markdown logging would technically suffice.
- **Why accepted anyway:**
  1. Portfolio talking point — "Do you have MLflow experience?" → "Yes, here's my tracking UI"
  2. Minimal overhead with `mlflow.pytorch.autolog()` — ~10 lines of code
  3. Runs locally (`mlflow ui` in terminal, no server needed)
  4. New use cases identified by Nolan:
     - Track Gemini API prompt iterations for photo labeling (do different prompts yield better date/context extraction over time?)
     - Compare local ML vs web ML versions of face compare (InsightFace locally vs API-based)
  5. MLflow now has Claude autologging and MCP server integration
- **Implementation plan:** Add to CORAL date estimation training script first. Expand to Gemini prompt tracking and face compare benchmarking as those features mature.
- **What MLflow does NOT replace:** ALGORITHMIC_DECISIONS.md. MLflow tracks metrics and parameters, not reasoning and decisions. It won't help explain WHY you chose CORAL over standard regression.
- See new BACKLOG entry: "MLflow Integration"

### 1C: Key Conclusion — Current Harness Is Sufficient

The existing documentation system (ALGORITHMIC_DECISIONS.md, DECISION_LOG.md, OPS_DECISIONS.md, HARNESS_DECISIONS.md, ROADMAP.md, session_context files, .claude/rules/) is already doing a good job of minimizing context rot at the project level. The context rot Rhodesli experiences is primarily at the Claude Code session level (long sessions losing focus), which is addressed by the prompt decomposition and verification gate harness rules from Session 48.

No new memory infrastructure is needed. The focus should remain on building ML features and shipping.

---

## PART 2: FACE COMPARE STANDALONE PRODUCT

### 2A: Competitive Landscape Analysis

Researched 7+ existing face comparison tools (Feb 2026):

| Tool | Approach | Limitations |
|------|----------|-------------|
| ToolPie | Basic AI, single % score | No context, no kinship, no cross-age |
| FacePair | Browser-based, "freakishly accurate" | Single score, entertainment focus |
| ProFaceFinder | Browser-based + reverse search | Gender/age estimate bolt-on, no kinship |
| IMGonline | Overall image similarity (not face-specific) | May count background/lighting |
| MxFace | API-level face compare | Developer-focused, no consumer UX |
| pictriev | Old tool, similarity + identity modes | 200KB limit, JPEG only, dated UI |
| RauGen AI | Modern AI comparison | "Entertainment purposes only" disclaimer |

**Universal weakness:** Every tool gives a single percentage with no meaningful context. None distinguish "same person" from "family resemblance" from "coincidental similarity." None handle cross-age matching with temporal context. None are calibrated against real genealogical data.

### 2B: Rhodesli's Existing Advantages

From Session 32 (AD-067, AD-068, AD-069):
- **Kinship calibration:** Empirically derived from 46 confirmed identities
  - Same-person: 959 pairs, mean=1.01, std=0.19, Cohen's d=2.54 (strong)
  - Same-family: 385 pairs, mean=1.34, std=0.07, Cohen's d=0.43 (weak but honest)
  - Different-person: 605 pairs, mean=1.37, std=0.06
- **Tiered results:** Identity Match (green) / Possible Match (amber) / Similar Features (blue) / Other
- **CDF-based confidence:** Sigmoid approximation of empirical same-person distribution
- **Multi-face detection:** Upload group photo, select which face to compare
- **Upload persistence:** Photos saved to R2 with metadata
- **Cross-age capability:** InsightFace embeddings + CORAL temporal context

### 2C: Three-Tier Product Plan

#### Tier 1 — Minimal Viable Standalone (1-2 sessions, ~3-4 hours)
**Goal:** Public-facing face comparison tool at facecompare.nolanandrewfox.com

**What to build:**
- New FastHTML app or route at subdomain
- Same InsightFace backend, same kinship-calibrated comparison logic
- Stripped-down UI: upload two photos → get tiered results
- No account required, no persistence (photos processed and discarded after comparison)
- Clear differentiation messaging: "Calibrated against real genealogical data — not just a similarity score"
- Mobile-responsive design
- Privacy-first: all processing server-side, photos deleted after comparison

**What it shares with Rhodesli:**
- InsightFace model and embedding computation
- Kinship threshold calibration data (kinship_thresholds.json)
- Multi-face detection logic
- Tiered result display component

**What's different from Rhodesli:**
- No identity database lookup
- No archive integration
- No persistence of uploads
- No admin features
- Simpler, single-purpose UI

**Deployment:** Could be same Railway app with subdomain routing, or separate lightweight deployment.

#### Tier 2 — Rhodesli Integration Layer (2-3 additional sessions)
**Goal:** Shared backend with divergent post-comparison behavior

**Architecture:**
```
facecompare.nolanandrewfox.com (public)
  → Upload two photos
  → Get tiered comparison results
  → "Want deeper analysis? Try Rhodesli" CTA
  → Photos discarded after comparison

rhodesli.nolanandrewfox.com/compare (Rhodesli instance)
  → Same comparison engine
  → Results also show matches against archive identities
  → Uploaded photos saved to Rhodesli collection for future ML work
  → "This face matches [Known Identity X] with 87% confidence"
  → Advanced ML matching (similarity calibration, temporal context)
  → Contribute-to-archive flow
```

**Shared backend components:**
- Face detection and embedding extraction
- Kinship-calibrated distance computation
- Tiered result classification
- Multi-face selection UI

**Rhodesli-specific additions:**
- Archive identity matching (compare against all known faces)
- Upload persistence to R2 collection
- Date estimation context ("this photo is likely from ~1935")
- Identity linking ("this might be the same person as Leon Capeluto")
- Admin review queue for contributed photos

#### Tier 3 — Product-Grade (significant additional work, post-employment)
**Goal:** Standalone product with growth features

**Features:**
- User accounts, saved comparison history
- "Compare against a collection" — upload one face, match against entire album
- API access for developers (REST endpoint, authentication, rate limiting)
- Batch comparison (upload 50 photos, get all pairwise similarities)
- Shareable comparison results (link to a specific comparison)
- Celebrity lookalike mode (entertainment angle for virality)
- Family tree integration (upload family photos, auto-cluster by likely relationships)

### 2D: Related Product Idea — Historical Photo Date Estimator

**Standalone at:** facedate.nolanandrewfox.com or similar
- Upload a historical photo → estimate when it was taken
- Uses CORAL date estimation model
- Genuinely novel — no existing tool offers this for historical photos
- Could combine with face comparison: "These two photos are likely 25 years apart, consistent with the same person aging"
- **Priority:** After CORAL model is trained and validated
- **Portfolio value:** Very high — demonstrates custom PyTorch model in production

---

## PART 3: UPDATED ROADMAP PRIORITIES

### Confirmed Priority Order (from this conversation)

1. **Similarity calibration on frozen embeddings** — Very High portfolio value, directly builds on Session 32 kinship work
2. **Fix production UX issues** — phantom features, broken loading indicators, missing nav items actively hurt sharing with employers/community
3. **Face Compare Standalone Tier 1** — quick win, shippable demo, differentiated from competition
4. **CORAL date estimation training** — PyTorch portfolio centerpiece
5. **MLflow integration** — add to CORAL training, expand to Gemini prompt tracking
6. **Face Compare Tier 2** — Rhodesli integration, shared backend architecture
7. **NL Archive Query MVP (LangChain)** — after core ML is solid
8. **Face Date Estimator Standalone** — after CORAL is trained and validated

### New BACKLOG Entries to Create

| ID | Title | Priority | Source |
|----|-------|----------|--------|
| NEW | Face Compare Standalone Tier 1 | P1 | Session 54c planning context |
| NEW | Face Compare Tier 2 — Shared Backend | P2 | Session 54c planning context |
| NEW | Face Compare Tier 3 — Product Grade | P3 (deferred) | Session 54c planning context |
| NEW | MLflow Integration — CORAL Training | P2 | Session 54c planning context |
| NEW | MLflow — Gemini Prompt Tracking | P3 | Session 54c planning context |
| NEW | MLflow — Local vs Web ML Benchmarking | P3 | Session 54c planning context |
| NEW | NL Archive Query MVP (LangChain) | P3 (future) | Session 54c planning context |
| NEW | Historical Photo Date Estimator Standalone | P3 (after CORAL) | Session 54c planning context |

### New ALGORITHMIC_DECISIONS Entries to Create

| ID | Title | Status |
|----|-------|--------|
| AD-NEW | Memory Infrastructure Evaluation (Feb 2026) | Decided: current harness sufficient |
| AD-NEW | MLflow Integration Strategy | Accepted: targeted integration |
| AD-NEW | Face Compare Product Architecture | Accepted: three-tier plan |
| AD-NEW | LangChain NL Query — Deferred | Deferred: after core ML |

---

## PART 4: SKILLS AND LEARNING ROADMAP

Nolan noted: "I love how this has unveiled a lot of really valuable ML building blocks for me to master."

### ML Building Blocks Identified in This Conversation

1. **Experiment Tracking (MLflow)** — industry-standard tool, portfolio value
2. **RAG Architecture** — understanding how NotebookLM works internally (indexing + retrieval + generation)
3. **Vector Databases & Semantic Search** — understanding when they're appropriate vs. structured docs
4. **MCP (Model Context Protocol)** — Anthropic's transport layer for tool integration
5. **LLM Orchestration (LangChain/LangGraph)** — chaining models, tools, and memory
6. **Architecture Decision Records** — established software engineering practice (MADR format, 2000+ GitHub stars)
7. **Kinship Detection in Embeddings** — novel application of metric learning
8. **Cross-Age Face Matching** — InsightFace + temporal context
9. **Ordinal Regression (CORAL)** — specialized ML for ordered categories

### Interview Preparation Strategy (confirmed)
- Existing ALGORITHMIC_DECISIONS.md entries are sufficient for interview recall
- No special tooling needed — review AD entries before interviews
- NotebookLM can be used manually (upload docs, conversational review) if extra prep is wanted
- The kinship calibration honesty (d=0.43, not reliably separable) is itself an impressive interview talking point

---

## PART 5: WHAT WAS NOT DECIDED / OPEN QUESTIONS

1. **Exact subdomain structure** for face compare standalone — could be facecompare.nolanandrewfox.com or faces.nolanandrewfox.com or compare.nolanandrewfox.com
2. **Deployment architecture** for Tier 1 — same Railway app with routing vs separate deployment
3. **Whether estimate + compare should share a site** — Nolan mentioned "compare and estimate could live in one space." Could be faces.nolanandrewfox.com with /compare and /estimate routes.
4. **MLflow hosting** — local only vs. hosted tracking server
5. **LangChain vs direct API calls** for NL query MVP — might not need LangChain's overhead for a simple chain
6. **Semantic search layer timing** — when/if to add vector indexing over decision docs (current answer: not until 500+ decisions across 5+ projects)
