# Session 61: Gemini Photo Detective + Multi-Photo Compare + ML Iteration Loop

## SESSION IDENTITY
- **Session**: 61
- **Predecessor**: Session 60/60B (Gemini Progressive Refinement + UX Unification)
- **Lineage**: 60 (shipped architecture) → 60B (verification, found gaps) → 61 (this session)
  - There is no "60C" — the 60B gap fixes are ACT 0 of this session.
  - See `session_61_planning_context.md` Section 1 for full reconciliation.
- **Goal**: Wire the enriched Gemini pipeline end-to-end, add multi-photo upload,
  surface "Photo Detective" UX, implement MLflow experiment tracking for Flash vs Pro comparison
- **Estimated time**: 90-120 minutes
- **Context file**: `docs/session_context/session_61_planning_context.md`
- **Post-61 planning**: See context file Section 9. Session 62 candidates:
  PRD-015 face alignment, Flash vs Pro comparison run, LoRA similarity calibration.
  These are tracked in BACKLOG, NOT implemented in 61.

---

## ⚠️ CONTEXT MANAGEMENT — MANDATORY

This session uses aggressive context management to prevent the compaction failures
that have plagued Sessions 47, 49C, and 60.

### Before ANYTHING else:
```bash
cp docs/session_context/session_61_planning_context.md /tmp/session_61_context.md
cat > /tmp/session_61_checklist.md << 'EOF'
# Session 61 Phase Checklist
# Lineage: 60 → 60B → 61 (no 60C — gaps folded into ACT 0)
# Post-61: see context file Section 9
- [ ] ACT 0: Orient + Fix 60 Gaps
- [ ] ACT 1: ML Pipeline — Wire Enriched Prompt + MLflow
- [ ] ACT 2: Multi-Photo Upload
- [ ] ACT 3: Photo Detective UX
- [ ] ACT 4: Data Storage Verification
- [ ] ACT 5: Documentation + Verification Gate + Harness Hardening
EOF
```

### Between EVERY act:
```bash
# 1. Commit current work
git add -A && git commit -m "act N complete: [description]"

# 2. Check context usage
# If context > 50%, run /compact

# 3. Re-read context + checklist
cat /tmp/session_61_context.md | head -80
cat /tmp/session_61_checklist.md

# 4. Update checklist
sed -i 's/- \[ \] ACT N/- [x] ACT N/' /tmp/session_61_checklist.md
```

### At session end:
```bash
# Re-read original prompt and verify EVERY act
cat docs/prompts/session_61_prompt.md
cat /tmp/session_61_checklist.md
# Fix any unchecked items before declaring done

# Verify ROADMAP/BACKLOG not corrupted
diff /tmp/roadmap_pre_session61.md ROADMAP.md || true
wc -l ROADMAP.md  # must be < 150

# Verify post-61 work is tracked
grep -q "62\|PRD-015\|Flash.*Pro\|LoRA" BACKLOG.md && \
  echo "✓ Post-61 work tracked" || echo "✗ Post-61 items missing from BACKLOG"
```

---

## ⚡ PARALLELIZATION WITH WORKTREES

Where noted, use subagents with worktree isolation to parallelize independent work.
Rules:
- Only parallelize tasks that don't touch the same files
- Each worktree gets a descriptive branch name
- Merge back to main after completion, run full tests
- If a worktree task fails, fix in main after merge

---

## ACT 0: ORIENT + FIX SESSION 60 GAPS (~10 min)

### 0A: Read Context + Orient
```bash
cat CLAUDE.md
cat docs/session_context/session_61_planning_context.md
head -20 CHANGELOG.md
git log --oneline -15
cat ROADMAP.md
cat BACKLOG.md

# Save pre-session state for conflict checking later (ACT 5)
cp ROADMAP.md /tmp/roadmap_pre_session61.md
cp BACKLOG.md /tmp/backlog_pre_session61.md

# Verify session lineage is clear
echo "Session 61 lineage: 60 → 60B → 61 (ACT 0 fixes 60B gaps)"
echo "Post-61 candidates: PRD-015, Flash/Pro comparison, LoRA"
```

### 0B: Fix Quick-Identify CSS Crash
Session 60B found: CSS selector crash on legacy face IDs.

```bash
# Find the crash
grep -rn "quick.identify\|quickIdentify\|quick_identify" \
  --include="*.py" --include="*.html" --include="*.js" . | head -20

# Find legacy face ID format handling
grep -rn "inbox_\|face_id.*format\|parse.*face" \
  --include="*.py" . | head -20
```

