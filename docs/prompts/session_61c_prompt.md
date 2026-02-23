# Session 61C: GEDCOM-Enriched Analysis + Flash vs Pro

Read CLAUDE.md. Read all .claude/rules/*.md files.
Read docs/session_context/session_61c_planning_context.md.
Read CHANGELOG.md (first 10 lines). Read ROADMAP.md. Read BACKLOG.md.
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines).
Read docs/session_context/session_61b_assessment.md.

## SESSION IDENTITY
- **Session**: 61C
- **Predecessor**: 61B (verify/optimize, shipped unified extraction + self-assessment)
- **Lineage**: 60 → 60B → 61 → 61B → 61C (this session)
- **Goal**: Build GEDCOM context extractor, run 2×5 comparison matrix
  (Flash/Pro × 5 GEDCOM variants), store GEDCOM data in Supabase,
  verify roadmap integrity, close 61B loose ends
- **Budget**: $10 approved for ALL Gemini API calls — no further approval needed
- **Parallel**: Designed to run simultaneously with Session 62 via worktree
- **Estimated time**: 70-90 minutes
- **Context file**: `docs/session_context/session_61c_planning_context.md`
- **Post-61C**: Session 62 = PRD-015 face alignment (can start in parallel)
- **Deferred to 63**: Platt scaling (AD-145), UX-130

---

## ⚠️ CRITICAL: WORKTREE SETUP FOR PARALLEL OPERATION

This session MUST use a git worktree if Session 62 is running concurrently.
If Session 62 is NOT running, skip worktree and work on main.

```bash
# Check if another session is active
git branch | grep "session-62" && \
  echo "⚠ Session 62 active — USE WORKTREE" || \
  echo "✓ No conflict — can work on main"

# If worktree needed:
git checkout -b session-61c 2>/dev/null || git checkout session-61c
git worktree add .claude/worktrees/session-61c session-61c 2>/dev/null
cd .claude/worktrees/session-61c
echo "Working in worktree: $(pwd)"

# If no worktree needed: work on main as normal
```

### File Ownership (if parallel with Session 62)
- 61C OWNS: rhodesli_ml/*, scripts/*, results/, tests/test_ml_*
- 61C APPENDS ONLY: ROADMAP.md, BACKLOG.md, ALGORITHMIC_DECISIONS.md
- 61C CREATES: docs/session_context/session_61c_*
- DO NOT TOUCH: app/*, app/templates/* (Session 62 owns these)

---

## ⚠️ CONTEXT MANAGEMENT — MANDATORY

### Before ANYTHING else:
```bash
cp docs/session_context/session_61c_planning_context.md /tmp/session_61c_context.md
cat > /tmp/session_61c_checklist.md << 'EOF'
# Session 61C Phase Checklist
# Lineage: 60 → 60B → 61 → 61B → 61C
- [ ] PHASE 0: Orient + Verify 61B Loose Ends
- [ ] PHASE 1: Roadmap Integrity Audit
- [ ] PHASE 2: GEDCOM Parse + Database Storage
- [ ] PHASE 3: GEDCOM Context Builder (5 variants)
- [ ] PHASE 4: Flash vs Pro Baseline (Variant A, no GEDCOM)
- [ ] PHASE 5: GEDCOM-Enriched Runs (Variants B-E)
- [ ] PHASE 6: Meta-Comparison + Analysis Report
- [ ] PHASE 7: Documentation + Self-Assessment
EOF
```

### Between EVERY phase:
```bash
git add -A && git commit -m "61c phase N: [description]"
sed -i 's/- \[ \] PHASE N/- [x] PHASE N/' /tmp/session_61c_checklist.md
cat /tmp/session_61c_checklist.md
# If context > 50%: /compact then re-read:
# cat /tmp/session_61c_context.md | head -80
```

### At session end:
```bash
cat docs/prompts/session_61c_prompt.md | head -20
cat /tmp/session_61c_checklist.md
# Fix any unchecked items. Then run PHASE 7 self-assessment.
```

---

## PHASE 0: ORIENT + VERIFY 61B LOOSE ENDS (~8 min)

### 0A: Read State
```bash
cat CLAUDE.md
cat docs/session_context/session_61c_planning_context.md
cat docs/session_context/session_61b_assessment.md
head -20 CHANGELOG.md
git log --oneline -15
cat ROADMAP.md
cat BACKLOG.md
```

### 0B: Verify 61B Loose Ends (from assessment "Next Session Should Verify")
```bash
echo "=== 1. ENOSPC FIX PERSISTS ==="
df -h . | tail -1
# If Railway CLI available: railway logs --tail 20
git log --oneline -3

echo "=== 2. QUICK-IDENTIFY CSS ==="
grep -rn "sanitize\|escape.*id\|css.*safe\|face.*id.*format" \
  --include="*.py" --include="*.js" app/ | head -10
# Test: curl the identify page with a legacy face ID
curl -s "https://rhodesli.nolanandrewfox.com/identify" | head -5

echo "=== 3. UX ITEMS IN BACKLOG ==="
for item in UX-130 UX-131 UX-132; do
  grep -q "$item" BACKLOG.md && echo "✓ $item tracked" || echo "✗ $item MISSING"
done

echo "=== 4. HD-015 DUPLICATE ==="
grep -c "HD-015" docs/HARNESS_DECISIONS.md 2>/dev/null
# If count > 1: renumber the duplicate

echo "=== 5. GEMINI API KEY ==="
python3 -c "
import os
key = os.getenv('GEMINI_API_KEY', '')
print(f'Key present: {bool(key)}, length: {len(key)}')
"

echo "=== 6. UNIFIED EXTRACTION MODULE ==="
python3 -c "
from rhodesli_ml.gemini_extraction import EXTRACTION_PRESETS, build_extraction_prompt
print(f'Presets: {list(EXTRACTION_PRESETS.keys())}')
print('✓ Module works')
" 2>/dev/null || echo "✗ Import failed"

echo "=== 7. SELF-ASSESSMENT RULE EXISTS ==="
ls .claude/rules/self-assessment.md && echo "✓" || echo "✗ MISSING"
ls .claude/rules/ux-evaluation.md && echo "✓" || echo "✗ MISSING"

echo "=== 8. DEFERRED ITEMS TRACKED ==="
grep -q "Platt scaling\|AD-145\|similarity calibration" BACKLOG.md && \
  echo "✓ Platt scaling in BACKLOG" || \
  echo "✗ Platt scaling NOT in BACKLOG — add it now"
```

Fix anything that fails. If Platt scaling / AD-145 Stage 1 isn't in
BACKLOG, add it: `Platt scaling similarity calibration (AD-145 Stage 1)
— deferred from 61C, depends on Flash vs Pro results. Source: 61B assessment.`

Commit: `chore: 61C orient — verified 61B loose ends, [N] fixes`

---

## PHASE 1: ROADMAP INTEGRITY AUDIT (~5 min)

### Goal
Verify nothing was lost when 61B trimmed ROADMAP from 210→85 lines.

### USE A SUBAGENT (read-only, parallel-safe):
```
Spawn an Explore subagent:
"Compare ROADMAP.md at HEAD vs HEAD~12 (pre-61B state).
 For every item REMOVED in the trim, check if it:
 (a) exists in BACKLOG.md (completed or moved)
 (b) exists in SESSION_HISTORY.md (shipped)
 (c) was deprecated with an explicit note
 List any items removed WITHOUT being tracked elsewhere.
 Write findings to /tmp/roadmap_audit.md"
```

### After Subagent Returns:
```bash
cat /tmp/roadmap_audit.md
# If items were lost: restore to BACKLOG with note
# "recovered from ROADMAP trim in Session 61B"
```

Commit: `audit: 61C roadmap integrity — [N] items verified, [N] recovered`

---

## PHASE 2: GEDCOM PARSE + DATABASE STORAGE (~12 min)

### Goal
Parse the GEDCOM file once, store in Supabase tables for fast lookup.
This data persists — no need to re-parse the GEDCOM file again.

### 2A: Locate and Analyze GEDCOM
```bash
echo "=== FIND GEDCOM ==="
find ~/Downloads -name "*.ged" -maxdepth 2 2>/dev/null
# Also check repo for any previously copied GEDCOM
find . -name "*.ged" -maxdepth 3 2>/dev/null

echo "=== GEDCOM STATS ==="
GEDCOM_PATH="$(find ~/Downloads -name '*.ged' -maxdepth 2 | head -1)"
python3 << EOF
with open("$GEDCOM_PATH", "r", errors="replace") as f:
    content = f.read()
lines = content.splitlines()
print(f"Total lines: {len(lines)}")
for tag in ["@ INDI", "@ FAM", "BIRT", "DEAT", "MARR", "RESI", "IMMI", "EMIG", "OCCU"]:
    clean = tag.replace("@ ", "@")
    count = sum(1 for l in lines if clean in l)
    print(f"{tag.strip()}: {count}")
EOF
```

### 2B: Create Supabase Tables
```python
# Create the 4 GEDCOM tables in Supabase
# Schema from planning context Section 3
# gedcom_individuals, gedcom_events, gedcom_face_links, gedcom_relationships
```

### 2C: Create GEDCOM Parser + Import Script
Create `scripts/import_gedcom.py`:
- Parse GEDCOM file into structured records
- Populate gedcom_individuals with all people
- Populate gedcom_events with all events per person
- Populate gedcom_relationships by parsing FAM records
- Report: N individuals, N events, N relationships imported
- Idempotent: can re-run safely (upsert on gedcom_id)

### 2D: Run Import
```bash
python3 scripts/import_gedcom.py --file "$GEDCOM_PATH" --verbose
# Verify:
python3 -c "
# Query Supabase to confirm data loaded
# Print: N individuals, N events, N relationships
"
```

### 2E: Create Name Matching + Linking
Create `rhodesli_ml/gedcom_context.py` with:
- `match_person_to_gedcom(name, supabase)` — fuzzy match Rhodesli
  person name to GEDCOM individual. Return best match + confidence.
- `auto_link_faces(supabase)` — batch link all identified Rhodesli
  faces to GEDCOM individuals. Save to gedcom_face_links table.
- Log matches and non-matches for admin review.

### Tests (use subagent for parallel test writing):
- `test_parse_gedcom_basic_structure`
- `test_import_idempotent`
- `test_fuzzy_name_matching_exact`
- `test_fuzzy_name_matching_variations` (e.g., "Leon" vs "Big Leon")
- `test_relationship_extraction`

Commit: `feat(ml): GEDCOM parse + Supabase storage + name linking — AD-XXX`

---

## PHASE 3: GEDCOM CONTEXT BUILDER (5 Variants) (~10 min)

### Goal
Build the module that extracts per-photo context at each of the 5
enrichment levels, for injection into Gemini prompts.

### 3A: Context Extraction Functions
Add to `rhodesli_ml/gedcom_context.py`:

```python
def build_photo_context(photo_id, identified_faces, supabase,
                        variant="curated", photo_date_estimate=None):
    """
    Build GEDCOM context for all identified people in a photo.

    Variants:
      "none"     → empty string (baseline)
      "full"     → all events for identified people
      "curated"  → events within ±15yr of photo_date_estimate
      "first_order" → full + all events for immediate family
      "co_occurrence" → first_order + events for anyone sharing
                        ANY photo with identified people

    Returns: context string for Gemini prompt injection
    """

def _get_person_events(individual_id, supabase, curated=False,
                       photo_date=None):
    """Get events for one person, optionally filtered by date."""

def _get_first_order_connections(individual_id, supabase):
    """Get parents, siblings, spouse, children from relationships table."""

def _get_photo_co_occurrences(face_id, supabase):
    """Get all people who appear in ANY photo with this face.
    Returns list of (person_name, gedcom_individual_id) pairs."""

def get_enrichment_delta(baseline_result, enriched_result):
    """Compare baseline vs enriched Gemini results.
    Returns dict of what changed and by how much."""
```

### 3B: Integration with Unified Extraction
Update `rhodesli_ml/gemini_extraction.py`:
- `build_extraction_prompt()` now accepts `gedcom_context=None` parameter
- If provided, adds: `"GENEALOGICAL CONTEXT FOR IDENTIFIED INDIVIDUALS:\n{context}"`
- This is a clean extension — no changes to existing behavior when
  gedcom_context is not provided

### 3C: Token Counter
```python
def estimate_context_tokens(context_string):
    """Rough token count for GEDCOM context.
    ~4 chars per token for English text."""
    return len(context_string) // 4
```

Log token counts for EVERY context variant to track Variant D and E
growth. If any single photo's context exceeds 15,000 tokens, log a
warning but still run — we want to see the quality impact.

### Tests:
- `test_build_context_none_returns_empty`
- `test_build_context_full_includes_all_events`
- `test_build_context_curated_filters_by_date`
- `test_build_context_first_order_includes_family`
- `test_build_context_co_occurrence_includes_shared_photos`
- `test_token_estimation`
- `test_extraction_prompt_includes_gedcom_context`

Commit: `feat(ml): GEDCOM context builder — 5 variants + extraction integration`

---

## PHASE 4: FLASH VS PRO BASELINE (No GEDCOM) (~10 min)

### Goal
Run 20-photo comparison with NO GEDCOM context.
This is Runs A1 (Flash) and A2 (Pro) — the baseline.

### 4A: Select 20 Photos
```python
"""
Select photos that maximize learning signal:
- 5 with confirmed IDs linked to GEDCOM (GEDCOM-enrichable)
- 5 with confirmed IDs but NO GEDCOM link (ID control)
- 5 with high-match unconfirmed IDs (partial enrichment)
- 5 with NO identified faces (pure visual baseline)

Save to results/comparison_photo_set.json with metadata:
{photo_id, has_gedcom_link, has_confirmed_id, face_count, collections}
"""
```

### 4B: Run Baseline
```bash
# A1: Flash, no GEDCOM
python3 scripts/compare_models.py \
  --photos results/comparison_photo_set.json \
  --model gemini-3-flash \
  --preset full \
  --gedcom-variant none \
  --output results/run_A1_flash_none.json \
  --mlflow-run A1-flash-none

# A2: Pro, no GEDCOM
python3 scripts/compare_models.py \
  --photos results/comparison_photo_set.json \
  --model gemini-3.1-pro-preview \
  --preset full \
  --gedcom-variant none \
  --output results/run_A2_pro_none.json \
  --mlflow-run A2-pro-none
```

### 4C: Cost Check
```bash
python3 << 'EOF'
import json
total = 0
for f in ["results/run_A1_flash_none.json", "results/run_A2_pro_none.json"]:
    try:
        with open(f) as fh:
            data = json.load(fh)
        cost = sum(r.get("cost", 0) for r in data.get("results", []))
        total += cost
        print(f"{f}: ${cost:.4f}")
    except: pass
print(f"Baseline total: ${total:.4f}")
if total > 3:
    print("⚠ Baseline unexpectedly expensive — reassess before GEDCOM runs")
EOF
```

Commit: `feat(ml): Flash vs Pro baseline (no GEDCOM) — 20 photos`

---

## PHASE 5: GEDCOM-ENRICHED RUNS (Variants B-E) (~15 min)

### Goal
Run all 8 remaining comparison cells: B1/B2, C1/C2, D1/D2, E1/E2.
Track token usage, cost, and wall-clock time per call.

### 5A: Generate GEDCOM Contexts for All Photos
```python
"""
For each of the 20 photos, generate context at each variant level.
Save to results/gedcom_contexts.json:
{
  photo_id: {
    "none": "",
    "full": "...",
    "curated": "...",
    "first_order": "...",
    "co_occurrence": "..."
  }
}

Also log token counts per variant per photo.
"""
```

### 5B: Run All 8 Cells
```bash
for VARIANT in full curated first_order co_occurrence; do
  for MODEL_TAG in "gemini-3-flash:flash" "gemini-3.1-pro-preview:pro"; do
    MODEL=$(echo $MODEL_TAG | cut -d: -f1)
    TAG=$(echo $MODEL_TAG | cut -d: -f2)
    LETTER=$(echo $VARIANT | head -c1 | tr 'fcao' 'BCDE')
    NUM=$([ "$TAG" = "flash" ] && echo "1" || echo "2")
    RUN_ID="${LETTER}${NUM}"

    echo "=== Run $RUN_ID: $TAG + $VARIANT ==="
    python3 scripts/compare_models.py \
      --photos results/comparison_photo_set.json \
      --model "$MODEL" \
      --preset full \
      --gedcom-variant "$VARIANT" \
      --gedcom-contexts results/gedcom_contexts.json \
      --output "results/run_${RUN_ID}_${TAG}_${VARIANT}.json" \
      --mlflow-run "${RUN_ID}-${TAG}-${VARIANT}" \
      --track-tokens \
      --track-latency
  done
done
```

### 5C: Running Cost Tally
```bash
python3 << 'EOF'
import json, glob
total = 0
for f in sorted(glob.glob("results/run_*.json")):
    with open(f) as fh:
        data = json.load(fh)
    cost = sum(r.get("cost", 0) for r in data.get("results", []))
    tokens = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0)
                 for r in data.get("results", []))
    total += cost
    print(f"{f}: ${cost:.4f} ({tokens:,} tokens)")
print(f"\nCUMULATIVE: ${total:.4f} / $10.00")
if total > 8:
    print("⚠ APPROACHING BUDGET — skip meta-comparison if needed")
EOF
```

### 5D: Token Analysis for Variants D and E
```python
"""
CRITICAL: Analyze whether Variant D/E contexts are too large.
For each photo, compare:
- Variant B token count vs Variant D token count
- Variant D token count vs Variant E token count
- Did quality improve proportionally to token increase?
- Were there photos where D/E HURT quality (noise > signal)?
"""
```

Commit: `feat(ml): GEDCOM-enriched runs — variants B-E × Flash + Pro`

---

## PHASE 6: META-COMPARISON + ANALYSIS REPORT (~10 min)

### 6A: Quantitative Analysis
```python
"""
Compare all 10 runs across:
- Date accuracy: decade agreement with known dates
- Location accuracy: correct city/country identification
- Evidence richness: number of evidence categories with findings
- Novel insights: things discovered ONLY with GEDCOM context
- Cost per photo per model per variant
- Token usage per variant
- Latency per variant
- Quality-per-token: which variant gives best improvement per token spent

Save to results/comparison_analysis.json
"""
```

### 6B: Meta-Comparison (Ask Gemini to Judge)
**Only if cumulative spend < $8:**

For the 5 GEDCOM-linked photos, send all 5 variant results to Pro:
```
"Here are five analyses of the same photo, each with different
amounts of genealogical context:
A (visual only): {result}
B (person's full record): {result}
C (curated events only): {result}
D (person + immediate family): {result}
E (person + family + photo co-occurrences): {result}

Compare these analyses:
1. Which is most accurate and complete?
2. What did the genealogical context add?
3. Was full context or curated better?
4. Did first-order connections help?
5. Did photo co-occurrence help or add noise?
6. Were there cases where extra context was misleading?"
```

### 6C: Write Comparison Report
Create `results/gedcom_enrichment_comparison_report.md`:
- Executive summary: which model × variant combination wins
- Verdict: Is GEDCOM enrichment worth it? Which level?
- Token analysis: D and E growth patterns
- Cost analysis: marginal cost of each enrichment level
- Per-photo breakdowns for the 5 GEDCOM-linked photos
- Recommendations for default production settings
- Implications for the engagement virtuous cycle feature
- What changed from Albert Fox-style insights?

### 6D: Write ADs
- AD-XXX: GEDCOM-Enriched Analysis — Comparison Results
  - What we tested, results, decision, rejected alternatives
  - Source: Session 61C + Nolan's Albert Fox / Big Leon examples
- AD-XXX: GEDCOM Storage Architecture
  - Decision: Supabase tables, parse once, query fast
  - Source: Session 61C

Commit: `analysis: GEDCOM enrichment comparison — 2×5 matrix report + ADs`

---

## PHASE 7: DOCUMENTATION + SELF-ASSESSMENT (~8 min)

### 7A: Update BACKLOG.md (append-only)
New items from this session:
- GEDCOM enrichment in upload flow (high-match popup)
- "Analysis improved because..." UX feature
- Batch re-analysis with GEDCOM enrichment
- Admin GEDCOM link review UI
- Platt scaling (AD-145 Stage 1) — if not already there

### 7B: Update ROADMAP.md (with conflict check)
```bash
cp ROADMAP.md /tmp/roadmap_pre_61c.md
# Make updates — append only, do not rewrite
# Then verify:
diff /tmp/roadmap_pre_61c.md ROADMAP.md
wc -l ROADMAP.md  # Must stay < 150
```

### 7C: Session Outcomes
Create `docs/session_context/session_61c_outcomes.md`:
- Total API cost spent (vs $10 budget)
- GEDCOM enrichment verdict (which variant wins)
- Token/cost/latency breakdown per variant
- Supabase tables created
- Items added to BACKLOG
- What Session 63 should do (Platt scaling? Implement winning variant?)
- What Session 62 covers (PRD-015, running in parallel)

### 7D: CHANGELOG + SESSION_HISTORY

### 7E: SELF-ASSESSMENT (mandatory per .claude/rules/self-assessment.md)
```bash
echo "=== SESSION 61C SELF-ASSESSMENT ==="
cat docs/prompts/session_61c_prompt.md | head -20

echo "--- Phase 0: Loose Ends ---"
for item in UX-130 UX-131 UX-132; do
  grep -q "$item" BACKLOG.md && echo "✓ $item" || echo "✗ $item"
done

echo "--- Phase 1: Roadmap Audit ---"
ls /tmp/roadmap_audit.md 2>/dev/null && echo "✓ Ran" || echo "✗ Missing"

echo "--- Phase 2: GEDCOM Storage ---"
python3 -c "
# Check Supabase tables exist and have data
# Print row counts for each table
" 2>/dev/null || echo "✗ DB check failed"

echo "--- Phase 3: Context Builder ---"
python3 -c "
from rhodesli_ml.gedcom_context import build_photo_context
print('✓ Module imports')
" 2>/dev/null || echo "✗ Module broken"

echo "--- Phases 4-5: Comparison Runs ---"
RUN_COUNT=$(ls results/run_*.json 2>/dev/null | wc -l)
echo "Runs completed: $RUN_COUNT / 10 expected"

echo "--- Phase 6: Analysis ---"
ls results/*comparison_report* 2>/dev/null && \
  echo "✓ Report exists" || echo "✗ No report"

echo "--- Budget ---"
python3 << 'BUDGET'
import json, glob
total = sum(
    sum(r.get("cost", 0) for r in json.load(open(f)).get("results", []))
    for f in glob.glob("results/run_*.json")
)
print(f"Spent: ${total:.2f} / $10.00")
print("✓ Within budget" if total <= 10 else "✗ OVER BUDGET")
BUDGET

echo "--- Tests ---"
pytest tests/test_ml_* -x -q --tb=short 2>&1 | tail -3

echo "--- ROADMAP ---"
wc -l ROADMAP.md | awk '{
  print ($1<=150) ? "✓ ROADMAP ok ("$1")" : "✗ ROADMAP too long ("$1")"
}'

echo "=== WRITE ASSESSMENT ==="
# Create docs/session_context/session_61c_assessment.md
# Template from .claude/rules/self-assessment.md
```

**Fix any failures before declaring session complete.**

### 7F: Merge (if in worktree)
```bash
# If in worktree:
cd /path/to/main/repo
git merge session-61c --no-ff -m "merge: session 61C — GEDCOM enrichment + Flash vs Pro comparison"
git worktree remove .claude/worktrees/session-61c
git branch -d session-61c

# If on main: just push
git push origin main
```

---

## SESSION RULES

- **Budget: $10 total approved** — no need to ask for more until $10 accrues
- Track cumulative spend after EVERY Gemini API call
- If spend > $8: skip meta-comparison (Phase 6B), go to Phase 7
- Deploy via git push (NOT Railway dashboard)
- Commit after every phase with descriptive message
- Update BOTH ROADMAP and BACKLOG when completing/deferring items
- Before editing ROADMAP/BACKLOG: save to /tmp for diff
- After editing: verify nothing lost, ROADMAP stays < 150 lines
- DO NOT filter out any GEDCOM data for privacy — include all records
  regardless of birth date or living status. We can adjust later.
- GEDCOM file location: ~/Downloads/*.ged
- Store all parsed GEDCOM data in Supabase (parse once, query fast)
- Log token counts, cost, and latency for EVERY Gemini API call
- Use subagents for parallelizable work (roadmap audit, test writing)
- If in worktree: append-only to shared docs, never rewrite
- End with self-assessment (Phase 7E) — MANDATORY
- All algorithmic decisions → ALGORITHMIC_DECISIONS.md with provenance
- Deferred items tracked in BACKLOG with breadcrumbs
- This session is designed for autonomous operation
- Nolan explicitly stated: "I want to set this and go plow my driveway"
