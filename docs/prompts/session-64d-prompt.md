# Session 64d: Batch Process Remaining 144 Photos
# Rhodesli Heritage Photo Archive
# Created: 2026-02-23
# Run in parallel with Session 64c (concerns + harness)

# ═══════════════════════════════════════════════════════
# GIT SETUP — DO THIS FIRST
# This session runs in parallel with Session 64c.
# Each session works on its own branch to avoid conflicts.
# ═══════════════════════════════════════════════════════

```bash
git checkout main
git pull origin main
git checkout -b session-64d
```

If `git pull` fails or there are uncommitted changes, resolve before proceeding.

# ═══════════════════════════════════════════════════════
# READ NEXT — MANDATORY
# ═══════════════════════════════════════════════════════

Read these files IN ORDER:
1. `CLAUDE.md`
2. `docs/session_context/session_64b_assessment.md`
3. `ALGORITHMIC_DECISIONS.md` — read AD-153 (API tracking), AD-155 (combined pipeline)
4. `rhodesli_ml/gemini_config.py` or wherever GEMINI_MODEL is defined
5. `scripts/run_combined_pipeline.py`

Confirm you have read all five. Print: the configured model name, and whether GEMINI_API_KEY is available:
```bash
echo "GEMINI_API_KEY set: $([ -n \"$GEMINI_API_KEY\" ] && echo YES || echo NO)"
echo "Model config:"
grep -n "GEMINI_MODEL\|gemini-3" rhodesli_ml/gemini_config.py 2>/dev/null || grep -rn "GEMINI_MODEL" rhodesli_ml/ --include="*.py" | head -5
```

# ═══════════════════════════════════════════════════════
# SESSION RULES (NON-NEGOTIABLE)
# ═══════════════════════════════════════════════════════

1. Every Gemini API call → log via `log_gemini_call()`.
2. If rate limited: save progress, log rate_limit_type, STOP gracefully.
3. Print cost running total every 20 photos.
4. If total cost exceeds $5.00: STOP and report.
5. Use `gemini-3.1-pro-preview` for production calls (NOT Flash).
6. Verify model used matches config BEFORE starting batch.
7. Commit progress checkpoints every 50 photos.

# ═══════════════════════════════════════════════════════
# PHASE 1: Pre-flight checks (~3 min)
# ═══════════════════════════════════════════════════════

## 1A: Verify API access

```bash
# Quick test: can we reach the Gemini API?
python -c "
from google import genai
import os
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
# Tiny test call — text only, minimal tokens
response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents='Say hello in one word.'
)
print(f'API accessible: YES')
print(f'Response: {response.text[:50]}')
" 2>&1
```

If API is not accessible:
- Print the error
- Check if GEMINI_API_KEY is set
- If not set: STOP. Print instructions for Nolan to set it and re-run.
- If set but error: check if it's a billing/quota issue

## 1B: Identify remaining photos

```bash
python -c "
from app.supabase_data import get_supabase_client
sb = get_supabase_client()

# All photos
all_photos = sb.table('photos').select('photo_id').execute()

# Already aligned
aligned = sb.table('face_gemini_alignments').select('photo_id').execute()
aligned_ids = {r['photo_id'] for r in aligned.data}

total = len(all_photos.data)
done = len(aligned_ids)
remaining = total - done
print(f'Total photos: {total}')
print(f'Already aligned: {done}')
print(f'Remaining: {remaining}')
print(f'Estimated cost (Pro sync): \${remaining * 0.028:.2f}')
print(f'Estimated cost (Pro batch): \${remaining * 0.014:.2f}')
" 2>&1
```

## 1C: Check Batch API availability

```bash
python -c "
from google import genai
import os
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
# Check if batch API is available for our model
try:
    # List available models to check batch support
    models = client.models.list()
    for m in models:
        if 'gemini-3.1-pro' in m.name.lower() or 'gemini-3-pro' in m.name.lower():
            print(f'{m.name} — batch: {getattr(m, \"supported_generation_methods\", \"unknown\")}')
except Exception as e:
    print(f'Model list error: {e}')
    print('Will fall back to synchronous processing.')
" 2>&1
```

Print all pre-flight results. Proceed to Phase 2 if API is accessible.

Commit: `docs: Session 64d pre-flight check results`

# ═══════════════════════════════════════════════════════
# PHASE 2: Run batch — Batch API path (~30 min wait)
# Preferred: 50% cost savings, no rate limit issues.
# ═══════════════════════════════════════════════════════

**If Batch API IS available for gemini-3.1-pro-preview:**

1. Prepare JSONL input file:
```python
# For each remaining photo:
# - Load InsightFace coordinates
# - Build GEDCOM context via _build_parsed_gedcom_from_supabase()
# - Construct the combined prompt (alignment + GEDCOM + extraction)
# - Write as one line in JSONL file
```

2. Upload and submit batch:
```python
from google import genai
client = genai.Client(api_key=GEMINI_API_KEY)

# Upload input file
input_file = client.files.upload("batch_input.jsonl")

# Create batch job
batch = client.batches.create(
    model="gemini-3.1-pro-preview",
    file_name=input_file.name,
    display_name=f"rhodesli-alignment-{datetime.now().strftime('%Y%m%d')}"
)
print(f"Batch job created: {batch.name}")
print(f"Status: {batch.state}")
```

3. Poll for completion (or save batch ID for manual check later):
```python
import time
while batch.state not in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'):
    time.sleep(60)
    batch = client.batches.get(batch.name)
    print(f"Status: {batch.state} — {getattr(batch, 'completion_stats', 'pending')}")
```

4. Process results and save to Supabase + log to gemini_api_calls.

**If batch wait exceeds 15 minutes:** Save the batch job ID, document how to retrieve results later, and proceed to Phase 3. Don't block the session.