Fix the CSS selector to handle both legacy (`inbox_*`) and new face ID formats.
Test with both formats. The fix must be defensive — never crash on unexpected ID format.

### 0C: Verify Session 60 Enriched Prompt Builder Exists
```bash
# Find the enriched prompt builder
grep -rn "enriched.*prompt\|build.*prompt\|context.*prompt\|verified.*fact" \
  --include="*.py" . | head -20

# Find Gemini API call points
grep -rn "gemini\|genai\|generate_content\|_call_gemini" \
  --include="*.py" . | head -20

# What's the gap?
echo "=== ENRICHED PROMPT BUILDER ==="
# Show the function that builds context-enriched prompts
echo "=== GEMINI API CALLER ==="
# Show the function that calls the API
echo "=== ARE THEY CONNECTED? ==="
# Is there a code path from builder → API call?
```

Document what exists and what's missing. This informs Act 1.

### 0D: Audit Gemini Model References
```bash
echo "=== ALL GEMINI MODEL REFERENCES ==="
grep -rn "gemini-2\|gemini-3\|gemini_model\|GEMINI_MODEL" \
  --include="*.py" --include="*.env*" --include="*.toml" \
  . | grep -v __pycache__ | grep -v ".git/"

echo "=== DEPRECATED MODELS (MUST FIX) ==="
grep -rn "gemini-2.0-flash\|gemini-1.5\|gemini-2.5" \
  --include="*.py" . | grep -v __pycache__
```

If any deprecated model references exist, note them for Act 1.

### 0E: Check Current Supabase State
```bash
# What tables exist? What's being written?
grep -rn "supabase\|SUPABASE" --include="*.py" . | head -30
grep -rn "\.insert\|\.upsert\|\.update\|\.select" --include="*.py" . | head -30
```

Commit: `fix: session 60 gaps — quick-identify CSS + audit state`

---

## ACT 1: ML PIPELINE — Wire Enriched Prompt + MLflow (~25 min)

### Goal
Connect the enriched prompt builder to actual Gemini API calls,
implement MLflow experiment tracking, and run a Flash vs Pro comparison.

### ⚡ PARALLELIZABLE: Launch as worktree `ml-pipeline` if Act 2 is ready

### 1A: Centralize Gemini Model Config

Create or update `rhodesli_ml/config.py`:
```python
# Gemini model configuration — centralized, never hardcode elsewhere
GEMINI_MODELS = {
    "estimation_bulk": "gemini-3-flash",        # Cost-efficient for batch
    "estimation_detailed": "gemini-3.1-pro-preview",  # Best reasoning
    "face_alignment": "gemini-3.1-pro-preview",  # PRD-015 (future)
    "realtime_upload": "gemini-3-flash",         # Speed for interactive
}

# Pricing (per 1M tokens) for cost tracking
GEMINI_PRICING = {
    "gemini-3-flash": {"input": 0.50, "output": 3.00},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
}
```

Replace ALL hardcoded model strings with config references.
Grep to verify none remain:
```bash
grep -rn '"gemini-' --include="*.py" . | grep -v config.py | grep -v __pycache__
# Should return ZERO results
```

### 1B: Wire Enriched Prompt → Gemini API

This is the **critical gap from Session 60B**.

1. Find the enriched prompt builder function
2. Find the Gemini API call function
3. Connect them:

```python
def analyze_photo_with_context(photo_id, model="estimation_detailed"):
    """
    Full pipeline:
    1. Build enriched prompt with verified facts
    2. Call Gemini with appropriate model
    3. Log to MLflow
    4. Return structured results
    """
    # Step 1: Get enriched prompt
    prompt = build_enriched_prompt(photo_id)  # EXISTS from Session 60

    # Step 2: Call Gemini
    model_name = GEMINI_MODELS[model]
    response = call_gemini(prompt, model_name)  # Wire this connection

    # Step 3: Log to MLflow
    log_gemini_call(photo_id, model_name, prompt, response)

    # Step 4: Return structured result
    return parse_gemini_response(response)
```

The enriched prompt should include:
- The photo (base64 or URI)
- Any confirmed identities in the photo (names, birth years)
- Any confirmed dates for the photo
- Geographic context (Rhodes, specific locations)
- Related photos context (other photos of same people)

### 1C: Install + Configure MLflow

```bash
pip install mlflow --break-system-packages
```

