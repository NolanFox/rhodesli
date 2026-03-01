# Session 82c: Gemini Re-run with GEDCOM Enrichment
# Tool: Claude Code
# Branch: session-82c/gemini-rerun

---

## SETUP

```bash
git checkout -b session-82c/gemini-rerun
git push -u origin session-82c/gemini-rerun
```

Read these files first (in order):
1. `CLAUDE.md`
2. All files in `.claude/rules/`
3. `docs/session_context/session-82-context.md`
4. `ROADMAP.md`
5. `docs/ALGORITHMIC_DECISIONS.md` (find all Gemini-related ADs)
6. Any existing Gemini pipeline code: `grep -rn "gemini\|alignment\|enrichment" --include="*.py" . | grep -v __pycache__ | grep -v test | head -40`

Run baseline tests:
```bash
pytest tests/ -x -q
```

---

## CONTEXT

We have 269 photo alignments from Session 64d, but the prompts may have been simplified (cost was 5x cheaper than estimated). We need to:
1. Validate that Gemini adds real value with GEDCOM enrichment
2. Use the Asheville photo as our litmus test
3. Run in controlled batches with budget gates
4. Surface the results clearly in the app

---

## PHASE 0: ORIENT + VALIDATE EXISTING STATE (~5 min)

```bash
echo "=== GEMINI STATE AUDIT ==="

# Check what Gemini data we have
python3 -c "
import json, os
files = ['gemini_api_calls', 'photo_alignments', 'alignment_results']
for f in files:
    for ext in ['.json', '.jsonl']:
        path = f'data/{f}{ext}'
        if os.path.exists(path):
            print(f'{path}: exists')
        path = f'rhodesli_ml/data/{f}{ext}'
        if os.path.exists(path):
            print(f'{path}: exists')
"

# Check Supabase tables
# (use whatever DB access method is available)

# Find the Asheville photo
grep -rn "asheville\|Asheville\|victoria.*capuano\|Victoria.*Capuano\|capeluto.*children" data/ rhodesli_ml/data/ --include="*.json" | head -10

# Check current gemini pipeline code
ls scripts/*gemini* rhodesli_ml/pipelines/*gemini* 2>/dev/null

# Check API key availability
echo "GEMINI_API_KEY set: $([ -n \"$GEMINI_API_KEY\" ] && echo 'yes' || echo 'no')"

echo "=== END AUDIT ==="
```

Document findings. Identify the Asheville photo's UUID.

Commit: `docs: session 82c phase 0 — gemini state audit`

Use `/clear` before Phase 1.

---

## PHASE 1: ASHEVILLE LITMUS TEST — 3-Variant Experiment (~15 min)

### Find the Photo
Locate the photo of Victoria Capuano Capeluto with 3 of her 4 children. It's currently geolocated to Brooklyn incorrectly. Find its UUID and all associated data.

### Build the 3 Variants

**Variant A: No GEDCOM context**
```python
prompt_a = """
Analyze this historical photograph. Describe the scene, estimate the 
date and location, identify any text or landmarks, and describe the 
people visible. Be as specific as possible about the likely geographic 
location based on visual evidence.
"""
```

**Variant B: Full GEDCOM context**
```python
# Pull ALL GEDCOM events for Victoria and her children
# Include: births, deaths, marriages, residences, immigration, census records
# Include first-order connections (spouses, siblings, parents)
prompt_b = """
Analyze this historical photograph. You have access to genealogical 
records for the people identified in this photo:

{gedcom_context}

Using both the visual evidence in the photo AND the genealogical records 
above, estimate the date and location of this photo. Consider:
- Where did these people live at various points in their lives?
- Do any visual clues (architecture, vegetation, clothing, signs) 
  match a specific location from their records?
- What life events (weddings, gatherings, holidays) might this photo 
  document?

Be specific about your location reasoning. If you can narrow it to a 
city or neighborhood, do so with your confidence level.
"""
```

**Variant C: Curated GEDCOM context**
```python
# Pre-filter GEDCOM to only include:
# - Location/time events within ±15 years of estimated photo date
# - First-order connections' location events in same timeframe
# - Privacy filter: exclude anyone born after 1930 or flagged as living
prompt_c = """
[Same as Variant B but with curated context]
"""
```

