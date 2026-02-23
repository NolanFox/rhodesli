# Session 64: Verify, Migrate, Harden
# Rhodesli Heritage Photo Archive
# Created: 2026-02-23

# ═══════════════════════════════════════════════════════
# READ FIRST — MANDATORY
# ═══════════════════════════════════════════════════════

Read these files IN ORDER before doing anything else:
1. `CLAUDE.md`
2. `ALGORITHMIC_DECISIONS.md` (last 10 entries)
3. `ROADMAP.md`
4. `docs/session_context/session_64_context.md` (the planning context for this session)
5. `BACKLOG.md`

Confirm you have read all five. Print the last AD number and the current ROADMAP line count.

# ═══════════════════════════════════════════════════════
# SESSION RULES (NON-NEGOTIABLE)
# ═══════════════════════════════════════════════════════

1. ONE deliverable per phase. Do not combine.
2. Commit after EVERY phase. Message format: `feat|fix|docs(scope): description`
3. After EVERY phase: print context window usage percentage.
4. If context < 40%: run `/clear` and re-read CLAUDE.md + this prompt before continuing.
5. If context < 20%: STOP. Do not continue. Log what's done and what remains.
6. NEVER use `/compact`. Always `/clear` + re-read from disk.
7. Every ML behavior change → update ALGORITHMIC_DECISIONS.md with full provenance.
8. Every ROADMAP/BACKLOG edit → diff first, confirm no items silently dropped.
9. All Gemini API calls → log model, tokens, cost, latency, status, photo_id.
10. Postgres is the source of truth. JSON files are cache-only or eliminated.

# ═══════════════════════════════════════════════════════
# PHASE 0: HARNESS HARDENING (~15 min)
# This phase builds the infrastructure that makes
# all future sessions better. Do this FIRST.
# ═══════════════════════════════════════════════════════

## Phase 0A: Create Skills

Create the following files. Each skill is a markdown file in `.claude/skills/`.

### `.claude/skills/session-run.md`
```markdown
---
description: "Framework for overnight/autonomous Claude Code sessions. Use when executing a multi-phase session prompt."
---
# Overnight Session Execution

## Protocol
1. Read CLAUDE.md, then the session prompt, then referenced context files
2. Execute phases sequentially — ONE deliverable per phase
3. Commit after every phase with descriptive message
4. Print context % after every phase
5. If context < 40%: /clear and re-read CLAUDE.md + prompt
6. If context < 20%: STOP. Log progress to SESSION_HISTORY.md
7. NEVER use /compact — it's lossy. Use /clear + re-read from disk

## Commit Discipline
- Atomic commits: one logical change per commit
- Run tests before commit: `pytest tests/ -x -q --ignore=tests/e2e/`
- Format: `feat|fix|docs(scope): description`

## Verification Gate (end of every track)
- Re-read the original prompt
- Check each phase: completed/skipped/partial
- List any deviations with reasoning
- Run full test suite
- Log results to session history
```

### `.claude/skills/deploy-verify.md`
```markdown
---
description: "Deploy to Railway and verify production. Use after completing code changes."
---
# Deploy and Verify

## Steps
1. `git push origin main`
2. Wait 60 seconds for Railway deploy
3. Verify these routes return 200 (not 500):
   - `/` (landing page)
   - `/map`
   - `/connect`
   - `/tree`
   - `/timeline`
   - `/collections`
   - `/compare`
4. Pick one photo with face data → verify face overlays render
5. Pick one photo with alignment data → verify per-face cards show
6. Report: all routes OK / which failed

## If any route fails:
- Do NOT proceed with other work
- Fix the 500 first
- Re-deploy and re-verify
```

### `.claude/skills/ml-pipeline.md`
```markdown
---
description: "Protocol for modifying ML code. Use whenever editing rhodesli_ml/ or core/*.py files that affect ML behavior."
---
# ML Code Modification Protocol

## Before making changes:
1. Read the relevant section of ALGORITHMIC_DECISIONS.md
2. Read any referenced PRDs (docs/prds/)
3. Understand the current behavior and why it exists

## After making changes:
1. Update ALGORITHMIC_DECISIONS.md with new AD entry:
   - Decision title
   - What was decided
   - What alternatives were considered and rejected
   - Why this approach was chosen
   - Source/breadcrumb to prior decisions
2. Run: `pytest rhodesli_ml/tests/ -v`
3. Run: `pytest tests/ -x -q --ignore=tests/e2e/`
4. If tests fail, fix before proceeding

## Invariants:
- Gatekeeper pattern: ML outputs are PROPOSALS until admin accepts
- Confirmed data feeds back as ground truth anchors
- Never overwrite user-entered data with ML predictions
```