Create `rhodesli_ml/tracking.py`:
```python
import mlflow
import os
import json
from datetime import datetime

MLFLOW_DIR = os.path.join(os.path.dirname(__file__), "mlruns")

def init_tracking():
    """Initialize MLflow tracking."""
    mlflow.set_tracking_uri(f"file://{MLFLOW_DIR}")
    mlflow.set_experiment("rhodesli-date-estimation")

def log_gemini_call(photo_id, model, prompt_text, response, cost=None):
    """Log a single Gemini API call to MLflow."""
    init_tracking()
    with mlflow.start_run(run_name=f"{model}-{photo_id[:8]}"):
        mlflow.log_param("model", model)
        mlflow.log_param("photo_id", photo_id)
        mlflow.log_param("prompt_length", len(prompt_text))
        mlflow.log_param("timestamp", datetime.utcnow().isoformat())

        if response:
            mlflow.log_param("response_length", len(str(response)))
            # Parse structured output
            result = parse_gemini_response(response)
            if result.get("estimated_year"):
                mlflow.log_metric("estimated_year", result["estimated_year"])
            if result.get("confidence"):
                mlflow.log_metric("confidence", result["confidence"])
            if result.get("evidence_count"):
                mlflow.log_metric("evidence_count", result["evidence_count"])

        if cost:
            mlflow.log_metric("cost_usd", cost)

        # Log full prompt and response as artifacts
        with open("/tmp/prompt.txt", "w") as f:
            f.write(prompt_text)
        mlflow.log_artifact("/tmp/prompt.txt")

def log_model_comparison(flash_results, pro_results, photo_ids):
    """Log a Flash vs Pro comparison run."""
    init_tracking()
    with mlflow.start_run(run_name="flash-vs-pro-comparison"):
        mlflow.log_param("flash_model", "gemini-3-flash")
        mlflow.log_param("pro_model", "gemini-3.1-pro-preview")
        mlflow.log_param("photo_count", len(photo_ids))

        # Agreement metrics
        agreements = sum(1 for pid in photo_ids
                        if flash_results[pid]["decade"] == pro_results[pid]["decade"])
        mlflow.log_metric("decade_agreement_rate", agreements / len(photo_ids))

        # Evidence richness comparison
        flash_evidence = sum(flash_results[pid].get("evidence_count", 0) for pid in photo_ids)
        pro_evidence = sum(pro_results[pid].get("evidence_count", 0) for pid in photo_ids)
        mlflow.log_metric("flash_avg_evidence", flash_evidence / len(photo_ids))
        mlflow.log_metric("pro_avg_evidence", pro_evidence / len(photo_ids))

        # Cost comparison
        flash_cost = sum(flash_results[pid].get("cost", 0) for pid in photo_ids)
        pro_cost = sum(pro_results[pid].get("cost", 0) for pid in photo_ids)
        mlflow.log_metric("flash_total_cost", flash_cost)
        mlflow.log_metric("pro_total_cost", pro_cost)
        mlflow.log_metric("pro_cost_premium_pct",
                         ((pro_cost - flash_cost) / flash_cost * 100) if flash_cost > 0 else 0)

        # Save full comparison
        comparison = {
            "photo_ids": photo_ids,
            "flash": flash_results,
            "pro": pro_results,
            "agreement_rate": agreements / len(photo_ids)
        }
        with open("/tmp/comparison.json", "w") as f:
            json.dump(comparison, f, indent=2)
        mlflow.log_artifact("/tmp/comparison.json")
```

### 1D: Create Flash vs Pro Comparison Script

Create `scripts/compare_models.py`:
- Takes `--photos N` (default 20) for eval subset
- Runs the same photos through Flash AND Pro
- Uses the enriched prompt builder for both
- Logs everything to MLflow
- Outputs a summary comparing:
  - Decade agreement rate
  - Evidence richness (how many evidence categories per photo)
  - Confidence calibration
  - Cost difference
  - Which photos changed estimate when using Pro
- **DO NOT RUN THE SCRIPT IN THIS SESSION** — just create it
  - Running it costs money and needs Nolan's approval
  - Include a `--dry-run` flag that shows what would be analyzed

### 1E: Update Gemini API Call Logging to Supabase