### Run the Experiment
```python
import json, time

results = {}
total_cost = 0

for variant_name, prompt in [("A_no_gedcom", prompt_a), 
                              ("B_full_gedcom", prompt_b), 
                              ("C_curated_gedcom", prompt_c)]:
    # Call Gemini API
    result = call_gemini(
        photo_id=asheville_photo_uuid,
        prompt=prompt,
        model="gemini-3.1-pro-preview"  # Use Pro, not Flash
    )
    
    results[variant_name] = result
    total_cost += result.get("cost", 0)
    
    print(f"Variant {variant_name}:")
    print(f"  Location estimate: {result.get('location_estimate')}")
    print(f"  Confidence: {result.get('confidence')}")
    print(f"  Cost: ${result.get('cost', 0):.4f}")
    print(f"  Running total: ${total_cost:.4f}")
    
    time.sleep(2)  # Rate limit buffer

# Save results
with open("results/asheville_litmus_test.json", "w") as f:
    json.dump(results, f, indent=2)
```

### Evaluate
```python
# Ask Gemini to compare its own results
meta_prompt = """
You previously analyzed the same photograph three times with different 
levels of context. Here are your three analyses:

Variant A (no genealogy data): {result_a}
Variant B (full genealogy data): {result_b}  
Variant C (curated genealogy data): {result_c}

The GROUND TRUTH is that this photo was taken in Asheville, North Carolina.

Compare your three analyses:
1. Which variant got closest to the correct location?
2. What specific genealogical data points helped (or would have helped)?
3. What visual clues in the photo support Asheville?
4. Rate each variant's accuracy on a 1-10 scale.
5. Recommend which variant approach should be used for batch processing.
"""
```

### Budget Check
```bash
echo "=== ASHEVILLE TEST COST ==="
echo "Variant A: $X"
echo "Variant B: $X"  
echo "Variant C: $X"
echo "Meta-comparison: $X"
echo "Total Phase 1: $X"
echo ""
echo "Budget remaining: $(echo '3.00 - TOTAL' | bc)"
echo "If over $3, STOP and report to Nolan."
```

Commit: `experiment: asheville litmus test — 3 GEDCOM variants`

Use `/clear` before Phase 2.

---

## PHASE 2: ASSESS VALUE + DECIDE BATCH APPROACH (~5 min)

Based on the Asheville results, answer:
1. Does GEDCOM enrichment meaningfully improve location accuracy?
2. Is the curated variant better than full? (signal-to-noise)
3. What's the per-photo cost for the winning variant?
4. Projected cost for all 271 photos?
5. Is this worth running at scale?

### Decision Gate
If GEDCOM enrichment clearly helped (Asheville identified correctly in B or C but not A):
→ Proceed to Phase 3 (batch preparation)

If GEDCOM enrichment made no difference:
→ Skip to Phase 4 (document findings, propose alternative approach)

If results are ambiguous:
→ Run 5 more test photos (mix of GEDCOM-linked and not) before deciding

Document the decision in `ALGORITHMIC_DECISIONS.md`:
- AD-XXX: Gemini GEDCOM enrichment value assessment
- Include: experimental results, cost analysis, recommendation

Commit: `docs: AD-XXX gemini GEDCOM enrichment assessment`

Use `/clear` before Phase 3.

---

## PHASE 3: BATCH PREPARATION (~10 min)

### Only proceed here if Phase 2 approved batch processing.

### Build the Batch Pipeline
```python
"""
scripts/run_gemini_enrichment.py

Usage: python scripts/run_gemini_enrichment.py \
  --variant [A|B|C] \
  --batch-size 10 \
  --max-cost 10.00 \
  --output results/gemini_batch_{timestamp}.json

Features:
- Processes photos in batches of 10
- Prints cost after each batch
- Stops if cumulative cost exceeds --max-cost
- Saves results incrementally (no data loss on crash)
- Logs every API call to gemini_api_calls table
- Uses Gatekeeper pattern: all results are PROPOSALS
- Supports resume from last completed photo
"""
```

### Privacy Safeguards
```python
def filter_gedcom_for_privacy(gedcom_data):
    """
    MANDATORY before any GEDCOM data goes to Gemini:
    - Remove anyone born after 1930
    - Remove anyone flagged as living
    - Remove any personally identifiable info for living people
    - Keep only: name, birth year, death year, locations, events
    """
```