### `.claude/skills/assess-session.md`
```markdown
---
description: "Assess Claude Code session output. Use after a session completes to evaluate quality before proceeding."
disable-model-invocation: true
---
# Session Assessment Protocol

## Read the session output/transcript and evaluate:

### For each phase:
- Status: completed / skipped / partial
- If partial: what was missed and why
- Tests: how many added, total passing

### Red flag checklist:
- [ ] Data stored in JSON instead of Supabase?
- [ ] API calls made without logging model/cost/tokens?
- [ ] Gemini model drift (used Flash when Pro was specified)?
- [ ] ALGORITHMIC_DECISIONS.md not updated after ML changes?
- [ ] Tests skipped or test count decreased?
- [ ] ROADMAP/BACKLOG items silently dropped?
- [ ] Production smoke test not run?
- [ ] /compact used instead of /clear?

### Output format:
```
## Session [N] Assessment
- Duration: X minutes
- Phases: N/N completed
- Tests: +N new, NNNN total passing
- Concerns: [list]
- Follow-up needed: [list]
```
```

### `.claude/skills/build-prompt.md`
```markdown
---
description: "Build a session prompt following Rhodesli best practices. Use when planning the next session."
disable-model-invocation: true
---
# Session Prompt Builder

## Inputs needed:
1. ROADMAP.md current priorities
2. BACKLOG.md open items
3. Last session assessment (from /skill:assess-session)
4. Any specific goals from Nolan

## Best practices to enforce:
- ONE deliverable per phase
- Total prompt under 3500 tokens per track
- /clear between phases (mandatory, explicit, repeated)
- Verification gate at end of each track
- Commit per phase
- Context file in docs/session_context/ with breadcrumbs
- Prompt file in docs/prompts/
- Small enough phases that context window doesn't fill up

## Template structure:
1. READ FIRST block (files to read in order)
2. SESSION RULES (non-negotiable constraints)
3. Phases grouped by track (if using worktrees)
4. Each phase: goal, steps, tests, commit message
5. Verification gate per track
6. Documentation updates (AD, ROADMAP, SESSION_HISTORY)

## Before finalizing:
- Diff ROADMAP.md — no items may be silently removed
- Diff BACKLOG.md — no items may be silently removed
- Check that all open concerns from last assessment have a phase
```

Commit: `feat(harness): add 5 Claude Code skills for session execution, deploy, ML, assessment, prompt building`

## Phase 0B: Create Rules (path-scoped)

### `.claude/rules/ml-development.md`
```markdown
# ML Development Rules
- ALWAYS read ALGORITHMIC_DECISIONS.md before modifying ML code
- ALWAYS update AD after ML changes with full provenance
- Gatekeeper pattern: ML outputs are proposals, admin accepts/rejects
- Confirmed data = ground truth anchors for training
- Cost per API call must be logged
- Model version must be logged per API call
```

### `.claude/rules/data-layer.md`
```markdown
# Data Layer Rules
- Postgres/Supabase is the source of truth for ALL structured data
- JSON files are cache-only or deprecated — never primary store
- User-entered data MUST be in Supabase (AD-135)
- Never overwrite user data with ML predictions
- Dual-write is a temporary bridge, not permanent architecture
- New features store in Postgres from day one
```

### `.claude/rules/session-protocol.md`
```markdown
# Session Protocol Rules
- Use /clear (NEVER /compact) between phases when context is low
- Commit after every phase
- Run tests before every commit
- Print context % after every phase
- If context < 20%, STOP and log progress
- Update SESSION_HISTORY.md at session end
- Update ROADMAP.md — never silently drop items
```

Commit: `docs(harness): add path-scoped rules for ML, data layer, session protocol`

## Phase 0C: Configure Hooks