Every Gemini API call should ALSO be logged to Supabase for persistence:
```sql
CREATE TABLE IF NOT EXISTS gemini_api_logs (
    id SERIAL PRIMARY KEY,
    photo_id TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT,
    estimated_year INTEGER,
    confidence REAL,
    evidence_json JSONB,
    cost_usd REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

This gives us a persistent record even if MLflow local files are lost.

### Tests
- `test_gemini_config_centralized` — no hardcoded model strings
- `test_enriched_prompt_includes_verified_facts`
- `test_mlflow_logging_creates_run`
- `test_model_comparison_script_dry_run`
- `test_gemini_log_to_supabase`

Commit: `feat(ml): wire enriched prompt → Gemini 3.1 Pro, MLflow tracking, model comparison`

**Update ALGORITHMIC_DECISIONS.md:**
- AD-XXX: Gemini 3.1 Pro model upgrade strategy
- AD-XXX: MLflow experiment tracking for VLM comparison
- AD-XXX: Dual logging (MLflow + Supabase) for API calls

---

## ACT 2: MULTI-PHOTO UPLOAD (~20 min)

### Goal
Face Compare accepts 2+ photos, compares them against each other AND the archive.
All uploaded photos are saved and enter the processing pipeline.

### ⚡ PARALLELIZABLE: Launch as worktree `multi-upload` (independent of Act 1)

### 2A: Write PRD-021

Create `docs/prds/021_multi_photo_compare.md`:

**Problem**: Face Compare currently accepts only 1 photo. Users comparing family
photos need to upload multiple photos to cross-match faces. Every competitive
tool (FamilySearch, MyHeritage, Face++) supports multi-photo or at minimum
2-photo comparison.

**Solution**: Extend the upload to accept 2-5 photos simultaneously.
Detect faces in each, cross-compare all faces, and show results ranked
by match confidence. Every uploaded photo is saved for pipeline processing.

**Success Criteria**:
1. User can upload 2-5 photos via drag-and-drop or file picker
2. Each photo shows face count after upload (before full comparison)
3. Cross-comparison shows all face pairs ranked by similarity
4. Archive matches shown alongside cross-matches
5. All photos saved to R2 with metadata
6. Progress shown via SSE during processing

### 2B: Backend — Multi-File Upload Handler

Modify the compare upload endpoint:

```python
@app.route("/api/compare/upload-multiple", methods=["POST"])
async def compare_upload_multiple(request):
    """Accept 2-5 photos, detect faces, cross-compare."""
    files = await request.form()
    # Validate: 2-5 files, each < 10MB, valid image type

    results = []
    for file in files.getlist("photos"):
        # Save to R2: uploads/compare/{uuid}.{ext}
        saved_path = save_upload(file)
        # Run InsightFace face detection
        faces = detect_faces(saved_path)
        # Run CORAL date estimate if available
        date_est = estimate_date(saved_path) if coral_available else None
        results.append({
            "upload_id": uuid,
            "path": saved_path,
            "faces": faces,
            "date_estimate": date_est
        })

    # Cross-compare all faces between uploaded photos
    cross_matches = cross_compare_faces(results)

    # Compare against archive
    archive_matches = compare_to_archive(results)

    return render_compare_results(results, cross_matches, archive_matches)
```

### 2C: Frontend — Multi-Photo Upload UI

The upload area should:
1. Accept drag-and-drop of multiple files
2. Show thumbnails as files are added
3. "+" button to add more (up to 5)
4. Remove individual photos before comparing
5. Show face count per photo after detection
6. Single "Compare All" button

**This is FastHTML + HTMX. NOT React.**

```python
# Upload zone with multiple file support
Div(
    Input(type="file", name="photos", multiple=True,
          accept="image/*", hx_post="/api/compare/upload-multiple",
          hx_target="#compare-results", hx_indicator="#upload-progress"),
    Div(id="photo-previews"),  # JS fills with thumbnails
    Button("Compare All Faces", type="submit"),
    Div(id="upload-progress", cls="htmx-indicator"),
    id="multi-upload-zone"
)
```

### 2D: Verify Upload → Pipeline Flow

Critical verification — EVERY uploaded photo must:
1. ✅ Be saved to R2 (not just temp)
2. ✅ Have metadata written (uploader, timestamp, status)
3. ✅ Have face detection run and embeddings stored
4. ✅ Be queued for full pipeline processing
5. ✅ Appear in admin uploads queue

```bash
# Upload a test photo via curl
curl -X POST https://rhodesli.nolanandrewfox.com/api/compare/upload-multiple \
  -F "photos=@test1.jpg" -F "photos=@test2.jpg" \
  -H "Cookie: session=..." \
  -o /tmp/compare_result.html

# Verify it was saved
# Check R2 for the upload
# Check admin queue for pending upload
# Check metadata includes status field
```

### 2E: Verify Data Persistence

After upload, verify data reaches Supabase:
```python
def test_upload_persisted_to_supabase():
    """Upload via compare → verify record in Supabase."""
    # Upload test photo
    # Check supabase.table("uploads").select("*").eq("photo_id", test_id)
    # Verify: status, uploader, created_at, face_count all populated
