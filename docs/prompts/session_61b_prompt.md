# Session 61B: Verify, Optimize, Assess — Closing the Loop

Read CLAUDE.md. Read all .claude/rules/*.md files.
Read CHANGELOG.md (first 10 lines).
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines).
Read ROADMAP.md. Read BACKLOG.md.

## SESSION IDENTITY
- **Session**: 61B
- **Predecessor**: Session 61 (Gemini Photo Detective + Multi-Photo + MLflow)
- **Lineage**: 60 → 60B → 61 (shipped v0.64.0) → 61B (this session)
- **Goal**: Verify 61 actually works in production, optimize Gemini API
  architecture, run Flash vs Pro comparison, create PRDs for face alignment
  and LoRA, install self-assessment pattern into harness
- **Estimated time**: 90-110 minutes
- **Context file**: `docs/session_context/session_61b_planning_context.md`
- **Post-61B planning**: Session 62 = implement PRD-015 face alignment

---

## ⚠️ CONTEXT MANAGEMENT — MANDATORY

### Before ANYTHING else:
```bash
cp docs/session_context/session_61b_planning_context.md /tmp/session_61b_context.md
cat > /tmp/session_61b_checklist.md << 'EOF'
# Session 61B Phase Checklist
# Lineage: 60 → 60B → 61 → 61B (verify + optimize)
- [ ] PHASE 0: Orient + Push + Deploy
- [ ] PHASE 1: Red Flag Verification
- [ ] PHASE 2: Production Smoke Test
- [ ] PHASE 3: UX Screenshot Evaluation
- [ ] PHASE 4: Gemini Unified Prompt Architecture
- [ ] PHASE 5: Flash vs Pro Comparison
- [ ] PHASE 6: PRD-015 + LoRA Research PRDs
- [ ] PHASE 7: Self-Assessment Protocol
- [ ] PHASE 8: Documentation + Final Self-Assessment
EOF
```

### Between EVERY phase:
```bash
git add -A && git commit -m "phase N complete: [description]"
cat /tmp/session_61b_checklist.md
sed -i 's/- \[ \] PHASE N/- [x] PHASE N/' /tmp/session_61b_checklist.md
# If context > 50%, run /compact then: cat /tmp/session_61b_context.md | head -60
```

### At session end:
```bash
cat docs/prompts/session_61b_prompt.md
cat /tmp/session_61b_checklist.md
# Fix any unchecked items. Then run PHASE 8 self-assessment.
```

---

## PHASE 0: ORIENT + PUSH + DEPLOY (~5 min)

### 0A: Read Context
```bash
cat CLAUDE.md
cat docs/session_context/session_61b_planning_context.md
head -20 CHANGELOG.md
git log --oneline -10
cat ROADMAP.md
cat BACKLOG.md
```

### 0B: Push and Deploy
```bash
# Save pre-session state for conflict checking
cp ROADMAP.md /tmp/roadmap_pre_61b.md
cp BACKLOG.md /tmp/backlog_pre_61b.md

# Push Session 61 work
git push origin main

# Wait for Railway deploy (check with Railway CLI if available)
# If Railway CLI not available, wait 60 seconds then proceed
```

### 0C: Verify Deploy
```bash
# Check the deployed app is responding
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/
# Should return 200

# Check version matches
curl -s https://rhodesli.nolanandrewfox.com/ | grep -o "v0\.[0-9]*\.[0-9]*" | head -1
# Should show v0.64.0
```

Commit: `chore: session 61B orient — pushed 61, verified deploy`

---

## PHASE 1: RED FLAG VERIFICATION (~15 min)

### 1A: Audit What Actually Changed in Session 61
```bash
echo "=== FILES CHANGED IN SESSION 61 ==="
git diff HEAD~7..HEAD --stat

echo "=== TOTAL LINES CHANGED ==="
git diff HEAD~7..HEAD --shortstat
```

Review: Does the scope of changes match what was claimed?

### 1B: Quick-Identify CSS Crash
```bash
echo "=== QUICK-IDENTIFY CSS ==="
grep -rn "quick.identify\|quickIdentify\|quick_identify" \
  --include="*.py" --include="*.html" --include="*.js" . | head -20

echo "=== LEGACY FACE ID HANDLING ==="
grep -rn "inbox_\|face_id.*format\|css.*selector.*face\|sanitize.*id" \
  --include="*.py" --include="*.js" . | head -20
```

If the CSS crash was NOT fixed in Session 61:
1. Find the crash: CSS selectors that break on `inbox_*` face IDs
2. Fix: sanitize face IDs before using them in CSS selectors
3. Test with both legacy and new ID formats
4. This is a P0 — fix now, don't defer

### 1C: Harness Rules Verification
```bash
echo "=== DUAL-UPDATE RULE ==="
grep -i "dual.update\|update BOTH\|ROADMAP.*BACKLOG" \
  CLAUDE.md .claude/rules/*.md 2>/dev/null

echo "=== DEPLOY RULES ==="
grep -i "Railway\|git push\|deploy\|smoke test" \
  CLAUDE.md .claude/rules/*.md 2>/dev/null

echo "=== SESSION BREADCRUMB RULE ==="
grep -i "breadcrumb\|predecessor\|deferred.*future\|session.*context" \
  CLAUDE.md .claude/rules/*.md 2>/dev/null
```

If any rule is MISSING: add it now. The rules from the 61 planning
context Section 10 must be in the harness. This is non-negotiable.

### 1D: ROADMAP/BACKLOG Integrity
```bash
echo "=== ROADMAP LINE COUNT ==="
wc -l ROADMAP.md  # Must be < 150

echo "=== POST-61 ITEMS IN BACKLOG ==="
grep -i "PRD-015\|Flash.*Pro\|LoRA\|compare_models\|face alignment" BACKLOG.md

echo "=== SESSION 62 CANDIDATES TRACKED? ==="
grep -i "62\|next.*session\|upcoming" ROADMAP.md
```

If post-61 items are NOT in BACKLOG: add them from the planning context.

### 1E: Test Quality Spot-Check
```bash
echo "=== TESTS ADDED IN SESSION 61 ==="
git diff HEAD~7..HEAD --stat -- tests/ | tail -5

echo "=== SAMPLE TEST (check for thin tests) ==="
# Pick a test from the new ones and check it tests real behavior
grep -A 20 "def test_multi_upload\|def test_evidence_card\|def test_mlflow" \
  tests/*.py | head -40
```

If tests are thin (just checking existence, not behavior): note in
assessment but don't rewrite now. Add to BACKLOG as tech debt.

Commit: `fix: session 61B red flag verification — [list what was found/fixed]`

---

## PHASE 2: PRODUCTION SMOKE TEST (~10 min)

### Goal
Non-destructive verification that Session 61 features work in production.
This is the browser/curl testing that 61 may have skipped.

### 2A: Core Pages
```bash
echo "=== CORE PAGE CHECKS ==="
for page in "/" "/compare" "/estimate" "/admin"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://rhodesli.nolanandrewfox.com$page")
  echo "$page: $STATUS"
done
```

### 2B: Multi-Photo Upload Endpoint
```bash
echo "=== MULTI-UPLOAD ENDPOINT ==="
# Check the endpoint exists (don't actually upload — non-destructive)
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "https://rhodesli.nolanandrewfox.com/api/compare/upload-multiple" \
  -F "photos=@/dev/null"
# 400 or 422 = endpoint exists but rejected empty file (GOOD)
# 404 = endpoint doesn't exist (BAD — ACT 2 didn't ship)
# 500 = endpoint crashes (BAD — needs fix)
```

### 2C: Evidence Cards / Detective UX
```bash
echo "=== PHOTO DETECTIVE UX ==="
# Fetch a known photo page, check for evidence display
PHOTO_HTML=$(curl -s "https://rhodesli.nolanandrewfox.com/photo/$(
  curl -s "https://rhodesli.nolanandrewfox.com/" | \
  grep -oP '/photo/[a-f0-9]+' | head -1 | cut -d'/' -f3
)")
echo "$PHOTO_HTML" | grep -c "evidence\|detective\|estimate" || \
  echo "⚠ No evidence display found on photo page"
```

### 2D: MLflow and Compare Script
```bash
echo "=== MLFLOW ==="
python -c "import mlflow; print('✓ MLflow installed')" 2>/dev/null || \
  echo "✗ MLflow not installed"

echo "=== COMPARE SCRIPT ==="
ls scripts/compare_models.py 2>/dev/null && \
  python scripts/compare_models.py --dry-run 2>&1 | head -10 || \
  echo "✗ compare_models.py missing or broken"
```

### 2E: Take Screenshots
Use Claude Chrome (preferred) or Playwright to capture:
1. Homepage
2. Compare page (multi-upload area)
3. A photo page with estimate display
4. Estimate page
5. Admin dashboard

Save screenshots to `docs/session_context/61b_screenshots/`.

### 2F: Log Smoke Test Results
Write results to `docs/session_context/session_61b_smoke_test.md`:
- Each endpoint tested, status code, pass/fail
- Any visual issues from screenshots
- Any errors in server logs

Commit: `test: session 61B production smoke test — [pass/fail summary]`

---

## PHASE 3: UX SCREENSHOT EVALUATION (~10 min)

### Goal
Evaluate screenshots against the app thesis (see context file Section 2).
Log all UX issues. Prioritize. Add to BACKLOG with breadcrumbs.

### 3A: Evaluate Each Screenshot
For each screenshot from Phase 2E, assess:

1. **Does this page serve the app thesis?**
   - Can a community member identify someone from this page?
   - Can they share what they found?
   - Can they contribute knowledge?
   - Is there a clear path to the next action?

2. **Visual quality** — Does it look professional? Mobile-friendly?

3. **Discoverability** — Can a first-time visitor understand what to do?

4. **Sharing** — Is there a share button? Does it produce a good preview?

### 3B: Log UX Findings
Create `docs/session_context/session_61b_ux_evaluation.md`:

```markdown
# Session 61B UX Evaluation
# Date: [today]
# Evaluator: Claude Code
# Screenshots: docs/session_context/61b_screenshots/

## Page: Homepage
- [ ] Issue: [description] | Priority: P1/P2/P3 | Serves: [which thesis goal]
- [ ] Improvement: [description] | Priority: P1/P2/P3

## Page: Compare
...

## Summary
- P1 issues (blocking adoption): N
- P2 issues (degrading experience): N
- P3 issues (nice to have): N
- Quick wins (< 30 min each): [list]
```

### 3C: Add to BACKLOG
Every P1 and P2 issue goes to BACKLOG with:
- ID format: UX-NNN
- Breadcrumb: `Source: Session 61B UX evaluation, screenshot [filename]`
- Priority and estimated effort

Commit: `docs: session 61B UX evaluation — [N] issues logged, [N] P1`

---

## PHASE 4: GEMINI UNIFIED PROMPT ARCHITECTURE (~20 min)

### Goal
Restructure Gemini API calls so one call extracts everything needed,
with configurable presets for different use cases. This saves ~80% on
API costs for bulk analysis.

### 4A: Audit Current Gemini Call Sites
```bash
echo "=== ALL GEMINI CALL SITES ==="
grep -rn "call_gemini\|generate_content\|genai\|gemini.*api" \
  --include="*.py" . | grep -v __pycache__ | grep -v test | grep -v ".git"

echo "=== WHAT EACH CALL EXTRACTS ==="
grep -B5 -A10 "call_gemini\|generate_content" \
  --include="*.py" . | grep -v __pycache__ | head -60
```

Document: How many separate Gemini calls happen per photo today?
What does each one extract? Is there duplication?

### 4B: Create Unified Extraction Config

Create or update `rhodesli_ml/gemini_extraction.py`:

```python
# Configurable extraction presets
# See AD-XXX for decision rationale
EXTRACTION_PRESETS = {
    "full": {  # All extractions — detailed analysis, batch runs
        "date_estimation": True,
        "face_analysis": True,    # needs face coordinates passed in
        "location": True,
        "cultural_markers": True,
        "clothing_era": True,
        "photo_technique": True,
        "text_signage": True,
        "group_composition": True,  # NEW: formal/candid/ceremony
        "photo_condition": True,    # NEW: damage, fading assessment
    },
    "quick": {  # Fast — interactive upload, Flash model
        "date_estimation": True,
        "location": True,
        "text_signage": True,
    },
    "compare": {  # Face compare uploads
        "date_estimation": True,
        "face_analysis": True,
    },
}

def build_extraction_prompt(photo_id, preset="full",
                            include=None, exclude=None,
                            face_coordinates=None,
                            verified_facts=None):
    """
    Build a unified Gemini prompt that extracts all requested info
    in a single API call.

    Args:
        photo_id: Photo to analyze
        preset: One of EXTRACTION_PRESETS keys
        include: List of additional extractions to add
        exclude: List of extractions to remove from preset
        face_coordinates: InsightFace bbox data for face_analysis
        verified_facts: Known facts (confirmed names, dates) for
                       progressive refinement
    Returns:
        Structured prompt string requesting JSON response
    """
    config = EXTRACTION_PRESETS[preset].copy()
    if include:
        for key in include:
            config[key] = True
    if exclude:
        for key in exclude:
            config[key] = False
    # Build prompt sections based on config...
```

### 4C: Structured JSON Output Schema
The prompt should request structured JSON so parsing is reliable:

```json
{
  "date_estimation": {
    "year": 1932,
    "range": 5,
    "confidence": 0.85,
    "evidence": [
      {"category": "clothing", "description": "...", "strength": "strong"},
      {"category": "architecture", "description": "...", "strength": "medium"}
    ]
  },
  "face_analysis": [
    {"face_id": "face_001", "estimated_age": 35, "confidence": 0.7}
  ],
  "location": {
    "place": "Rhodes, Greece",
    "confidence": 0.9,
    "evidence": "..."
  },
  "text_signage": {
    "detected": true,
    "text": "...",
    "language": "Ladino"
  }
}
```

### 4D: Batch API Integration for Bulk Runs
For re-analyzing all 271 photos: use Gemini Batch API (50% discount).
Create `scripts/batch_analyze.py` that:
1. Generates JSONL file with one request per photo
2. Submits to Batch API
3. Polls for completion (up to 24hr)
4. Parses results and logs to MLflow + Supabase
5. Include `--dry-run` that shows cost estimate

### 4E: Write AD for Unified Prompt Architecture
AD-XXX: Gemini Unified Extraction Architecture
- Decision: Single API call per photo with configurable presets
- Rationale: ~80% cost savings, consistent data structure
- Rejected: Separate calls per extraction type (wasteful)
- Rejected: One fixed prompt for all contexts (inflexible)
- Source: Session 61B, Gemini API pricing research

### Tests
- `test_extraction_preset_full_includes_all`
- `test_extraction_preset_quick_is_minimal`
- `test_build_prompt_with_include_exclude`
- `test_build_prompt_includes_verified_facts`
- `test_extraction_response_parses_to_schema`

Commit: `feat(ml): unified Gemini extraction architecture — presets, batch API`

---

## PHASE 5: FLASH VS PRO COMPARISON (~15 min)

### Goal
Run the comparison script created in Session 61 on 20 photos.
This costs ~$0.62 and requires Nolan's pre-approval.

### 5A: Pre-Flight Check
```bash
# Verify script exists and dry-run works
python scripts/compare_models.py --dry-run --photos 20

# Verify Gemini API key is set
python -c "import os; assert os.getenv('GEMINI_API_KEY'), 'No key!'"

# Verify MLflow is ready
python -c "import mlflow; mlflow.set_experiment('test'); print('ready')"
```

### 5B: Run Comparison (REQUIRES NOLAN APPROVAL)
**Check: Was this approved?** Look for approval in:
- Chat messages from Nolan
- A file like `APPROVED_RUNS.md`
- An environment variable `APPROVED_COST_LIMIT`

If NOT approved: skip to 5D. Create the approval request doc.

If approved:
```bash
python scripts/compare_models.py \
  --photos 20 \
  --flash-model gemini-3-flash \
  --pro-model gemini-3.1-pro-preview \
  --output results/flash_vs_pro_20.json
```

### 5C: Analyze Results
After run completes:
- Decade agreement rate (Flash vs Pro)
- Evidence richness comparison
- Cost per photo per model
- Which photos changed estimate with Pro?
- Are there photos where Pro found something Flash missed?

Log all metrics to MLflow. Save comparison report.

### 5D: If Not Approved — Create Approval Request
Create `docs/PENDING_APPROVALS.md`:
```markdown
# Pending Cost Approvals

## Flash vs Pro Comparison (20 photos)
- Estimated cost: ~$0.62
- Purpose: Determine if 3.1 Pro is worth 10x premium over Flash
- Script: scripts/compare_models.py --photos 20
- Approved: [ ] (Nolan must check this)
- Run command: `python scripts/compare_models.py --photos 20`

## Full Library Re-Analysis (271 photos)
- Estimated cost: ~$7.60 (Flash) + ~$11 (Pro unified prompt)
- Purpose: Full re-analysis with unified extraction architecture
- Script: scripts/batch_analyze.py --all
- Approved: [ ] (Nolan must check this)
```

Commit: `feat(ml): Flash vs Pro comparison — [ran/deferred pending approval]`

---

## PHASE 6: PRD-015 FACE ALIGNMENT + LORA RESEARCH (~15 min)

### 6A: PRD-015 Face Alignment

Create `docs/prds/015_gemini_face_alignment_v2.md` (or update existing):

**Problem**: InsightFace detects faces and gives bounding boxes. Gemini
analyzes the photo and can reason about who is who. But there's no
bridge between them — Gemini doesn't know which InsightFace bbox
corresponds to which person it identifies.

**Solution**: Pass InsightFace bounding box coordinates to Gemini in the
unified prompt. Gemini responds with its identification mapped to
specific coordinate regions. This bridges ML face detection with VLM
reasoning.

**Why 3.1 Pro**: This requires spatial reasoning (mapping descriptions
to coordinates) which is 3.1 Pro's strength — 2x+ improvement in
bounding box tasks over 3 Pro.

**Success Criteria**:
1. Gemini receives face coordinates as part of prompt
2. Gemini's response maps each identified person to a bbox region
3. Mismatches (Gemini sees 5 faces, InsightFace detects 4) are flagged
4. Vida Capeluto count mismatch is resolved
5. Results feed back into the identity confirmation workflow

**Architecture**: This is an extension of the unified extraction prompt
(Phase 4). The `face_analysis` extraction type uses InsightFace
coordinates as input and Gemini's identification as output.

### 6B: LoRA Similarity Calibration Research

Create `docs/prds/023_lora_similarity_calibration.md`:

**Problem**: InsightFace's default face embeddings are trained on
modern, diverse faces. Historical photos from 1900-1940 Rhodes have
different characteristics: sepia tones, formal poses, limited lighting,
period-specific grooming/clothing. The embedding space may not
optimally separate individuals from this era.

**Research Questions** (answer before implementation):
1. Does InsightFace's model support LoRA fine-tuning? (ArcFace backbone)
2. How many labeled face pairs do we need? (literature: 50-200 pairs min)
3. Do we have enough confirmed identities for training data?
4. What's the expected improvement? (literature: 5-15% for domain shift)
5. Is there a simpler calibration approach first? (threshold tuning,
   score normalization, Platt scaling)

**ML Plan Position**: date estimation (done) → similarity calibration
(this PRD) → LoRA (if calibration isn't sufficient)

**Decision**: Start with Platt scaling / isotonic regression on the
existing similarity scores using confirmed match/non-match pairs as
ground truth. Only pursue LoRA if simpler calibration is insufficient.

### 6C: Write ADs
- AD-XXX: Face alignment via coordinate bridging (PRD-015 v2)
- AD-XXX: Similarity calibration strategy — Platt scaling first, LoRA later

Commit: `docs: PRD-015 face alignment v2, PRD-023 LoRA/calibration, ADs`

---

## PHASE 7: SELF-ASSESSMENT PROTOCOL (~10 min)

### Goal
Install the self-assessment pattern into the Rhodesli harness so that
future sessions automatically verify their own work.

### 7A: Create Self-Assessment Rule
Create `.claude/rules/self-assessment.md`:

```markdown
# Self-Assessment Protocol (Mandatory)

Every session MUST end with a self-assessment phase. This cannot be
skipped, even if context is running low.

## At Session End
1. Re-read the ORIGINAL prompt from docs/prompts/session_NN_prompt.md
2. For each phase/act in the prompt:
   a. Verify it was completed (grep for expected artifacts)
   b. Verify it was tested (check for curl/browser evidence)
   c. Note any silent deferrals
3. Run the verification gate from the prompt
4. Write docs/session_context/session_NN_assessment.md:
   - What shipped (with evidence)
   - What was deferred (with reason and BACKLOG entry)
   - Red flags (with severity and recommended fix)
   - What the NEXT session should verify FIRST
5. If any red flag is fixable in < 5 min: fix it now
6. If any red flag needs BACKLOG entry: create it with breadcrumb

## Assessment Template
```
# Session NN Assessment
## Shipped
- [x] Phase 0: [description] — Evidence: [file/test/curl result]
## Deferred
- Phase X: [description] — Reason: [why] — BACKLOG: [ID]
## Red Flags
- [severity] [description] — Fix: [what to do]
## Next Session Should Verify
1. [highest priority verification]
```

## UX Feedback Collection
If screenshots were taken during the session:
1. Evaluate each screenshot against the app thesis goals
2. Log issues in docs/session_context/session_NN_ux_evaluation.md
3. P1/P2 issues → BACKLOG with breadcrumb
4. Quick wins → note for next session
```

### 7B: Create UX Evaluation Rule
Create `.claude/rules/ux-evaluation.md`:

```markdown
# UX Evaluation Protocol

When taking screenshots or evaluating UI during a session, assess
each page against the Rhodesli app thesis:

## Core Questions (from Nolan)
1. Can a community member identify someone from this page?
2. Can they share what they found? (share button, OG tags, link)
3. Can they contribute knowledge? (CTA, form, response mechanism)
4. Is there a clear path to the next action?
5. Does the growth loop work? (Find → Share → Click → Recognize → Respond)

## Logging
- All UX findings go to docs/session_context/session_NN_ux_evaluation.md
- P1/P2 issues get BACKLOG entries with source breadcrumb
- Quick wins (< 30 min) are noted separately for easy pickup

## This evaluation feeds:
- BACKLOG.md (new items with UX-NNN IDs)
- ROADMAP.md (if P1 items affect session planning)
- Future session prompts (verification items)
```

### 7C: Add Hooks Reference to CLAUDE.md
Add to CLAUDE.md (if not already present):
```
## Session Protocol
- Every session ends with self-assessment: see .claude/rules/self-assessment.md
- UX feedback collected per session: see .claude/rules/ux-evaluation.md
- ROADMAP + BACKLOG must both be updated: see .claude/rules/dual-update.md
- Deploy via git push, verify with curl: see .claude/rules/deployment.md
```

Commit: `feat(harness): self-assessment protocol, UX evaluation rule, session hooks`

---

## PHASE 8: DOCUMENTATION + FINAL SELF-ASSESSMENT (~10 min)

### 8A: Update ALGORITHMIC_DECISIONS.md
Add new ADs from this session (with full provenance):
- Unified Gemini extraction architecture (Phase 4)
- Face alignment coordinate bridging (Phase 6)
- Similarity calibration strategy (Phase 6)
- Self-assessment protocol decision (Phase 7)

### 8B: Update ROADMAP.md + BACKLOG.md (WITH CONFLICT CHECK)
```bash
cp ROADMAP.md /tmp/roadmap_after_61b.md
# Make updates...
# Then verify:
diff /tmp/roadmap_pre_61b.md ROADMAP.md
grep "^\- \[" /tmp/roadmap_pre_61b.md | while read line; do
  grep -qF "$line" ROADMAP.md || echo "MISSING: $line"
done
wc -l ROADMAP.md  # Must be < 150
```

### 8C: Save Session Outcomes
Create `docs/session_context/session_61b_outcomes.md`:
- What shipped
- Red flags found and fixed
- Red flags found and deferred
- Smoke test results
- UX evaluation summary
- Flash vs Pro results (if run)
- PRDs created
- What Session 62 should do first

### 8D: Update SESSION_HISTORY.md

### 8E: SELF-ASSESSMENT (MANDATORY — THIS IS THE FIRST USE)

**This is the inaugural run of the self-assessment protocol from Phase 7.
Execute it fully as a proof-of-concept.**

```bash
echo "=== SESSION 61B SELF-ASSESSMENT ==="

# Re-read original prompt
cat docs/prompts/session_61b_prompt.md | head -20

# Phase 0: Deploy
echo "--- Phase 0: Deploy ---"
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/
# 200 = deployed

# Phase 1: Red flags
echo "--- Phase 1: Red Flags ---"
grep -q "dual.update\|update BOTH" CLAUDE.md .claude/rules/*.md 2>/dev/null && \
  echo "✓ Harness rules" || echo "✗ MISSING harness rules"

# Phase 2: Smoke test
echo "--- Phase 2: Smoke Test ---"
ls docs/session_context/session_61b_smoke_test.md && \
  echo "✓ Smoke test logged" || echo "✗ MISSING smoke test log"

# Phase 3: UX eval
echo "--- Phase 3: UX Evaluation ---"
ls docs/session_context/session_61b_ux_evaluation.md && \
  echo "✓ UX evaluation" || echo "✗ MISSING UX evaluation"

# Phase 4: Unified extraction
echo "--- Phase 4: Gemini Extraction ---"
grep -q "EXTRACTION_PRESETS\|extraction.*preset" rhodesli_ml/*.py 2>/dev/null && \
  echo "✓ Extraction presets" || echo "✗ MISSING extraction presets"

# Phase 5: Flash vs Pro
echo "--- Phase 5: Flash vs Pro ---"
ls results/flash_vs_pro*.json 2>/dev/null && \
  echo "✓ Comparison run" || echo "⚠ Comparison deferred (needs approval)"

# Phase 6: PRDs
echo "--- Phase 6: PRDs ---"
ls docs/prds/015_gemini_face_alignment*.md && echo "✓ PRD-015" || echo "✗ MISSING PRD-015"
ls docs/prds/023_lora*.md && echo "✓ PRD-023" || echo "✗ MISSING PRD-023"

# Phase 7: Self-assessment rule
echo "--- Phase 7: Self-Assessment ---"
ls .claude/rules/self-assessment.md && echo "✓ Rule exists" || echo "✗ MISSING rule"

# Phase 8: Docs
echo "--- Phase 8: Docs ---"
ls docs/session_context/session_61b_outcomes.md && \
  echo "✓ Outcomes" || echo "✗ MISSING outcomes"
wc -l ROADMAP.md | awk '{print ($1<=150) ? "✓ ROADMAP ok ("$1")" : "✗ ROADMAP too long ("$1")"}'

# Tests
echo "--- Tests ---"
pytest tests/ -x -q --tb=short 2>&1 | tail -5

echo "=== WRITE ASSESSMENT ==="
# Write docs/session_context/session_61b_assessment.md
# following the template from .claude/rules/self-assessment.md
```

**Fix any failures before declaring session complete.**

Commit: `docs: session 61B complete — assessment, outcomes, ADs, PRDs`
`git push`

---

## SESSION RULES

- Deploy via git push → Railway auto-deploys (NOT Railway dashboard)
- Browser testing: Claude Chrome preferred, Playwright if unavailable
- Test uploads with real files via curl, not mocks
- DO NOT run Gemini API calls without --dry-run unless cost-approved
- DO NOT modify confirmed identity data
- Commit after every phase with descriptive messages
- Update BOTH ROADMAP.md AND BACKLOG.md when completing items
- Before editing ROADMAP/BACKLOG: save current versions to /tmp for diff
- After editing ROADMAP/BACKLOG: verify no items were lost via diff
- Every AD: decision, rejected alternatives, source session, rationale
- Keep docs under 300 lines each, ROADMAP under 150 lines
- If context > 50%: /compact then re-read context file
- Session context file must link to predecessor and list deferred work
- Update ALGORITHMIC_DECISIONS.md after EVERY algorithmic decision
- End session with self-assessment (Phase 8E) — MANDATORY
- UX screenshots evaluated against app thesis goals
- All UX issues logged with priority and BACKLOG entry for P1/P2