### Run First Batch (10 photos)
- Select 10 photos with mix of: GEDCOM-linked, identified faces, unidentified
- Run with winning variant from Phase 1
- Review results manually
- Check: did any results improve over existing data?

### Budget Gate
After first batch of 10:
```bash
echo "=== BATCH 1 RESULTS ==="
echo "Photos processed: 10"
echo "Cost: $X"
echo "Projected full cost (271 photos): $X"
echo "Photos with improved data: X/10"
echo ""
echo "Continue? (budget remaining vs projected total)"
```

If first batch shows improvement: continue in batches of 10, checking cost each time.
If first batch shows no improvement: STOP and document why.

Commit: `feat: gemini enrichment batch pipeline with budget gates`

Use `/clear` before Phase 4.

---

## PHASE 4: SURFACE RESULTS IN APP (~10 min)

### Only proceed if batch results show value.

The Gemini enrichment results need to be visible in the app. Currently:
- Photo pages show Gemini analysis (scene description, tags, etc.)
- Map shows locations (some incorrectly, like Asheville→Brooklyn)

### Fix Map Location Data
If the Asheville experiment succeeded:
1. Update the photo's location data with the corrected result
2. Use the Gatekeeper pattern: stage as proposal, mark for admin review
3. Admin sees: "Gemini suggests: Asheville, NC (was: Brooklyn, NY). Evidence: [reasoning]. Accept / Reject?"

### Create "Analysis Improved" Indicator
When Gemini re-analysis produces better results:
- Show a subtle badge on the photo: "📍 Location updated" or "🔍 New insights"
- In admin view, show before/after comparison
- This creates the engagement loop: "Your identification of [Person] helped improve the analysis of [Photo]"

### Test:
```python
def test_gemini_results_displayed_on_photo_page():
    """Photo page shows latest Gemini analysis."""

def test_map_location_updates_after_enrichment():
    """Map reflects corrected location data."""

def test_gatekeeper_stages_gemini_proposals():
    """Gemini results are proposals, not auto-applied."""
```

Commit: `feat: surface gemini enrichment results with gatekeeper`

---

## PHASE 5: DOCUMENTATION + PR (~5 min)

### Update docs:
- `ALGORITHMIC_DECISIONS.md`: ADs for GEDCOM enrichment, privacy filtering, batch pipeline, gatekeeper integration
- `CHANGELOG.md`: v0.82c
- `docs/session_logs/session-82c-log.md`: Full session log
- `docs/session_context/session-82c-assessment.md`: Self-assessment
- Update ML plan in context: date estimation ✅ → gemini enrichment ✅ → similarity calibration (next)

### Create PR:
```bash
git add .
git commit -m "docs: session 82c complete — gemini enrichment pipeline"
git push origin session-82c/gemini-rerun

gh pr create \
  --title "Session 82c: Gemini Re-run with GEDCOM Enrichment" \
  --body "## Summary

### Asheville Litmus Test
- Tested 3 variants: no GEDCOM, full GEDCOM, curated GEDCOM
- Result: [which variant won and why]
- Asheville correctly identified: [yes/no]

### Batch Pipeline
- Processed X photos with winning variant
- Cost: $X total
- Photos with improved data: X/Y

### App Integration
- Gatekeeper pattern for all Gemini proposals
- Map location corrections staged for admin review
- 'Analysis improved' indicators on enriched photos

### Budget
- Total API cost: $X
- Under $10 cap: [yes/no]

## Evaluation
All Gemini results are PROPOSALS awaiting admin review." \
  --base main \
  --head session-82c/gemini-rerun
```

---

## DO NOT:
- Auto-apply Gemini results to public-facing data (Gatekeeper pattern!)
- Send living people's data to Gemini (privacy filter MANDATORY)
- Exceed $10 total API cost without stopping
- Skip the Asheville litmus test
- Use Batch API (too slow — use sync pipeline)
- Modify face detection or embedding code
- Touch any code that 82a or 82b might be modifying

## CRITICAL REMINDERS:
- Use `/clear` (not `/compact`) between phases
- Commit after every phase
- Track cost after EVERY API call
- All Gemini outputs are proposals, never auto-published
- Backup before any data writes
- Validate UUIDs before database operations