```

### Tests
- `test_multi_upload_accepts_2_photos`
- `test_multi_upload_rejects_6_photos`
- `test_multi_upload_cross_compares_faces`
- `test_multi_upload_includes_archive_matches`
- `test_upload_saved_to_r2`
- `test_upload_appears_in_admin_queue`
- `test_upload_metadata_has_status`

Commit: `feat: multi-photo compare upload — 2-5 photos, cross-matching, archive search`

**Create PRD-021, update BACKLOG.md**

---

## ACT 3: PHOTO DETECTIVE UX (~20 min)

### Goal
Surface Gemini's analysis as a "Photo Detective" experience.
Users should see the AI reasoning about evidence, not just a year number.

### 3A: Write PRD-022

Create `docs/prds/022_photo_detective_ux.md`:

**Concept**: Gemini analyzing a photo is like a detective examining evidence.
The UX should expose this process — showing each evidence category, the
reasoning chain, and how verified facts improve estimates.

**Key UX Elements**:
1. **Evidence Cards**: Each evidence category (clothing, architecture, text, faces)
   gets its own card showing what was detected and how it contributed
2. **Confidence Meter**: Visual indicator of overall estimate confidence
3. **"Before/After" for Progressive Refinement**: When verified facts improve
   an estimate, show what changed and why
4. **Model Comparison Badge**: "Analyzed with Gemini 3.1 Pro" vs "Quick estimate
   with Gemini Flash" — users see the value of deeper analysis
5. **Share Results**: OG-tagged shareable URLs for estimates

### 3B: Evidence Display Component

Create a reusable evidence display that works on:
- `/estimate` page (standalone tool)
- `/photo/{id}` page (inline estimate)
- Compare results (per-photo estimate)

```python
def evidence_card(category, evidence):
    """Render a single evidence category card."""
    icons = {
        "clothing": "👔",
        "architecture": "🏛️",
        "text_signage": "📝",
        "faces_people": "👥",
        "cultural_markers": "🕎",
        "photographic_technique": "📷",
    }
    return Div(
        H4(f"{icons.get(category, '🔍')} {category.replace('_', ' ').title()}"),
        P(evidence.get("description", "")),
        Span(f"Confidence: {evidence.get('strength', 'medium')}",
             cls=f"badge badge-{evidence.get('strength', 'medium')}"),
        cls="evidence-card"
    )

def detective_results(photo_id, analysis):
    """Full Photo Detective results display."""
    return Div(
        # Hero estimate
        Div(
            H2(f"Estimated: c. {analysis['year']} ± {analysis.get('range', 10)} years"),
            Div(confidence_meter(analysis.get('confidence', 0.5)),
                cls="confidence-display"),
            cls="estimate-hero"
        ),
        # Evidence cards
        Div(
            *[evidence_card(cat, ev) for cat, ev in analysis.get('evidence', {}).items()],
            cls="evidence-grid"
        ),
        # Model badge
        Div(
            Span(f"🔍 Analyzed with {analysis.get('model', 'Gemini')}",
                 cls="model-badge"),
            cls="analysis-meta"
        ),
        # Progressive refinement indicator (if re-analyzed)
        progressive_refinement_indicator(photo_id, analysis)
            if analysis.get('previous_estimate') else "",
        # CTAs
        Div(
            A("Help Identify People →", href=f"/photo/{photo_id}"),
            A("Share This Analysis", href=f"/estimate/{photo_id}/share",
              cls="btn-share"),
            cls="detective-ctas"
        ),
        cls="photo-detective-results"
    )
```

### 3C: Update Estimate Page

The standalone `/estimate` page should prominently feature:
1. Upload area (uses multi-photo from Act 2)
2. Archive browser with pagination (24 per page)
3. Each photo shows detective results when clicked
4. Evidence cards visible without expanding
5. "Know the actual date?" correction input
6. Model badge showing which Gemini model was used

### 3D: Update Photo Page

On `/photo/{id}`, if a date estimate exists:
1. Show estimate badge prominently: "c. 1935 ± 5 years"
2. Expandable evidence section (collapsed by default)
3. "See how we estimated this →" link to estimate detail
4. If user-provided date exists, show that as primary
5. If Flash AND Pro estimates exist, show "Deeper analysis available"

### 3E: Progressive Refinement Indicator

When a photo has been re-analyzed with new verified facts:
```python
def progressive_refinement_indicator(photo_id, analysis):
    """Show how verified facts improved the estimate."""
    prev = analysis.get('previous_estimate')
    if not prev:
        return ""
    delta = abs(analysis['year'] - prev['year'])
    return Div(
        H4("🔄 Estimate Updated"),
        P(f"Previous: c. {prev['year']} → Now: c. {analysis['year']}"),
        P(f"Updated because: {analysis.get('refinement_reason', 'New verified facts')}"),
        cls="refinement-indicator"
    )
