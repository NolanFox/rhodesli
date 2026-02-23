# Session 63: Close the Gaps, Calibrate, Re-Run

Read CLAUDE.md. Read all .claude/rules/*.md files.
Read docs/session_context/session_63_planning_context.md.
Read CHANGELOG.md (first 10 lines). Read ROADMAP.md. Read BACKLOG.md.
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines).
Read docs/session_context/session_61c_assessment.md.
Read docs/session_context/session_62_assessment.md.

## SESSION IDENTITY
- **Session**: 63
- **Predecessors**: 61C (GEDCOM + Flash vs Pro) + 62 (face alignment)
- **Lineage**: 61B → 61C + 62 (parallel) → 63 (this session)
- **Goal**: Fix unresolved gaps from 61C/62, deploy and verify with
  real photos, build calibration system, batch re-run 271 photos
- **Budget**: $7.54 remaining from 61C ($10 - $2.46) + Nolan pre-approves
  up to $5 additional for batch re-run = $12.54 max
- **Estimated time**: 90-110 minutes (10 phases × ~10 min each)
- **Context file**: `docs/session_context/session_63_planning_context.md`

---

## ⚠️ CONTEXT MANAGEMENT — MANDATORY — READ THIS FIRST

### Before ANYTHING else:
```bash
cp docs/session_context/session_63_planning_context.md /tmp/session_63_context.md
cp docs/prompts/session_63_prompt.md /tmp/session_63_prompt.md
cat > /tmp/session_63_checklist.md << 'EOF'
# Session 63 Phase Checklist
- [ ] PHASE 0: Orient + Read 61C/62 Results
- [ ] PHASE 1: Deploy to Railway
- [ ] PHASE 2: Real Photo Testing (face alignment)
- [ ] PHASE 3: Supabase GEDCOM Tables + Import
- [ ] PHASE 4: GEDCOM Face Linking
- [ ] PHASE 5: Ground Truth Pairs Extraction
- [ ] PHASE 6: Isotonic Regression Calibration
- [ ] PHASE 7: Recalibration Hooks
- [ ] PHASE 8: Batch Re-Run (271 photos)
- [ ] PHASE 9: Documentation + Self-Assessment
EOF
```

### ═══════════════════════════════════════════════════════
### AFTER EVERY PHASE — NO EXCEPTIONS — DO NOT SKIP THIS
### ═══════════════════════════════════════════════════════
```bash
# 1. Commit
git add -A && git commit -m "63 phase N: [description]"

# 2. Update checklist
sed -i 's/- \[ \] PHASE N/- [x] PHASE N/' /tmp/session_63_checklist.md

# 3. CLEAR context (mandatory — not /compact, not optional)
/clear

# 4. After /clear, re-read ONLY what you need for next phase:
cat /tmp/session_63_checklist.md
NEXT=N+1
sed -n "/^## PHASE $NEXT:/,/^## PHASE/p" /tmp/session_63_prompt.md | head -60
cat /tmp/session_63_context.md | head -40
git log --oneline -3
```
### ═══════════════════════════════════════════════════════

**WHY**: Sessions 61C and 62 both failed to /clear between phases.
61C hit 0% context and degraded during API calls. Do not repeat.

---

## PHASE 0: Orient + Read 61C/62 Results (~8 min)

### 0A: Read Assessments
```bash
cat docs/session_context/session_61c_assessment.md
cat docs/session_context/session_61c_outcomes.md 2>/dev/null
cat docs/session_context/session_62_assessment.md
cat docs/session_context/session_62_outcomes.md 2>/dev/null
```

### 0B: Read 61C Comparison Report
```bash
cat results/gedcom_enrichment_comparison_report.md 2>/dev/null || \
  echo "No comparison report found — check results/ for analysis files"
ls results/run_*.json 2>/dev/null | head -20
```

Answer these questions (write answers to /tmp/session_63_decisions.md):
1. Did Variant D (first-order) improve over C (curated)?
2. Did Variant E (co-occurrence) help or add noise?
3. What was Flash's "GEDCOM confusion bug"?
4. Is Flash viable for bulk work despite 3% errors?

### 0C: Inventory Unresolved Issues
```bash
echo "=== U1: GEDCOM Supabase tables ==="
# Check if tables exist
python3 -c "
from supabase import create_client
import os
sb = create_client(os.getenv('SUPABASE_URL',''), os.getenv('SUPABASE_KEY',''))
for t in ['gedcom_individuals','gedcom_events','gedcom_relationships','gedcom_face_links']:
    try:
        r = sb.table(t).select('id').limit(1).execute()
        print(f'✓ {t}: exists ({len(r.data)} rows)')
    except Exception as e:
        print(f'✗ {t}: MISSING — {e}')
" 2>/dev/null || echo "Check Supabase connection"

echo "=== U6: Face alignment real test ==="
ls results/face_alignment_test_*.json 2>/dev/null || \
  echo "✗ No real photo test results — MUST test in Phase 2"

echo "=== U8: Railway deploy status ==="
git log --oneline -3
# Check if latest commits are deployed
```

Commit: `chore: 63 orient — assessed 61C/62 gaps, decisions logged`

**→ /clear → re-read Phase 1**

---

## PHASE 1: Deploy to Railway (~5 min)

### 1A: Push to Production
```bash
git push origin main
```

### 1B: Verify Deploy
```bash
# Wait for Railway deploy (usually 2-3 min)
sleep 30
curl -s https://rhodesli.nolanandrewfox.com/ | head -5
curl -s https://rhodesli.nolanandrewfox.com/collections | head -5

# Check version
curl -s https://rhodesli.nolanandrewfox.com/ | grep -i "version\|v0\."
```

### 1C: Verify Face Alignment Endpoints Exist
```bash
# These should return 404 or empty (no data yet) — not 500
curl -s -o /dev/null -w "%{http_code}" \
  https://rhodesli.nolanandrewfox.com/api/face-alignment/test123
echo " (expect 404 or empty JSON, not 500)"
```

Commit: `deploy: 63 phase 1 — v0.65.0 live on Railway`

**→ /clear → re-read Phase 2**

---

## PHASE 2: Real Photo Testing — Face Alignment (~12 min)

### THIS IS THE #1 PRIORITY OF SESSION 63.
Session 62 built face alignment but NEVER tested it on real photos.

### 2A: Pick 3-5 Test Photos
```python
"""
Select photos for testing:
1. A photo with 2 faces (simple case)
2. A photo with 5+ faces (group photo — the hard case)
3. The Vida Capeluto photo (if identifiable — the PRD-015 motivation)
4. A photo with confirmed identities (verify description matches person)
5. A photo where old x-sorting is known to fail

Log photo IDs to /tmp/test_photos.txt
"""
```

### 2B: Run Face Alignment on Each Photo
```bash
# For each test photo:
PHOTO_ID="[fill in]"

# POST to trigger alignment
curl -X POST "https://rhodesli.nolanandrewfox.com/api/face-alignment/$PHOTO_ID" \
  -H "Content-Type: application/json" | python3 -m json.tool | head -30

# GET to verify stored result
curl -s "https://rhodesli.nolanandrewfox.com/api/face-alignment/$PHOTO_ID" \
  | python3 -m json.tool | head -30
```

### 2C: Evaluate Results
For each photo, verify:
- Gemini received the face coordinates (check logs)
- Descriptions are assigned to correct faces (not swapped)
- Age estimates are reasonable for the era (1900-1940)
- Mismatch handling works (if face counts differ)
- Cost per photo logged

### 2D: Log Results
```bash
cat > /tmp/face_alignment_results.md << 'EOF'
# Face Alignment Real Photo Test Results
| Photo | Faces | Aligned | Correct | Cost | Notes |
|-------|-------|---------|---------|------|-------|
| [id1] | N | N | Y/N | $X.XX | ... |
EOF
```

**If face alignment FAILS on real photos**: stop and fix before
proceeding. Do NOT continue to batch re-run with broken alignment.

Commit: `test: 63 phase 2 — face alignment verified on N real photos`

**→ /clear → re-read Phase 3**

---

## PHASE 3: Supabase GEDCOM Tables + Import (~10 min)

### 3A: Create Tables
The import script from 61C exists but tables were never created.

```sql
-- Run via Supabase client or Dashboard
CREATE TABLE IF NOT EXISTS gedcom_individuals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gedcom_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    death_date TEXT,
    death_place TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gedcom_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID REFERENCES gedcom_individuals(id),
    event_type TEXT NOT NULL,
    date TEXT,
    place TEXT,
    description TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS gedcom_face_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    face_id TEXT NOT NULL,
    gedcom_individual_id UUID REFERENCES gedcom_individuals(id),
    confidence FLOAT,
    linked_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gedcom_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID REFERENCES gedcom_individuals(id),
    related_individual_id UUID REFERENCES gedcom_individuals(id),
    relationship_type TEXT NOT NULL
);
```

### 3B: Run Import
```bash
# Find the GEDCOM file
GEDCOM=$(find ~/Downloads -name "*.ged" -maxdepth 2 | head -1)
echo "GEDCOM: $GEDCOM"

# Run 61C's import script
python3 scripts/import_gedcom_supabase.py --file "$GEDCOM" --verbose 2>&1 | tail -10

# Verify
python3 -c "
from supabase import create_client; import os
sb = create_client(os.getenv('SUPABASE_URL',''), os.getenv('SUPABASE_KEY',''))
for t in ['gedcom_individuals','gedcom_events','gedcom_relationships']:
    r = sb.table(t).select('id', count='exact').execute()
    print(f'{t}: {r.count} rows')
"
```

Commit: `feat: 63 phase 3 — GEDCOM tables created + data imported`

**→ /clear → re-read Phase 4**

---

## PHASE 4: GEDCOM Face Linking (~10 min)

### Goal
Match Rhodesli's identified faces to GEDCOM individuals by name.
Without this, GEDCOM enrichment only works for manually linked photos.

### 4A: Build Fuzzy Matching
Add to `rhodesli_ml/gedcom_context.py` (or create new module):

```python
def match_faces_to_gedcom(supabase):
    """
    For each identified face in Rhodesli:
    1. Get the person name
    2. Fuzzy match against gedcom_individuals.name
    3. If match confidence > 0.8: auto-link
    4. If 0.5-0.8: log for admin review
    5. Insert into gedcom_face_links table

    Handle name variations:
    - "Big Leon" → "Leon Capeluto"
    - "Victoria" → "Victoria Capeluto"
    - Maiden names, nicknames, transliterations
    """
```

### 4B: Run Linking
```bash
python3 -c "
from rhodesli_ml.gedcom_context import match_faces_to_gedcom
# Run matching, report results
" 2>&1 | tail -20
```

### 4C: Report
```bash
python3 -c "
from supabase import create_client; import os
sb = create_client(os.getenv('SUPABASE_URL',''), os.getenv('SUPABASE_KEY',''))
r = sb.table('gedcom_face_links').select('*', count='exact').execute()
print(f'Total links: {r.count}')
# Count by confidence bucket
"
```

Commit: `feat: 63 phase 4 — GEDCOM face linking (N auto-linked, M for review)`

**→ /clear → re-read Phase 5**

---

## PHASE 5: Ground Truth Pairs Extraction (~10 min)

### 5A: Create Calibration Pairs Table
```sql
CREATE TABLE IF NOT EXISTS calibration_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    face_id_a TEXT NOT NULL,
    face_id_b TEXT NOT NULL,
    similarity_score FLOAT NOT NULL,
    is_match BOOLEAN NOT NULL,
    source TEXT NOT NULL,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(face_id_a, face_id_b)
);
```

### 5B: Extract Match Pairs
```python
"""
Source: admin merges (faces confirmed as same person)
For every identity with 2+ faces:
  for each face pair under that identity:
    compute similarity → insert as match (source='admin_merge')
"""
```

### 5C: Extract Non-Match Pairs
```python
"""
Source: implicit_different_id
For every pair of DIFFERENT identified people:
  pick one face from each person
  compute similarity → insert as non-match

Sampling strategy:
- Prioritize hard negatives (similarity > 0.3)
- Include easy negatives (similarity < 0.2) to anchor low end
- Target ~1:1 match:non-match ratio
"""
```

### 5D: Report Pair Stats
```bash
python3 -c "
# Count: total, match, non-match
# Score distributions per class
# Save stats to /tmp/pair_stats.md
"
```

Commit: `feat: 63 phase 5 — ground truth pairs (N match, M non-match)`

**→ /clear → re-read Phase 6**

---

## PHASE 6: Isotonic Regression Calibration (~12 min)

### 6A: Create Calibration Module
Create `rhodesli_ml/similarity_calibration.py`:

```python
"""
Converts raw InsightFace cosine similarity → P(same person)
Uses isotonic regression (more flexible than logistic/Platt).

Design: continuous recalibration, versioned models, handles
future non-match spike when "reject" UX launches.

AD reference: AD-145 Stage 1
"""
from sklearn.isotonic import IsotonicRegression

class SimilarityCalibrator:
    def __init__(self, supabase): ...

    def fit(self, pairs=None):
        """Fit isotonic regression on calibration_pairs table."""

    def predict(self, score: float) -> float:
        """Raw score → calibrated P(match). Returns 0-1."""

    def should_recalibrate(self) -> tuple[bool, str]:
        """Check: >20 new pairs, >50% class shift, >30 days old."""

    def recalibrate_if_needed(self) -> bool:
        """Recalibrate if triggered. Compare to previous model.
        If threshold shift > 0.1: flag for review, don't auto-deploy."""

    def get_threshold(self, target_precision=0.9) -> float:
        """Raw score threshold for target precision."""

    def get_confidence_label(self, prob: float) -> str:
        """> 0.9 High, 0.7-0.9 Medium, 0.5-0.7 Low, < 0.5 Unlikely"""

    def calibration_report(self) -> dict:
        """AUC, precision@95recall, threshold@90precision, pair counts."""

    def _save_model_version(self): ...
    def _load_latest_model(self): ...
```

### 6B: Fit Initial Model
```python
"""
1. Load all pairs from calibration_pairs
2. Split 80/20 train/validation
3. Fit isotonic regression on train
4. Evaluate: AUC, calibration plot, threshold@90precision
5. Save model version 1 to Supabase
6. Print report
"""
```

### 6C: Wire into Compare/Match Display
Update similarity display in app:
- Show "85% match" instead of "similarity: 0.67"
- Confidence labels: High/Medium/Low/Unlikely
- Raw score always preserved underneath

### 6D: Tests (use subagent)
5-8 tests: fit, predict monotonic, bounded 0-1, threshold,
confidence labels, should_recalibrate triggers.

Commit: `feat(ml): 63 phase 6 — isotonic regression calibration`

**→ /clear → re-read Phase 7**

---

## PHASE 7: Recalibration Hooks (~10 min)

### 7A: Event Hooks
```python
async def on_face_merge(face_id_a, face_id_b, merged_by):
    """Insert match pair → check recalibration trigger."""

async def on_match_reject(face_id_a, face_id_b, rejected_by):
    """Insert non-match pair (weight=1.5) → check trigger.
    Ready for future 'reject' UX."""

async def on_identity_confirm(face_id, identity_name, confirmed_by):
    """Generate implicit non-match pairs with other identities.
    Sample — don't insert all pairs (could be huge)."""
```

### 7B: Safety Rails
```python
"""
- Rate limit: max 1 recalibration per hour
- Drift detection: threshold shift > 0.1 → flag for review
- Never change past merge decisions retroactively
- Log: old_threshold, new_threshold, drift_amount
"""
```

### 7C: Admin Endpoint
```python
# GET /api/calibration/status → model version, pair counts, AUC, drift
# POST /api/calibration/recalibrate → force recalibration
```

### 7D: Tests
4-6 tests: merge creates pair, reject creates weighted pair,
rate limit, drift detection.

Commit: `feat(ml): 63 phase 7 — recalibration hooks + safety rails`

**→ /clear → re-read Phase 8**

---

## PHASE 8: Batch Re-Run 271 Photos (~10 min)

### ⚠️ PREREQUISITE CHECK
```bash
echo "=== BATCH PREREQUISITES ==="
echo "1. Face alignment on real photos:"
cat /tmp/face_alignment_results.md 2>/dev/null | head -5

echo "2. GEDCOM in Supabase:"
python3 -c "
from supabase import create_client; import os
sb = create_client(os.getenv('SUPABASE_URL',''), os.getenv('SUPABASE_KEY',''))
r = sb.table('gedcom_individuals').select('id', count='exact').execute()
print(f'  Individuals: {r.count}')
" 2>/dev/null

echo "3. Calibration model fitted:"
python3 -c "
from rhodesli_ml.similarity_calibration import SimilarityCalibrator
print('  ✓ Module importable')
" 2>/dev/null || echo "  ✗ Not ready"

echo "4. Budget remaining:"
echo "  61C spent: \$2.46 / \$10.00"
echo "  271 photos × \$0.02 = \$5.42 (interactive) or \$2.71 (batch API)"
```

If ANY prerequisite fails: create PENDING_APPROVALS entry and skip to Phase 9.

### 8A: Run 5 Validation Photos First
```bash
python3 scripts/run_full_pipeline.py \
  --photos 5 \
  --model gemini-3.1-pro-preview \
  --gedcom-variant curated \
  --include-alignment \
  --output results/batch_validation_5.json 2>&1 | tail -10
```

Check quality before committing to 271.

### 8B: Submit Batch (if validation good)
```python
"""
Use Gemini Batch API if available (50% discount, 24hr SLA).
Otherwise use interactive API with rate limiting.

Submit all 271 photos with:
- Model: gemini-3.1-pro-preview
- GEDCOM variant: curated
- Face alignment: enabled
- Store results versioned in Supabase

Log batch job ID for tracking.
If batch API not available: run interactively with 2s delays.
"""
```

### 8C: Create Results Processor
```python
"""
Script to process batch results when they arrive:
1. Parse response
2. Store in Supabase (versioned)
3. Update calibration pairs with new data
4. Generate old-vs-new comparison
"""
```

Commit: `feat: 63 phase 8 — batch re-run [submitted/deferred]`

**→ /clear → re-read Phase 9**

---

## PHASE 9: Documentation + Self-Assessment (~8 min)

### 9A: Write ADs
- AD-XXX: Isotonic regression for similarity calibration
- AD-XXX: Continuous recalibration with non-match spike handling
- AD-XXX: Batch re-run strategy

### 9B: Update BACKLOG (append-only)
- Community "reject" UX (enables explicit non-match pairs)
- Active learning: surface uncertain pairs for labeling
- Calibration drift monitoring dashboard
- GEDCOM face link admin review UI

### 9C: Update ROADMAP (with conflict check)
```bash
cp ROADMAP.md /tmp/roadmap_pre_63.md
# Append only — do not rewrite
diff /tmp/roadmap_pre_63.md ROADMAP.md
wc -l ROADMAP.md  # Must stay < 150
```

### 9D: Session Outcomes
Create `docs/session_context/session_63_outcomes.md`:
- Unresolved items fixed (U1-U10 status)
- Face alignment real test results
- Calibration model stats (AUC, thresholds, pair counts)
- Batch re-run status
- What Session 64 should do

### 9E: SELF-ASSESSMENT (mandatory)
```bash
echo "=== SESSION 63 SELF-ASSESSMENT ==="

echo "--- U1: GEDCOM tables ---"
python3 -c "..." 2>/dev/null  # Check tables exist with data

echo "--- U6: Real photo test ---"
cat /tmp/face_alignment_results.md 2>/dev/null | head -3

echo "--- U8: Deploy ---"
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/

echo "--- Calibration ---"
python3 -c "from rhodesli_ml.similarity_calibration import SimilarityCalibrator; print('✓')"

echo "--- Tests ---"
pytest tests/ -x -q --tb=short 2>&1 | tail -3

echo "--- ROADMAP ---"
wc -l ROADMAP.md
```

**Fix any failures before declaring session complete.**

Commit: `docs: 63 phase 9 — session complete, self-assessment`

---

## SESSION RULES

- **CLEAR AFTER EVERY PHASE** — run `/clear` then re-read next phase
  from `/tmp/session_63_prompt.md`. Do NOT use `/compact`. Do NOT skip.
- Before doing ANYTHING in a phase, re-read that phase's instructions
  from the prompt file. Your memory after /clear is EMPTY.
- Budget: ~$12.54 max ($7.54 remaining from 61C + $5 for batch)
- Deploy via git push (NOT Railway dashboard)
- Commit after every phase with descriptive message
- Update BOTH ROADMAP and BACKLOG when completing/deferring items
- Before editing ROADMAP/BACKLOG: save to /tmp for diff
- ROADMAP stays < 150 lines
- All algorithmic decisions → ALGORITHMIC_DECISIONS.md with provenance
- Calibration models are versioned — never overwrite
- Never retroactively change past merge decisions
- If face alignment fails on real photos: STOP and fix before batch
- Do NOT filter GEDCOM data for privacy — include all records
- End with self-assessment — MANDATORY
- This session runs overnight autonomously
