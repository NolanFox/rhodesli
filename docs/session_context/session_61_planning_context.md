# Session 61 Planning Context
# "Gemini Photo Detective + Multi-Photo Compare + ML Iteration Loop"

## Source: Claude research conversation, Feb 22, 2026
## Breadcrumbs: Session 60 → 60B verification → planning conversation → Session 61

---

## 1. SESSION LINEAGE — 60 → 60B → 61 RECONCILIATION

### Why This Section Exists
Session numbering drifted across multiple conversations. This section
is the authoritative record of what happened and what belongs where.
Future sessions: if you see conflicting session numbers in ROADMAP,
BACKLOG, or docs, THIS section is the source of truth.

### Session 60 (shipped)
- Gemini Progressive Refinement architecture scaffolded
- SSE upload progress framework built
- Admin/public UX unification started
- Enriched prompt builder EXISTS in codebase

### Session 60B (verification pass)
- Found: enriched prompt builder NOT wired to Gemini API calls
- Found: quick-identify CSS selector crash on legacy face IDs
- Produced UX recommendations prioritizing community contribution
- No new code shipped — verification + gap identification only

### What Was Previously Called "60C"
There was no formal 60C session. The work that would have been 60C
(fixing 60B gaps) is folded into Session 61 as ACT 0. This is the
correct approach — the gaps are small enough to fix as preamble
rather than warranting a separate session number.

### Session 61 (this session) Covers:
1. Fix 60B gaps (quick-identify CSS, audit state) — ACT 0
2. Wire enriched prompt → Gemini API + MLflow — ACT 1
3. Multi-photo upload — ACT 2
4. Photo Detective UX — ACT 3
5. Data storage verification — ACT 4
6. Documentation, ROADMAP/BACKLOG sync, harness hardening — ACT 5

### Post-61 Work (DO NOT implement in 61, just track)
See Section 9 below for the full post-61 plan.

---

## 2. SESSION 60/60B STATUS — WHAT ACTUALLY SHIPPED VS WHAT DIDN'T

### Shipped (Session 60)
- Gemini Progressive Refinement architecture scaffolded
- SSE upload progress framework built
- Admin/public UX unification started
- Enriched prompt builder EXISTS in codebase

### Critical Gap Found in 60B
- **The enriched prompt builder is NOT wired to actual Gemini API calls**
  - The function that constructs context-enriched prompts (with verified facts,
    confirmed identities, known dates) exists
  - But no code path actually SENDS this enriched prompt to the Gemini API
  - This means progressive refinement is architecture without execution
- **Quick-identify CSS selector crash on legacy face IDs** — needs fix
- **UX recommendations from 60B** prioritize community contribution features

### What This Session Must Fix
1. Wire enriched prompt builder → Gemini 3.1 Pro API call
2. Fix quick-identify CSS crash
3. Close any remaining 60 gaps before advancing

---

## 3. GEMINI 3.1 PRO — RESEARCH SUMMARY

### Model Details (Released Feb 19, 2026)
- **Model string**: `gemini-3.1-pro-preview`
- **Pricing**: $2.00/1M input, $12.00/1M output (same as 3 Pro)
- **ARC-AGI-2**: 77.1% (vs 31.1% for 3 Pro — 2x+ reasoning)
- **SWE-Bench Verified**: 80.6%
- **Context window**: 1M tokens input, 64K output
- **Vision**: Improved bounding box, spatial reasoning
- **Thinking levels**: Low/Medium/High (control reasoning budget)

### Model Strategy for Rhodesli
| Use Case | Model | Reasoning |
|----------|-------|-----------|
| Bulk date labeling | gemini-3-flash | Cost-efficient, ~$0.003/photo |
| Detailed analysis / evidence | gemini-3.1-pro-preview | Best reasoning, ~$0.028/photo |
| Real-time upload analysis | gemini-3-flash | Speed for interactive use |
| Face alignment (PRD-015) | gemini-3.1-pro-preview | Needs best vision + bbox |
| Progressive refinement re-runs | gemini-3.1-pro-preview | Reasoning about verified facts |

### Cost for Full Library Comparison
- 271 photos × Flash: ~$0.81
- 271 photos × 3.1 Pro: ~$7.60
- 20-photo eval subset: ~$0.06 (Flash) / ~$0.56 (Pro)
- **Total for Flash+Pro comparison on 20 photos: ~$0.62**

### API Call Example
```python
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-3.1-pro-preview",
    contents=[image_part, prompt_text]
)
```

---

## 4. MLFLOW — EXPERIMENT TRACKING STRATEGY

### Why MLflow Here
- Track Flash vs Pro comparison metrics systematically
- Log every Gemini API call with full provenance
- Compare CORAL vs Gemini vs enriched-Gemini date estimates
- Portfolio piece: shows MLOps maturity to interviewers

### Experiment Structure
```
Experiment: "rhodesli-date-estimation"
├── Run: "gemini-3-flash-baseline" (271 photos)
├── Run: "gemini-3.1-pro-eval-20" (20 photo subset)
├── Run: "enriched-prompt-v1" (photos with verified facts)
└── Run: "coral-v1-baseline"
```

### Key Metrics to Track
- `decade_agreement`: % where Flash and Pro agree on decade
- `evidence_richness`: count of evidence categories per photo
- `cost_per_photo`: actual API cost tracked per call
- `delta_vs_known`: distance from confirmed dates (ground truth)
- `enrichment_impact`: change in estimate after adding verified facts

---

## 5. MULTI-PHOTO UPLOAD — COMPETITIVE RESEARCH