```

### Tests
- `test_evidence_cards_render_all_categories`
- `test_detective_results_shows_model_badge`
- `test_estimate_page_has_pagination`
- `test_photo_page_shows_estimate_badge`
- `test_progressive_refinement_shows_delta`

Commit: `feat(ux): Photo Detective evidence display, model badges, progressive refinement`

**Create PRD-022, add AD for UX evidence display approach**

---

## ACT 4: DATA STORAGE VERIFICATION (~10 min)

### Goal
Verify that ALL data from uploads and ML processing reaches Supabase/Postgres.
This is a trust-building exercise — Nolan needs confidence the system works.

### 4A: Audit Data Flow

```bash
echo "=== SUPABASE WRITES ==="
grep -rn "supabase.*insert\|supabase.*upsert\|supabase.*update" \
  --include="*.py" . | grep -v __pycache__ | grep -v test

echo "=== JSON FILE WRITES ==="
grep -rn "json.dump\|open.*json.*w" --include="*.py" . | \
  grep -v __pycache__ | grep -v test | grep -v mlruns

echo "=== WHAT'S IN SUPABASE? ==="
# List all tables referenced
grep -rn 'table("' --include="*.py" . | grep -v __pycache__
```

### 4B: Create Data Integrity Report

Write a script that:
1. Counts records in each Supabase table
2. Counts entries in each JSON file
3. Cross-references: do all confirmed identities in JSON also exist in Supabase?
4. Checks: are Gemini API logs being written?
5. Checks: are upload records being created?

```python
# scripts/data_integrity_report.py
def report():
    """Print data integrity summary."""
    print("=== SUPABASE TABLES ===")
    for table in ["identities", "photos", "uploads", "gemini_api_logs"]:
        count = supabase.table(table).select("*", count="exact").execute()
        print(f"  {table}: {count.count} rows")

    print("=== JSON FILES ===")
    for f in ["identities.json", "photo_index.json", "date_labels.json"]:
        data = json.load(open(f"data/{f}"))
        print(f"  {f}: {len(data)} entries")

    print("=== CROSS-CHECK ===")
    # Verify dual-write is working
    # Every Supabase identity should match a JSON identity
```

### 4C: Fix Any Gaps

If the audit reveals data NOT reaching Supabase:
- Add the missing write
- Ensure dual-write pattern (Supabase first, then JSON cache)
- Add a test for the write

### Tests
- `test_data_integrity_report_runs`
- `test_supabase_has_all_confirmed_identities`
- `test_upload_creates_supabase_record`

Commit: `fix: data storage verification — close any Supabase gaps`

---

## ACT 5: DOCUMENTATION + VERIFICATION GATE (~15 min)

### 5A: Update ALGORITHMIC_DECISIONS.md

Add new ADs with full provenance:
- **AD-XXX**: Gemini 3.1 Pro upgrade — model string, pricing, why upgrade, Flash vs Pro strategy
  - Source: Session 61, Gemini 3.1 Pro released Feb 19, 2026
  - Decision: 3.1 Pro for detailed analysis, Flash for bulk/realtime
  - Rejected: Using only Pro (cost), using only Flash (quality)
- **AD-XXX**: MLflow experiment tracking
  - Source: Session 61, need to compare VLM models systematically
  - Decision: MLflow for local tracking + Supabase for persistent API logs
  - Rejected: NotebookLM MCP (fragile), LangChain (overkill), manual spreadsheets
- **AD-XXX**: Multi-photo compare architecture
  - Source: Session 61, PRD-021
  - Decision: Extend existing compare endpoint, 2-5 photos, cross-match + archive
  - Rejected: Separate microservice (code duplication), single-photo only (competitive gap)
- **AD-XXX**: Photo Detective UX pattern
  - Source: Session 61, PRD-022
  - Decision: Evidence cards with category icons, model badges, refinement indicators
  - Rejected: Simple year badge only (hides value), full report page (too heavy)

### 5B: Update ROADMAP.md + BACKLOG.md (WITH CONFLICT CHECK)

**CRITICAL — ROADMAP/BACKLOG conflict prevention protocol:**
```bash
# Step 1: Save current state BEFORE any edits
cp ROADMAP.md /tmp/roadmap_pre_session61.md
cp BACKLOG.md /tmp/backlog_pre_session61.md

