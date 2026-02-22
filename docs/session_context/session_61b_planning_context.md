# Session 61B Planning Context
# "Verify, Optimize, Assess — Closing the Loop"

## Source: Claude research conversation, Feb 22, 2026
## Breadcrumbs: Session 60/60B → 61 shipped → 61 assessment → this planning → 61B

---

## 1. SESSION 61 ASSESSMENT — RED FLAGS

### What 61 Shipped (v0.64.0, 7 commits, 3232 tests)
- ACT 0: Diagnosed enriched prompt gap
- ACT 1: ML Pipeline — enriched prompt wiring, Gemini 3.1 Pro, MLflow
- ACT 2: Multi-photo compare upload (PRD-021)
- ACT 3: Photo Detective UX — evidence cards, model badges (PRD-022)
- ACT 4: Data storage verification, integrity report
- ACT 5: Docs — AD-139-142, harness rules

### Red Flags Requiring Verification
1. **No browser/curl verification mentioned** — prompt said "Start app
   and verify EVERY change in browser/curl" but summary has no evidence
   of this. Multi-photo upload is high-risk for production breakage.
2. **Quick-identify CSS crash may not be fixed** — ACT 0 says "diagnosed
   enriched prompt gap" but doesn't mention CSS fix from 60B.
3. **Harness rules may not have landed** — ACT 5 says "harness rules"
   but unclear if dual-update rule, deploy rules, session breadcrumbs
   actually were added to CLAUDE.md / .claude/rules/.
4. **ROADMAP/BACKLOG conflict check** — no mention of pre-edit backup
   or diff verification in summary.
5. **Test count suspiciously high** — 3232 tests from 37 min across
   6 ACTs including PRDs, ADs, UX, backend, MLflow. Tests may be thin.

### Pre-Push Verification Checklist
1. `git diff HEAD~7..HEAD --stat` — what actually changed?
2. `grep -r "quick.identify\|quickIdentify" app/ --include="*.py"` — CSS fixed?
3. `grep "dual.update\|update BOTH" CLAUDE.md .claude/rules/*.md` — harness landed?
4. `diff /tmp/roadmap_pre_session61.md ROADMAP.md` — nothing lost?
5. Start app locally, hit multi-upload with 2 real photos via curl
6. `python scripts/compare_models.py --dry-run` — script exists and runs?

---

## 2. APP THESIS — CORE USES (preserve in all UX decisions)

From Nolan's own words across multiple conversations:

### What Rhodesli Does
- Help people **identify photos** if they know a person who is unidentified
- **Share photos** with unidentified people to ask for help identifying them
- Help people **find photos with relatives** they didn't know existed
- **Solve mysteries** through photo context and who was present
- **Deepen understanding** through annotation and community knowledge
- **Systematize what happens on Facebook** — the platform automates
  and structures the posts like "who is this person" / "here is a photo
  of my family" / "what do you know about this person"

### Why It Matters
- Facebook posts get buried after a few days
- No easy way to surface historical identification discussions
- Data science can solve the problem of organizing scattered knowledge
- More uploads = more match chances
- More identifications = more people in the system = higher match odds
- Merging similar faces improves model accuracy for the next match

### Growth Loop
Find interesting thing → Share → Preview drives click → Visitor
recognizes someone → Submits response (no login) → Explores archive
→ Uploads their own photos → Cycle repeats

### Data Sources (ordered by accessibility)
1. Personal collections already scanned (e.g., Vida's, Nace's)
2. Facebook groups: Jews of Rhodes, Children of Rhodes
3. Ancestry.com collections
4. Large organized personal collections (Claude Benatar's, Aron's)
5. Books, synagogue archives, Rhodes municipal archives
6. Individual contributions (1-2 photos each, at scale)

**Every UX decision should be evaluated against these goals.**

---

## 3. GEMINI API OPTIMIZATION — RESEARCH FINDINGS

### The Question: Should We Batch All Extractions Into One Call?

Currently (or planned) Rhodesli extracts from each photo:
- Date/year estimation + evidence
- Face age estimation (per face, using coordinates)
- Location identification + evidence
- Cultural/community markers
- Clothing era analysis
- Photographic technique analysis
- Text/signage detection

### Answer: YES — One Call Is Almost Always Better

**Token economics**: Input tokens (the image) are paid once regardless
of how many questions you ask about it. The image is ~258 tokens for
a typical photo. The prompt text for all extractions might be ~500-800
tokens. Asking 7 separate questions = 7× image tokens + 7× prompt
overhead. One combined prompt = 1× image + 1× larger prompt.

**Savings estimate for 271 photos**:
- 7 separate calls: 271 × 7 × ~$0.028 = ~$53
- 1 combined call: 271 × 1 × ~$0.04 = ~$11 (larger output)
- **~80% savings from batching into single call**

**Quality impact**: Research shows VLMs handle multi-task prompts well
when tasks are clearly structured. Gemini 3.1 Pro's 64K output limit
means even detailed multi-extraction responses won't hit output ceiling.

**Risk**: If prompt gets too long or tasks too diverse, quality can
degrade. Mitigate with structured JSON output schema.

### Recommended Architecture: Configurable Extraction Config