Update `.claude/settings.json` (create if not exists). Merge with any existing settings:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "bash -c 'INPUT=$(cat); CMD=$(echo \"$INPUT\" | jq -r .tool_input.command 2>/dev/null); if echo \"$CMD\" | grep -qE \"^git commit\"; then cd \"$CLAUDE_PROJECT_DIR\" && python -m pytest tests/ -x -q --ignore=tests/e2e/ 2>&1 | tail -5; fi'"
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "bash -c 'INPUT=$(cat); FILE=$(echo \"$INPUT\" | jq -r .tool_input.file_path // .tool_input.path // \"\" 2>/dev/null); if echo \"$FILE\" | grep -qE \"(rhodesli_ml|core)/.*\\.py$\"; then echo \"REMINDER: Update ALGORITHMIC_DECISIONS.md if this changes ML behavior.\" >&2; fi'"
        }]
      }
    ],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "osascript -e 'display notification \"Claude Code session completed\" with title \"Rhodesli\"' 2>/dev/null; exit 0"
      }]
    }]
  }
}
```

**Test hooks:** Make a trivial change to any file and verify the hook fires. If on Linux (not macOS), replace osascript with: `echo 'Session complete' | wall 2>/dev/null; exit 0`

Commit: `feat(harness): configure pre-commit test gate, ML edit reminder, completion notification hooks`

## Phase 0D: Trim CLAUDE.md

Current CLAUDE.md is too long. Restructure it:
1. Read current CLAUDE.md completely
2. Identify what should stay (project identity, stack, critical invariants)
3. Identify what should move to rules/ or skills/ (already created above)
4. Rewrite CLAUDE.md to under 2000 characters. Target structure:

```
# Rhodesli — Heritage Photo Archive for the Jewish Community of Rhodes

## Stack
FastHTML + HTMX | Supabase/Postgres | Cloudflare R2 | Railway | InsightFace + PyTorch + Gemini

## Critical Invariants
- Postgres is source of truth for all structured data (not JSON files)
- ML outputs use Gatekeeper pattern: proposals → admin review → confirmed
- Confirmed data feeds back as ground truth anchors
- Deploy via git push (not Railway dashboard)

## ML Roadmap
Date estimation (done) → Similarity calibration (done, AUC 0.9577) → Face alignment (in progress) → LoRA fine-tuning

## Session Protocol
See .claude/rules/session-protocol.md
See .claude/skills/session-run.md

## Domain Rules
See .claude/rules/ml-development.md
See .claude/rules/data-layer.md
```

5. DIFF old vs new. Confirm nothing critical was lost — anything removed must exist in a rule or skill file.

Commit: `refactor(harness): trim CLAUDE.md to <2000 chars, move domain rules to .claude/rules/`

**Print context %. If < 40%, /clear and re-read CLAUDE.md + this prompt.**

# ═══════════════════════════════════════════════════════
# PHASE 0E: Set up worktrees
# ═══════════════════════════════════════════════════════

Push the Phase 0 commits first:
```bash
git push origin main
```

Then create worktrees for parallel tracks:
```bash
git worktree add ../rhodesli-track-a -b session-64-track-a main
git worktree add ../rhodesli-track-b -b session-64-track-b main
```

If worktrees fail (e.g., not a git repo, permissions):
- **Fallback:** Run Track A first, commit+push, then /clear, then Track B
- Log the failure for future debugging

Commit: (no commit needed — worktrees are local)

**NOW /clear and re-read CLAUDE.md + this prompt. Start Track A.**

# ═══════════════════════════════════════════════════════
# TRACK A: VERIFY + MIGRATE (in worktree track-a)
# Working directory: ../rhodesli-track-a/
# Resolves: Concerns 1, 5, 6 from Session 63 assessment
# ═══════════════════════════════════════════════════════

## Track A Phase 1: Audit the data layer

Run these diagnostic commands and print ALL output:

```bash
echo "=== FACE ALIGNMENT DATA LOCATIONS ==="
# Where is face alignment data stored?
find . -name "face_alignments*" -o -name "batch_alignment*" | head -20
ls -la data/face_alignments.json 2>/dev/null
ls -la results/batch_alignment_*.json 2>/dev/null

echo ""
echo "=== SUPABASE TABLE CHECK ==="
# Does face_gemini_alignments table exist and have data?
psql "$DATABASE_URL" -c "SELECT count(*) FROM face_gemini_alignments;" 2>&1
psql "$DATABASE_URL" -c "SELECT count(*) FROM face_gemini_alignments WHERE alignment_data IS NOT NULL;" 2>&1

echo ""
echo "=== JSON FILE INVENTORY ==="
# All JSON data files (not config, not package.json)
find . -name "*.json" -path "*/data/*" -o -name "*.json" -path "*/results/*" | sort

echo ""
echo "=== GEMINI MODEL AUDIT ==="
# What model did Session 63 actually use?
grep -rn "gemini" rhodesli_ml/scripts/run_batch_alignment.py 2>/dev/null | head -10
grep -rn "model" results/batch_alignment_*.json 2>/dev/null | head -5
grep -rn "GEMINI_MODEL\|gemini-3\|gemini-2" rhodesli_ml/ --include="*.py" | grep -v __pycache__ | head -20