# ═══════════════════════════════════════════════════════
# PHASE 2-ALT: Run batch — Synchronous fallback
# If Batch API not available for this model.
# ═══════════════════════════════════════════════════════

**If Batch API is NOT available:**

Use the existing combined pipeline with rate-limit-aware batching:

```bash
GEMINI_API_KEY=$GEMINI_API_KEY python scripts/run_combined_pipeline.py \
    --skip-aligned \
    --model gemini-3.1-pro-preview \
    --delay 3.0 \
    --max-cost 5.00 \
    --batch-id "session-64d-$(date +%Y%m%d)" \
    2>&1 | tee results/session_64d_batch_log.txt
```

If `--skip-aligned` flag doesn't exist, add it:
```python
# Skip photos that already have alignments in Supabase
aligned_ids = {r['photo_id'] for r in sb.table('face_gemini_alignments').select('photo_id').execute().data}
photos_to_process = [p for p in all_photos if p['photo_id'] not in aligned_ids]
```

**Rate limit handling:**
- On 429 (RESOURCE_EXHAUSTED):
  - Log to gemini_api_calls with status='rate_limited'
  - Save checkpoint: which photos completed, which remain
  - Print: "Rate limited after N photos. Completed: N. Remaining: N."
  - If RPM limit: wait 60 seconds, retry
  - If RPD limit: STOP, save progress, document for manual re-run tomorrow

**Progress tracking:**
```
After every 20 photos:
  Completed: N/144
  Cost so far: $X.XX
  Average cost/photo: $X.XXXX
  Model used: gemini-3.1-pro-preview (VERIFY — if different, STOP)
  Errors: N
  Rate limits hit: N
```

Commit checkpoint every 50 photos:
`feat(ml): batch alignment progress — N/144 photos (checkpoint)`

# ═══════════════════════════════════════════════════════
# PHASE 3: Verify results + model audit (~5 min)
# ═══════════════════════════════════════════════════════

After batch completes (or rate-limits out):

```sql
-- How many photos now have alignments?
SELECT count(*) as total_aligned FROM face_gemini_alignments;

-- What models were used?
SELECT model_used, count(*) as calls, 
       sum(cost_usd) as total_cost,
       avg(latency_ms) as avg_latency_ms
FROM gemini_api_calls 
WHERE batch_id LIKE 'session-64d%'
GROUP BY model_used;

-- Any errors?
SELECT status, count(*) FROM gemini_api_calls 
WHERE batch_id LIKE 'session-64d%'
GROUP BY status;

-- Cost summary
SELECT 
    count(*) as total_calls,
    sum(cost_usd) as total_cost,
    avg(cost_usd) as avg_cost_per_call,
    min(cost_usd) as min_cost,
    max(cost_usd) as max_cost
FROM gemini_api_calls 
WHERE batch_id LIKE 'session-64d%' AND status = 'success';
```

**Model drift check:** If any call used a model OTHER than gemini-3.1-pro-preview, that's a red flag. Document it.

**Cost sanity check:** 
- Expected: ~$0.028/photo for Pro sync, ~$0.014/photo for Pro batch
- If average cost is significantly different, investigate

Print full results.

Commit: `docs: Session 64d batch results — N photos aligned, $X.XX total cost`

# ═══════════════════════════════════════════════════════
# PHASE 4: Merge to main (~2 min)
# ═══════════════════════════════════════════════════════

```bash
git checkout main
git pull origin main
git merge session-64d --no-edit
```

If merge conflicts (because 64c pushed first):
- Resolve conflicts — 64d owns: gemini_api_calls inserts, face_gemini_alignments inserts, results/ logs
- 64c owns: app code, tests, harness files, ROADMAP, BACKLOG
- If conflict is in SESSION_HISTORY.md: keep both sessions' additions

```bash
git push origin main
```

If push fails (64c pushed while we were merging): `git pull --rebase origin main && git push origin main`

Clean up:
```bash
git branch -d session-64d
```

# ═══════════════════════════════════════════════════════
# PHASE 5: Session assessment (~2 min)
# ═══════════════════════════════════════════════════════

```
## Session 64d Assessment
- Duration: X minutes
- Photos processed: N/144
- Total aligned: N/271 (X%)
- Total cost: $X.XX
- Average cost/photo: $X.XXXX
- Model used: [confirm gemini-3.1-pro-preview]
- Errors: N
- Rate limits hit: N

## Alignment Coverage
- Before 64d: 127/271 (47%)
- After 64d: N/271 (X%)
- Remaining: N photos

## If incomplete:
- Re-run command: [exact command to resume]
- Estimated remaining cost: $X.XX
- Rate limit resets at: midnight Pacific

## GEDCOM enrichment:
- Photos with GEDCOM context: N
- Photos without GEDCOM context: N
- Quality observation: [did GEDCOM-enriched results look better?]
```

Commit: `docs: Session 64d assessment — alignment coverage N%`

# ═══════════════════════════════════════════════════════
# WHAT THIS SESSION DELIVERS
# ═══════════════════════════════════════════════════════
#
# 1. All remaining photos processed through combined pipeline
#    (alignment + GEDCOM enrichment + full extraction)
# 2. Every API call logged with model, cost, tokens, status
# 3. Model drift verified (all calls used correct model)
# 4. Cost analysis: actual vs expected
# 5. Alignment coverage: 47% → target 100%
#
# This runs in PARALLEL with 64c (concerns + harness).
# This session ONLY touches: 
#   - face_gemini_alignments table (inserts)
#   - gemini_api_calls table (inserts)
#   - results/ directory (logs)
# It does NOT modify any app code, tests, or harness files.
# ═══════════════════════════════════════════════════════