# Step 2: Read current state fully
cat ROADMAP.md
cat BACKLOG.md

# Step 3: Make edits (see below)

# Step 4: Diff to verify nothing was lost
diff /tmp/roadmap_pre_session61.md ROADMAP.md
diff /tmp/backlog_pre_session61.md BACKLOG.md

# Step 5: Verify all pre-existing items still present
echo "=== ITEMS IN OLD ROADMAP NOT IN NEW ==="
grep "^\- \[" /tmp/roadmap_pre_session61.md | while read line; do
  grep -qF "$line" ROADMAP.md || echo "MISSING: $line"
done

echo "=== ITEMS IN OLD BACKLOG NOT IN NEW ==="
grep "^\- \[" /tmp/backlog_pre_session61.md | while read line; do
  grep -qF "$line" BACKLOG.md || echo "MISSING: $line"
done
# If ANY items are MISSING → restore them before proceeding
```

ROADMAP:
- Mark Session 61 complete with deliverables
- Update version number
- Update test count
- Next: Session 62 should be one of:
  - PRD-015 face alignment (portfolio crown jewel)
  - Run Flash vs Pro comparison (costs ~$0.62 for 20 photos)
  - Similarity calibration LoRA (from ML plan)
- **Preserve ALL existing planned sessions and backlog items**

BACKLOG:
- Add: "Run compare_models.py with --photos 20" (needs Nolan approval)
- Add: "Run full 271-photo re-analysis with 3.1 Pro" (needs cost approval)
- Add: PRD-015 implementation (deferred, ready when 61 ships)
- Update any completed items' status (OPEN → DONE)
- **Do NOT remove or overwrite existing items — only add or update status**

### 5C: Save Session Context for Next Session

Create `docs/session_context/session_61_outcomes.md`:
- What shipped
- What was deferred
- MLflow experiment structure
- Flash vs Pro script ready to run (awaiting approval)
- Multi-photo upload state
- Data integrity status

### 5D: Update SESSION_HISTORY.md

### 5E: Harden Harness for Session Continuity

This addresses the recurring problem of sessions losing context during
compaction (happened in sessions 47, 49C, 60, and the planning conversation).

1. **Add dual-update rule** to CLAUDE.md or `.claude/rules/`:
   ```
   When completing tasks, update BOTH:
   1. ROADMAP.md — check the box, add date, move to "Recently Completed"
   2. BACKLOG.md — update the Status column (OPEN → DONE) for the corresponding item
   Never update one without the other.
   ```

2. **Add session context breadcrumb rule**:
   ```
   Every session context file must include:
   - Link to predecessor session context file
   - List of work deferred to future sessions
   - Post-session planning section with candidate next sessions
   ```

3. **Add deployment tooling rule** to CLAUDE.md:
   ```
   Deployment:
   - Deploy via git push (NOT Railway dashboard)
   - Browser testing: use Claude Chrome (preferred), Playwright if unavailable
   - Upload testing: curl against production endpoints
   - Smoke test mandatory after every deploy
   - Update SESSION_HISTORY.md when trimming ROADMAP
   ```

4. **Verify all rules are readable by Claude Code**:
   ```bash
   # Check CLAUDE.md isn't over reasonable size
   wc -l CLAUDE.md
   # Check all referenced rule files exist
   ls .claude/rules/*.md 2>/dev/null
   # Check ROADMAP.md is under 150 lines
   wc -l ROADMAP.md
   ```

Commit: `fix(harness): dual-update rule, session breadcrumbs, deployment tooling rules`

### 5F: Verification Gate

```bash
echo "=== SESSION 61 VERIFICATION ==="

# Act 0: Quick-identify CSS fixed
echo "--- Quick-identify CSS ---"
pytest tests/ -k "quick_identify" -x -q 2>/dev/null || echo "No quick-identify tests found"

# Act 1: ML Pipeline wired
echo "--- ML Pipeline ---"
grep -q "gemini-3.1-pro-preview" rhodesli_ml/config.py && echo "✓ 3.1 Pro configured" || echo "✗ MISSING: 3.1 Pro config"
python -c "import mlflow; print('✓ MLflow installed')" 2>/dev/null || echo "✗ MISSING: MLflow"
ls scripts/compare_models.py && echo "✓ Comparison script" || echo "✗ MISSING: compare script"
grep -q "enriched.*prompt\|build.*enriched" rhodesli_ml/*.py app/*.py && echo "✓ Enriched prompt wired" || echo "✗ MISSING: enriched prompt connection"

# Act 2: Multi-photo upload
echo "--- Multi-Photo Upload ---"
grep -q "upload-multiple\|upload_multiple\|multiple.*photo" app/main.py && echo "✓ Multi-upload endpoint" || echo "✗ MISSING: multi-upload"
ls docs/prds/021_multi_photo_compare.md && echo "✓ PRD-021" || echo "✗ MISSING: PRD-021"

# Act 3: Photo Detective UX
echo "--- Photo Detective ---"
grep -q "evidence.card\|evidence_card\|detective" app/main.py && echo "✓ Evidence cards" || echo "✗ MISSING: evidence display"
ls docs/prds/022_photo_detective_ux.md && echo "✓ PRD-022" || echo "✗ MISSING: PRD-022"

# Act 4: Data storage
echo "--- Data Storage ---"
grep -q "gemini_api_logs" app/main.py rhodesli_ml/*.py 2>/dev/null && echo "✓ API log table" || echo "✗ MISSING: API log writes"

# Act 5: Docs
echo "--- Documentation ---"
ls docs/session_context/session_61_outcomes.md && echo "✓ Session outcomes" || echo "✗ MISSING: outcomes doc"

# Act 5 bonus: Harness hardening
echo "--- Harness ---"
grep -q "ROADMAP.*BACKLOG\|dual.update\|update BOTH" CLAUDE.md .claude/rules/*.md 2>/dev/null && echo "✓ Dual-update rule" || echo "✗ MISSING: dual-update rule"
grep -q "Railway\|git push\|deploy" CLAUDE.md .claude/rules/*.md 2>/dev/null && echo "✓ Deploy rules" || echo "✗ MISSING: deploy rules"

# ROADMAP/BACKLOG conflict check
echo "--- Conflict Check ---"
if [ -f /tmp/roadmap_pre_session61.md ]; then
  MISSING=$(grep "^\- \[" /tmp/roadmap_pre_session61.md | while read line; do
    grep -qF "$line" ROADMAP.md || echo "$line"
  done)
  [ -z "$MISSING" ] && echo "✓ No ROADMAP items lost" || echo "✗ LOST ITEMS: $MISSING"
else
  echo "⚠ No pre-session backup found — manual review needed"
fi
wc -l ROADMAP.md | awk '{print ($1 <= 150) ? "✓ ROADMAP under 150 lines ("$1")" : "✗ ROADMAP too long ("$1" lines)"}'

# Full test suite
echo "--- Tests ---"
pytest tests/ -x -q --tb=short 2>&1 | tail -5

# Data integrity
echo "--- Data Integrity ---"
pytest tests/test_data_integrity.py -x -q 2>&1 | tail -3

echo "=== END VERIFICATION ==="
```

Fix any failures before declaring session complete.

Commit: `docs: session 61 complete — ADs, PRDs, ROADMAP, outcomes`
`git push`

---

## SESSION RULES

- Start app and verify EVERY change in browser/curl
- Run tests after EVERY act
- Check requirements.txt for any new dependencies
- Check Dockerfile for any new imports
- Handle missing API keys gracefully (degrade, don't crash)
- Handle missing insightface gracefully (scene-only mode)
- DO NOT run Gemini API calls against real photos without --dry-run
- DO NOT modify confirmed identity data
- Commit after every act with descriptive messages
- **Deploy via git push → Railway auto-deploys (NOT Railway dashboard)**
- **Browser testing: Claude Chrome preferred, Playwright if unavailable**
- Test uploads with real files, not mocks
- Every AD entry must have: decision, rejected alternatives, source session, rationale
- Keep docs under 300 lines each
- ROADMAP.md under 150 lines
- If context exceeds 50% at any point, /compact and re-read context file
- Verify dependency gate: pytest tests/test_dependency_gate.py
- Update ALGORITHMIC_DECISIONS.md after EVERY algorithmic decision (mandatory)
- **Update BOTH ROADMAP.md AND BACKLOG.md when completing items (dual-update)**
- **Before editing ROADMAP/BACKLOG: save current versions to /tmp for diff**
- **After editing ROADMAP/BACKLOG: verify no items were lost via diff**
- **Session context file must link to predecessor and list deferred work**