echo ""
echo "=== CALIBRATION CHECK ==="
# Is isotonic regression fitted and accessible?
python -c "
from rhodesli_ml.calibration import load_calibration
cal = load_calibration()
print(f'Calibration loaded: {cal is not None}')
if cal: print(f'Type: {type(cal).__name__}')
" 2>&1

echo ""
echo "=== RECALIBRATION HOOKS CHECK ==="
# Do the hooks exist? Are they called from app endpoints?
grep -rn "on_face_merge\|on_match_reject\|on_identity_confirm" --include="*.py" . | grep -v __pycache__ | head -20
```

Print the full output. Based on findings, document:
- Is face alignment in JSON-only, Supabase-only, or both?
- What Gemini model was used for the batch?
- Are recalibration hooks dead code or live?
- What JSON files still exist as primary data stores?

Commit: `docs: Session 64 Track A data layer audit results`

## Track A Phase 2: Migrate face alignment to Supabase

Based on audit findings:

1. If `face_gemini_alignments` table exists but is empty:
   - Read face alignment data from JSON files
   - Insert into Supabase table with proper schema
   - Verify row count matches

2. If table doesn't exist:
   - Create it with schema matching Session 62 design
   - Populate from JSON files

3. Update the face alignment code to write to Supabase FIRST, then optionally cache to JSON:
   ```python
   # Pattern: Supabase is source of truth
   async def save_face_alignment(photo_id, alignment_data, model_used, cost, tokens):
       # Write to Supabase
       supabase.table('face_gemini_alignments').upsert({
           'photo_id': photo_id,
           'alignment_data': alignment_data,
           'model_used': model_used,
           'cost': cost,
           'tokens_used': tokens,
           'created_at': datetime.utcnow().isoformat()
       }).execute()
   ```

4. Update any code that reads face alignment data to read from Supabase, not JSON.

Tests:
- `test_face_alignment_saves_to_supabase`
- `test_face_alignment_reads_from_supabase`
- `test_alignment_data_schema_valid`

Commit: `feat(data): migrate face alignment storage from JSON to Supabase`

## Track A Phase 3: Verify UI integration + wire hooks

1. **Calibrated scores in UI:**
   - Find where similarity scores are displayed (compare view, match display)
   - Verify the isotonic regression calibration is being called
   - If raw cosine scores still show: wire calibration into the display pipeline
   - Score should show as "85% match" not "0.73 similarity"

2. **Per-face description cards:**
   - Find the photo detail view
   - Check if face alignment data (from Supabase) is rendered per-face
   - If not: add face card component showing aligned description, age estimate, position

3. **Recalibration hooks — wire if dead:**
   - `on_face_merge`: should fire when admin merges two face identities → add new calibration pair
   - `on_match_reject`: should fire when admin rejects a match proposal → add negative pair
   - `on_identity_confirm`: should fire when admin confirms an identity → update ground truth
   - Check the app's merge/identify/reject endpoints. If hooks aren't called: add the calls.

Tests:
- `test_calibrated_score_display`
- `test_face_card_shows_alignment_data`
- `test_recalibration_hook_fires_on_merge`
- `test_recalibration_hook_fires_on_reject`

Commit: `feat(ui): wire calibrated scores, face cards, recalibration hooks into app`

## Track A Verification Gate

Re-read this prompt's Track A section. For each phase:
- [ ] Phase 1: Audit completed, findings documented
- [ ] Phase 2: Face alignment migrated to Supabase, reads from Supabase
- [ ] Phase 3: Calibrated scores display, face cards show, hooks fire

Run full test suite:
```bash
pytest tests/ -x -q --ignore=tests/e2e/
pytest rhodesli_ml/tests/ -v
```

Merge Track A back to main:
```bash
cd ../rhodesli  # main worktree
git merge session-64-track-a
git push origin main
```

**NOW /clear and re-read CLAUDE.md + this prompt. Start Track B.**

# ═══════════════════════════════════════════════════════
# TRACK B: BATCH COMPLETE + API LOGGING (in worktree track-b)
# Working directory: ../rhodesli-track-b/
# Resolves: Concerns 2, 3, 4, 7 from Session 63 assessment
# ═══════════════════════════════════════════════════════

**IMPORTANT:** If running sequentially (no worktrees), merge Track A first, then /clear, then start here.

## Track B Phase 1: Create gemini_api_calls tracking table

Create a Supabase table for API call logging:

```sql
CREATE TABLE IF NOT EXISTS gemini_api_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id TEXT NOT NULL,
    model_used TEXT NOT NULL,
    call_type TEXT NOT NULL,  -- 'alignment', 'enrichment', 'combined', 'date_estimation'
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC(10, 6),
    latency_ms INTEGER,
    status TEXT NOT NULL,  -- 'success', 'rate_limited', 'error', 'timeout'
    error_message TEXT,
    rate_limit_type TEXT,  -- 'rpm', 'rpd', 'tpm', null if not rate limited
    response_summary JSONB,  -- key fields from response (not full response)
    gemini_config JSONB,  -- thinking_level, max_output_tokens, temperature
    created_at TIMESTAMPTZ DEFAULT now(),
    batch_id TEXT  -- groups calls from same batch run
);