### Current State
- Face Compare accepts ONE photo at a time
- User must complete full flow, then start over for second photo
- This is a blocking UX gap — every competitor supports batch

### Rhodesli Differentiators
1. Upload 2+ photos → compare THEM against each other AND against archive
2. Multi-face detection in each photo → cross-match all faces
3. Every uploaded photo gets saved for archive processing
4. Date estimation runs on every upload automatically
5. Gemini evidence displayed for each photo — "photo detective" UX

### Upload → Pipeline Flow (MUST BE VERIFIED)
1. User uploads photo(s) → saved to R2 `uploads/compare/`
2. InsightFace → face detection + embeddings (immediate)
3. CORAL ONNX → decade estimate (immediate, if available)
4. Compare embeddings to archive → match proposals (immediate)
5. Gemini 3.1 Pro → evidence-based analysis (background)
6. Results displayed progressively via SSE
7. All photos enter admin queue for archive consideration
8. **Approved photos join next batch processing run**

---

## 6. DATA STORAGE VERIFICATION CHECKLIST

Must confirm stored in Supabase/Postgres:
- [ ] Confirmed identities (names, face IDs)
- [ ] Birth years (ground truth anchors)
- [ ] Date estimates (Gemini + CORAL)
- [ ] Gemini API call logs (prompt, response, cost, model)
- [ ] Upload metadata (who uploaded, when, status)
- [ ] Match proposals and admin decisions
- [ ] Photo metadata (dates, locations, collections)

Acceptable in JSON (performance cache, rebuilt from DB):
- [ ] Face embeddings, ML model artifacts, photo index

---

## 7. GIT WORKTREES + SUBAGENTS — PARALLELIZATION PLAN

### Parallelization Opportunities for Session 61
| Worktree | Task | Dependencies |
|----------|------|-------------|
| `main` | Orchestrator: context management, verification | None |
| `ml-pipeline` | Wire enriched prompt → Gemini API, MLflow | None |
| `multi-upload` | Multi-photo upload UX + backend | None |
| `ux-detective` | "Photo Detective" UX surface | After ml-pipeline |

### Rules for Worktree Use
- Only parallelize truly independent work
- Merge back to main after each worktree completes
- Run full test suite after each merge
- Don't parallelize if tasks touch same files

---

## 8. FUNDAMENTAL GOALS + DEPLOYMENT TOOLING

### App Goals
1. **Usable by others** — real community members, not just Nolan
2. **Expandable** — beyond Rhodes, platform for heritage archives
3. **Community adoption** — people contribute and return
4. **Portfolio piece** — demonstrates ML/MLOps maturity for job search

### "Photo Detective" Framing
Gemini analyzing a photo = detective examining evidence:
clothing → era, architecture → location, text → language/place,
faces → age/family, cultural markers → community identification.
**This detective metaphor should be THE UX framing.**

### Deployment & Testing Tooling
- **Deploy via**: `git push` → Railway auto-deploys (NOT Railway dashboard)
- **Browser testing**: Claude Chrome (preferred), Playwright as fallback
- **Upload testing**: `curl` against production endpoints
- **Smoke test**: mandatory after every deploy
- **Session history**: update SESSION_HISTORY.md when trimming ROADMAP

---

## 9. POST-61 WORK — WHAT COMES NEXT

This section ensures context isn't lost between sessions. These items
should be added to BACKLOG.md during ACT 5, NOT implemented in 61.

### Session 62 Candidates (pick 1-2)
- **PRD-015 face alignment** — portfolio crown jewel, uses 3.1 Pro
  vision + bbox. Deferred from sessions 53, 54, 60.
- **Run Flash vs Pro comparison** — costs ~$0.62 for 20 photos.
  Script created in 61, needs Nolan's approval to run.
- **Similarity calibration LoRA** — from ML plan (date est → sim cal → LoRA)

### Queued (needs Nolan approval)
- Run `compare_models.py --photos 20` (~$0.62)
- Run full 271-photo re-analysis with 3.1 Pro (~$7.60)

### Long-term Backlog Items (preserve, don't lose)
- GEDCOM re-import with improved matching
- Landing page refresh with live data entry points
- Community voting/verification system
- NL archive query (LangChain, deferred)
- Batch identity confirmation workflow

### PRD/AD Breadcrumbs
- PRD-015 (Gemini face alignment) → NOT implemented, deferred
- AD-090 (face coordinate approach) → deferred until after 61
- Session 57 (CORAL) → ground truth anchors = verified birth years
- Session 55/55b (similarity calibration) → calibrated thresholds in use
- Session 60/60B → enriched prompt builder exists, not wired

---

## 10. HARNESS HARDENING REQUIREMENTS

### Problem
Sessions 47, 49C, 60, and this planning conversation all suffered
from context compaction losing later phases. This erodes trust and
wastes time. Session 61 must include harness improvements.

### Required Harness Updates (ACT 5)
1. **ROADMAP conflict check**: Before updating ROADMAP.md, read the
   current version and diff against planned changes. Flag any items
   that would be overwritten or lost. Print the diff.
2. **BACKLOG dual-update rule**: Every ROADMAP checkbox change must
   have a corresponding BACKLOG status update. The rule must be in
   CLAUDE.md or .claude/rules/.
3. **Session context breadcrumbs**: Every session_context file must
   link to its predecessor AND list what post-session work was deferred.
4. **Doc size enforcement**: ROADMAP < 150 lines, no doc > 300 lines.
   If a doc exceeds limits, split it — don't truncate.
5. **Post-session verification**: Re-read original prompt at session end
   and verify every phase/act was completed. This is already in the
   prompt but Claude Code sometimes skips it during compaction.