```python
EXTRACTION_PRESETS = {
    "full": {  # All extractions, used for detailed analysis
        "date_estimation": True,
        "face_analysis": True,  # needs face coordinates
        "location": True,
        "cultural_markers": True,
        "clothing_era": True,
        "photo_technique": True,
        "text_signage": True,
    },
    "quick": {  # Fast estimate for interactive upload
        "date_estimation": True,
        "face_analysis": False,  # too slow for interactive
        "location": True,
        "cultural_markers": False,
        "clothing_era": False,
        "photo_technique": False,
        "text_signage": True,
    },
    "compare": {  # For face compare uploads
        "date_estimation": True,
        "face_analysis": True,
        "location": False,
        "cultural_markers": False,
        "clothing_era": False,
        "photo_technique": False,
        "text_signage": False,
    },
}
```

The prompt builder should accept a preset OR manual include/exclude,
so any call site can customize what it asks for.

### Additional Extractions to Consider
- **Handwriting analysis** (back of photos often have inscriptions)
- **Group composition** (formal portrait vs candid vs ceremony)
- **Photo condition** (damage, fading — helps prioritize restoration)
- **Relationship inference** (who is standing together, body language)

### Batch API (50% Discount)
For bulk re-analysis of 271 photos: use Gemini Batch API at 50% off.
Not for interactive use (24hr SLA). Perfect for overnight runs.

---

## 4. SELF-ASSESSMENT PATTERN — RESEARCH

### The Problem
Sessions ship, summaries look clean, but red flags hide. The human
must manually review and create a "B" session to verify. This should
be automated into the session itself.

### Builder-Validator Pattern (from Claude Code community)
The "ClaudeCodeAgents" project (github.com/darcyegb/ClaudeCodeAgents)
provides specialized QA agents:
- **Jenny**: verifies implementations match specifications
- **Karen**: realistic project completion assessment
- **Verification agent**: confirms claimed completions are functional

Key insight: "The real friction usually comes from incomplete
execution — the agent forgets a file, a barrel export is missing,
types don't align. You discover it only during review."

### Self-Validating Agent Pattern
Embed quality checks INTO the agent's workflow. The agent cannot
produce unchecked output. Instead of treating validation as a human
responsibility after the fact, each phase validates itself.

### Proposed Pattern for Rhodesli Sessions

Add a **Final ACT: Self-Assessment** to every session prompt:

```
## FINAL ACT: SELF-ASSESSMENT (mandatory, cannot be skipped)

1. Re-read the ORIGINAL prompt (from docs/prompts/)
2. For each ACT, verify:
   a. Was it actually completed? (grep for expected artifacts)
   b. Was it tested in production? (curl/browser evidence)
   c. Were there any silent failures?
3. Run the verification gate
4. Write a CRITICAL assessment:
   - What shipped and what evidence proves it works
   - What was deferred and WHY
   - What red flags exist
   - What the NEXT session should verify first
5. If ANY red flag is found:
   a. Attempt to fix it (max 5 min per flag)
   b. If unfixable, add to BACKLOG as P0 with breadcrumb
6. Save assessment to docs/session_context/session_NN_assessment.md
```

### Hooks for Automated Verification
Claude Code hooks can run after every commit:
```yaml
# .claude/hooks/post-commit.sh
pytest tests/ -x -q --tb=short
wc -l ROADMAP.md | awk '{if ($1 > 150) print "ROADMAP too long!"}'
```

---

## 5. DATA STORAGE + UX AUDIT PLAN

### How Gemini Data Should Be Stored
- **Supabase**: Every API call logged (photo_id, model, prompt_hash,
  result JSON, cost, timestamp). This is the persistent record.
- **MLflow**: Experiment-level tracking (run comparisons, metrics).
  Local files, acceptable to lose and rebuild from Supabase.
- **JSON cache**: Photo-level results cached for fast page loads.
  Rebuilt from Supabase on demand.

### UX for Surfacing Gemini Data (evaluate against app thesis)
The "Photo Detective" UX must serve the core goals:
1. **Discovery**: Evidence cards help users understand what era a photo
   is from, prompting "oh, that could be my grandmother's generation"
2. **Sharing**: Detective results should be shareable — "look what the
   AI found about this photo" drives engagement loop
3. **Contribution**: "Know the actual date?" CTA turns passive viewers
   into active contributors, generating ground truth
4. **Trust**: Model badge + evidence categories show users WHY the AI
   thinks what it thinks, not just a number

### Flash vs Pro Comparison UX
When both estimates exist, show:
- "Quick estimate" (Flash) vs "Deep analysis" (Pro) side-by-side
- Evidence richness comparison (Pro typically has 3-4x more evidence)
- Cost transparency ("This deeper analysis cost $0.03")

---

## 6. POST-61 WORK SCOPE

### Track A: Flash vs Pro Comparison (~15 min)
- Run `compare_models.py --photos 20` (~$0.62)
- Analyze: decade agreement, evidence richness, cost delta
- Decision: when to use Flash vs Pro going forward
- Log everything to MLflow

### Track B: PRD-015 Face Alignment (~30 min)
- Portfolio crown jewel: Gemini 3.1 Pro identifies face locations
  and associates identities with coordinates
- Bridges InsightFace bounding boxes with Gemini vision
- Solves Vida Capeluto's count mismatch problem
- Needs PRD + SDD/AD before implementation

### Track C: LoRA Similarity Calibration (research + plan)
- From ML plan: date estimation (done) → similarity calibration → LoRA
- LoRA fine-tunes the face embedding model on Rhodes-specific data
- Needs research on InsightFace LoRA feasibility + data requirements
- PRD scope only in 61B, implementation in later session