CREATE INDEX idx_gemini_calls_photo ON gemini_api_calls(photo_id);
CREATE INDEX idx_gemini_calls_model ON gemini_api_calls(model_used);
CREATE INDEX idx_gemini_calls_status ON gemini_api_calls(status);
CREATE INDEX idx_gemini_calls_batch ON gemini_api_calls(batch_id);
```

Create a Python logging utility:
```python
# rhodesli_ml/api_logging.py
async def log_gemini_call(photo_id, model_used, call_type, **kwargs):
    """Log every Gemini API call to Supabase for analysis."""
    # ... insert into gemini_api_calls
```

Backfill from Session 63 data if available (check results/*.json for model/cost info).

Tests:
- `test_api_call_logging_creates_record`
- `test_api_call_logging_rate_limit_status`

AD entry: `AD-XXX: Gemini API call tracking table for model/cost/performance analysis`

Commit: `feat(data): gemini_api_calls tracking table + logging utility`

## Track B Phase 2: Audit and fix combined pipeline

1. **Audit what Session 63 batch actually did:**
   ```bash
   # What does run_batch_alignment.py actually send to Gemini?
   cat rhodesli_ml/scripts/run_batch_alignment.py
   # Does it include GEDCOM context? Or just coordinates?
   grep -n "gedcom\|GEDCOM\|genealog\|enrichment\|context" rhodesli_ml/scripts/run_batch_alignment.py
   ```

2. **If alignment-only (no GEDCOM context):**
   Create combined pipeline script that sends ONE Gemini call per photo with:
   - InsightFace face coordinates (for alignment)
   - Curated GEDCOM context (family names, birth years, relationships)
   - Photo metadata (collection, source, existing identifications)
   - Request: date estimate + per-face descriptions + location analysis

   This implements the winning combination from Session 61C:
   `gemini-3.1-pro-preview + curated GEDCOM context`

3. **Centralize model config:**
   ```python
   # rhodesli_ml/config.py
   GEMINI_MODELS = {
       'combined_analysis': 'gemini-3.1-pro-preview',  # Best vision reasoning
       'date_estimation_bulk': 'gemini-3-flash-preview',  # Cost-effective bulk
       'testing': 'gemini-3-flash-preview',  # Free tier for dry-runs
   }
   ```
   Replace ALL hardcoded model strings in the codebase with config references.

4. **Log every call** through the `log_gemini_call` utility from Phase 1.

Tests:
- `test_combined_pipeline_includes_gedcom_context`
- `test_combined_pipeline_uses_configured_model`
- `test_model_config_no_hardcoded_strings`

AD entry: `AD-XXX: Combined Gemini pipeline (alignment + GEDCOM + extraction) using 3.1 Pro`

Commit: `feat(ml): combined Gemini pipeline with GEDCOM enrichment, centralized model config`

## Track B Phase 3: Process remaining photos

1. **Use Batch API if available and practical:**
   - Check if `gemini-3.1-pro-preview` supports Batch API
   - If yes: prepare JSONL file with remaining 144 photos, submit batch job
   - If no: use synchronous with delay between calls

2. **Prioritize GEDCOM-linked photos first:**
   ```python
   # Query photos that have GEDCOM face links but no alignment
   SELECT p.photo_id FROM photos p
   JOIN gedcom_face_links gfl ON p.photo_id = gfl.photo_id
   WHERE p.photo_id NOT IN (SELECT photo_id FROM face_gemini_alignments)
   ```

3. **Explicitly include the Vida Capeluto photo:**
   - Find her photo ID
   - Ensure it's in the batch
   - After processing: verify face count matches InsightFace detection
   - Document the PRD-015 motivating case result

4. **Rate limit handling:**
   - If 429 hit: log to gemini_api_calls with status='rate_limited' and rate_limit_type
   - Save progress (which photos completed)
   - Print: "Rate limited after N photos. Completed: [list]. Remaining: [count]. Re-run with --skip-processed"
   - Do NOT retry aggressively — move on to next phase

5. **Cost tracking:**
   - Print running total after every 10 photos
   - Compare actual cost to expected ($0.028/photo for Pro sync, $0.014 for batch)
   - If cost diverges significantly, STOP and investigate (may be using wrong model)

Tests:
- `test_batch_skips_already_processed`
- `test_batch_logs_every_api_call`
- `test_vida_capeluto_face_count`

Commit: `feat(ml): process remaining 144 photos with combined pipeline + Batch API`

## Track B Verification Gate

Re-read this prompt's Track B section. For each phase:
- [ ] Phase 1: gemini_api_calls table created, logging utility works
- [ ] Phase 2: Combined pipeline includes GEDCOM, model centralized, no hardcoded strings
- [ ] Phase 3: Photos processed (or rate-limited with progress saved), Vida Capeluto verified

Run full test suite:
```bash
pytest tests/ -x -q --ignore=tests/e2e/
pytest rhodesli_ml/tests/ -v
```

Merge Track B:
```bash
cd ../rhodesli  # main worktree
git merge session-64-track-b
git push origin main
```

# ═══════════════════════════════════════════════════════
# PHASE FINAL: DOCUMENTATION + DEPLOY VERIFY
# Back in main worktree
# ═══════════════════════════════════════════════════════

## Final Phase 1: Update documentation

1. **ALGORITHMIC_DECISIONS.md** — add all new AD entries from this session:
   - Gemini API call tracking
   - Combined pipeline with GEDCOM + 3.1 Pro
   - Face alignment migration to Supabase
   - Skills/hooks/rules harness architecture
   - Batch API usage decision

2. **ROADMAP.md** — update:
   - Mark completed items
   - DIFF against pre-session version
   - Confirm no items silently dropped
   - Print diff

3. **SESSION_HISTORY.md** — add Session 64 entry:
   - Duration
   - Phases completed
   - Test count
   - Key decisions
   - Outstanding items for Session 65

4. **BACKLOG.md** — update:
   - Remove completed items
   - Add any new items discovered during this session
   - DIFF against pre-session version

Commit: `docs: Session 64 documentation updates (AD, ROADMAP, SESSION_HISTORY, BACKLOG)`

## Final Phase 2: Deploy and verify production

Follow the `/skill:deploy-verify` protocol:

```bash
git push origin main
```

Wait for Railway deploy, then verify:
1. All routes return 200
2. Open a photo that has face alignment data → do face cards show?
3. Open compare view → do scores show as "85% match" calibrated probabilities?
4. Check the Vida Capeluto photo specifically → count correct?

If anything fails: fix, re-deploy, re-verify before ending session.

## Final Phase 3: Generate session assessment

Use the `/skill:assess-session` protocol on this session's own output.
Print the assessment. Include:
- Which of the 7 Session 63 concerns were resolved
- Which remain for Session 65
- Any new concerns discovered
- Recommended Session 65 priorities

Commit: `docs: Session 64 self-assessment`

# ═══════════════════════════════════════════════════════
# SUMMARY OF WHAT THIS SESSION DELIVERS
# ═══════════════════════════════════════════════════════
#
# Harness:
# - 5 skills (session-run, deploy-verify, ml-pipeline, assess-session, build-prompt)
# - 3 hooks (pre-commit tests, ML edit reminder, completion notification)
# - 3 rule files (ml-development, data-layer, session-protocol)
# - CLAUDE.md trimmed to <2000 chars
#
# Data:
# - Face alignment migrated JSON → Supabase
# - gemini_api_calls tracking table
# - Centralized Gemini model config (no hardcoded strings)
#
# ML:
# - Combined pipeline (alignment + GEDCOM + extraction in one call)
# - Remaining 144 photos processed (or progress saved if rate limited)
# - Vida Capeluto photo explicitly verified (PRD-015)
# - All API calls logged with model, cost, tokens, status
#
# UI:
# - Calibrated probability scores displayed
# - Per-face description cards from alignment data
# - Recalibration hooks wired into live endpoints
#
# Resolves all 7 Session 63 assessment concerns.
# ═══════════════════════════════════════════════════════
