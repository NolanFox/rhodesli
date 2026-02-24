# SESSION 65d — Disk Space Fix, GEDCOM Versioning, Self-Improving Harness
# Overnight autonomous prompt — run with: claude --chrome --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2).

Three sessions have tried to fix upload. Each found a different root cause: 65a found subprocess issues, 65c found RAM exhaustion, and now we discover **the disk is full** (Errno 28: No space left on device). This session fixes the disk, verifies upload FOR REAL in the browser, builds GEDCOM versioning, and installs a self-improving evaluation harness so future sessions can't skip verification.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-65d-context.md
cat ROADMAP.md
cat SESSION_LOG.md 2>/dev/null || echo "No prior log"
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task.
2. `pytest tests/ -x -q` before each commit. All must pass.
3. Use `head`, `grep`, `tail` — never cat entire large files.
4. **Use /clear between phases. NEVER use /compact.** /compact is lossy and banned. After /clear, re-read CLAUDE.md + context file + SESSION_LOG.md.
5. Deploy via `git push origin main`.
6. Update ALGORITHMIC_DECISIONS.md with full provenance.
7. Context file: `docs/session_context/session-65d-context.md`
8. Log work to SESSION_LOG.md.
9. Screenshots to `docs/screenshots/session-65d/`.
10. Assessment file: `docs/assessments/session-65d-assessment.md` — MANDATORY.
11. **If you use /compact at any point, log it in the assessment as a RED FLAG with explanation.**

## BROWSER TESTING — USE CHROME PLUGIN
This session was launched with `--chrome`. You have access to the `browser` tool. Nolan is logged in as admin in Chrome.

**Use the browser tool for ALL production verification:**
- Navigate to URLs, take screenshots, interact with elements
- Upload files, click buttons, verify UI renders correctly
- Auth is solved — Chrome inherits Nolan's admin session

**Data safety:** Use synthetic test images (`_test_65d_delete_me.jpg`). Delete after verification.

## CHECKPOINT & RESUME
Between phases: commit, write SESSION_CHECKPOINT.md, push. On resume: read checkpoint, continue.

---

## PHASE 0 — ORIENT (~3 min)

```bash
cat CLAUDE.md
cat docs/session_context/session-65d-context.md
cat ROADMAP.md
```

Write SESSION_LOG.md:
```markdown
# Session 65d Log
## Mission: Fix disk space → verify upload in browser → GEDCOM versioning → self-improving harness
## Started: [timestamp]
## Context: Upload shows "Errno 28: No space left on device". Chrome plugin enabled.
## Rule: /clear between phases, NEVER /compact.
```

Commit: `docs: session 65d plan`

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 1 — FIX DISK SPACE + VERIFY UPLOAD IN BROWSER (~25 min)

### 1A: Diagnose Disk Usage (~5 min)

Figure out WHAT is consuming disk on Railway. This requires running commands in the production container or analyzing the Dockerfile/deployment.

```bash
# Check what's taking space locally (mirrors production)
du -sh ./* | sort -rh | head -20

# Find InsightFace model cache
find . -name "*.onnx" -size +10M 2>/dev/null | head -10
du -sh ~/.insightface/ 2>/dev/null
find /tmp -maxdepth 2 -size +1M 2>/dev/null | head -10

# Check if Dockerfile has proper cleanup
cat Dockerfile | head -60
cat .dockerignore 2>/dev/null

# Check for temp file accumulation in upload pipeline
grep -rn "tmp\|temp\|NamedTemporary\|mktemp\|tempfile" app/ core/ --include="*.py" | head -20

# Check for cleanup/finally blocks in upload
grep -rn "finally\|cleanup\|os.remove\|os.unlink\|shutil.rmtree" app/ core/ --include="*.py" | head -20

# Check Railway environment
grep -rn "INSIGHTFACE\|model.*path\|MODEL_DIR\|RAILWAY_VOLUME" app/ core/ --include="*.py" | head -10
```

Document in SESSION_LOG.md: what's consuming disk, how much.

### 1B: Fix Disk Space (~8 min)

**Required fixes:**

1. **Temp file cleanup in finally blocks:**
   - Every upload/processing function must clean temp files in a `finally` block
   - This means cleanup happens even if processing throws an exception

2. **InsightFace model cache control:**
   - Set `INSIGHTFACE_ROOT` environment variable to a controlled location
   - Ensure only ONE copy of model files exists
   - Add to Dockerfile or startup script: clean stale model downloads

3. **Startup cleanup script:**
   - Create `scripts/startup_cleanup.py` that runs when the app boots
   - Cleans: temp files older than 1 hour, duplicate model files, stale upload artifacts
   - Logs disk usage at startup: `df -h` equivalent

4. **Dockerfile optimization:**
   - Add/update `.dockerignore`: tests/, docs/, .git/, __pycache__/, *.pyc
   - Multi-stage build if not already (build deps in stage 1, runtime only in stage 2)
   - Clean pip cache in Dockerfile: `pip install --no-cache-dir`

5. **Railway volume:**
   - If using a volume: check if it needs to be grown (Railway dashboard → Volume → Grow)
   - Add a note in SESSION_LOG.md about current volume size and recommended size

6. **Disk space monitoring:**
   - Add a health check endpoint or startup log that reports available disk
   - Warn if available space < 200MB

```bash
pytest tests/ -x -q
```

Commit: `fix(infra): disk space cleanup — temp files, model cache, Dockerfile optimization`
git push

### 1C: Verify Upload in Browser (~8 min)

**Wait for Railway deploy to complete** (check deploy status).

**USE THE BROWSER TOOL:**

1. Generate test image:
   ```bash
   python3 -c "from PIL import Image; Image.new('RGB', (200, 200), 'blue').save('/tmp/_test_65d_upload.jpg')"
   ```

2. Navigate to `https://rhodesli.nolanandrewfox.com/upload`
3. Screenshot the page BEFORE upload
4. Fill in: Collection="TEST-DELETE", Source="TEST"
5. Upload the test image
6. **Watch the progress.** Screenshot during processing.
7. **Wait for completion.** Screenshot the result.
8. If it succeeds: screenshot the photo in the library. Then DELETE the test photo.
9. If it fails: read the error, diagnose, fix, redeploy, try again. Do not proceed until upload works.

**Test OTHER upload surfaces:**
10. Navigate to `/compare/pair`. Upload test image into Panel A. Screenshot.
11. Navigate to `/estimate`. Upload test image. Screenshot.

**Clean up ALL test data.** Screenshot library after cleanup.

### 1D: Log Results

```markdown
## Phase 1: Disk Space + Upload
- Disk usage before fix: [stats]
- Root cause: [what consumed disk]
- Fix applied: [temp cleanup, model cache, Dockerfile]
- /upload browser test: [PASS/FAIL — screenshot]
- /compare/pair browser test: [PASS/FAIL — screenshot]
- /estimate browser test: [PASS/FAIL — screenshot]
- Test data cleaned: [YES/NO]
```

**AD entry:** AD-XXX: Disk space root cause — [findings], [fix], Railway volume status. Upload now verified working in browser. Previous: 65a (PID tracking), 65c (RAM fix), 65d (disk space).

Commit: `docs: upload verification screenshots, disk space AD entry`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 2 — GEDCOM VERSIONING (~25 min)

Build the temporal versioning system for GEDCOM data so Nolan can re-import updated GEDCOMs without losing history.

### 2A: Schema Design (~5 min)

Read current GEDCOM tables:
```bash
grep -rn "gedcom\|GEDCOM" core/ app/ --include="*.py" | head -40
grep -rn "CREATE TABLE.*gedcom\|gedcom_individuals\|gedcom_events\|gedcom_relationships" core/ scripts/ --include="*.py" --include="*.sql" | head -20
```

Create migration for temporal versioning. Design documented in context file Part 2. Key tables:
- `gedcom_versions` — version metadata per import
- Add `version_id`, `superseded_by`, `is_current` to existing individual/event/relationship tables
- `gedcom_change_log` — field-level change tracking
- `current_gedcom_individuals` view — always shows latest state

### 2B: Import Pipeline (~12 min)

Build `scripts/import_gedcom_version.py` (or equivalent):

**Input:** New GEDCOM file path
**Output:** Version summary (N added, N modified, N removed, N unchanged)

Flow:
1. Parse new GEDCOM file (reuse existing parser)
2. Hash the file (SHA256) — skip if same hash as latest version
3. Create `gedcom_versions` entry
4. For each individual in new GEDCOM:
   - Match to existing by `xref_id`
   - If new: INSERT with `version_id`, `is_current=TRUE`
   - If modified: Mark old row `is_current=FALSE`, `superseded_by=new_id`. INSERT new row.
   - If unchanged: No action (preserve existing row)
   - If removed: Mark `is_current=FALSE` (soft delete, don't hard delete)
5. Log all changes to `gedcom_change_log`
6. Print summary

### 2C: Admin UI for GEDCOM Upload (~5 min)

Add a GEDCOM upload page at `/admin/gedcom` (admin-only):
- File upload for .ged files
- Show current GEDCOM version info (version N, imported date, individual count)
- After upload: show diff summary (N added, N modified, N removed)
- Show list of modified individuals with field-level changes
- "Apply" button to finalize (or "Cancel" to discard)

### 2D: Re-enrichment Queue (~3 min)

When individuals are modified in a GEDCOM update:
- Find their photos via `gedcom_face_links`
- Add those photos to a re-enrichment queue (NOT auto-run)
- Show count on admin dashboard: "N photos need re-enrichment due to GEDCOM update"
- Add `trigger` field to queue: 'gedcom_update' vs 'model_upgrade' vs 'manual_rerun'

### 2E: Tests

```python
# Test: import new GEDCOM creates version
# Test: re-import same GEDCOM (same hash) is no-op
# Test: modified individual creates new row, marks old superseded
# Test: removed individual soft-deleted (is_current=FALSE)
# Test: current_gedcom_individuals view only shows current
# Test: change_log records field-level changes
# Test: re-enrichment queue populated for modified individuals
```

```bash
pytest tests/ -x -q
```

Commit: `feat(gedcom): temporal versioning with change tracking and re-enrichment queue`
git push

**AD entry:** AD-XXX: GEDCOM temporal versioning — version chain per community, is_current flag for current state, superseded_by for history, change_log for field-level diffs. Gemini queries read current view only. Multi-community ready via community_id. Re-enrichment queued on data changes.

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 3 — SELF-IMPROVING HARNESS (~15 min)

Install infrastructure so post-session evaluation happens automatically and lessons are captured.

### 3A: Stop Hook for Evaluation (~8 min)

Create `.claude/hooks/post-session-eval.sh`:
```bash
#!/bin/bash
# Stop hook: runs when Claude Code finishes a session
# Triggers a subagent to evaluate work against the prompt

SESSION_ID=$(cat .claude/current_session.txt 2>/dev/null || echo "unknown")
echo "Running post-session evaluation for session $SESSION_ID..."

# Check if assessment already exists
if [ -f "docs/assessments/session-${SESSION_ID}-assessment.md" ]; then
  echo "Assessment already exists. Skipping."
  exit 0
fi

# Run evaluation
bash scripts/session_assessment.sh "$SESSION_ID"
echo "⚠️  Assessment file missing! Please run: bash scripts/session_assessment.sh $SESSION_ID"
```

Update `.claude/settings.json` to register the Stop hook:
```json
{
  "hooks": {
    "stop": ["bash .claude/hooks/post-session-eval.sh"]
  }
}
```

Create `.claude/current_session.txt` — updated at Phase 0 of each session with the session ID.

### 3B: Enhanced Evaluation Script (~4 min)

Upgrade `scripts/session_assessment.sh` (created in 65c) to:
1. Check mandatory outputs (assessment, session log, AD entries, changelog)
2. Check for /compact usage (grep git log for "compact" references)
3. Check for browser screenshots (if UX work was done)
4. Run test suite and report
5. Check git log for session commits
6. Output results to both console AND assessment file template
7. Return non-zero exit code if critical items missing

### 3C: CLAUDE.md Updates (~3 min)

Add to CLAUDE.md:

```markdown
## Mandatory Rules (enforced by hooks)
- /clear between phases. NEVER /compact. If /compact is used, log as RED FLAG in assessment.
- Assessment file (`docs/assessments/session-NNx-assessment.md`) is mandatory.
- Browser verification mandatory for all UX changes. Use --chrome flag. "Auth required" is not valid excuse.
- All evaluation results printed to console in final phase.
- Post-session evaluation hook runs automatically at session end.
- Set .claude/current_session.txt at session start.
```

Commit: `feat(harness): stop hook, enhanced eval script, CLAUDE.md enforcement rules`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 4 — DOCS SYNC (~5 min)

### 4A: CHANGELOG, ROADMAP, BACKLOG
- Add 65d entry: disk space fix, GEDCOM versioning, self-improving harness
- ROADMAP: update version, test count. Next: 66 (enrichment re-run + portfolio), 67 (similarity calibration), 68 (multi-community)
- BACKLOG: mark GEDCOM versioning as COMPLETE. Add: GEDCOM admin UI polish, re-enrichment experiment, Reflect-style skill system, Langfuse-style prompt scoring.
- Keep ROADMAP < 150 lines.

### 4B: AD Entries
Verify all decisions logged with full provenance.

Commit: `docs: session 65d changelog, ROADMAP, BACKLOG sync`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 5 — SELF-EVALUATION (MANDATORY) (~10 min)

### 5A: Re-read the prompt from context file
```bash
cat docs/session_context/session-65d-context.md
```

### 5B: Evaluate every phase — PASS/FAIL with evidence

```markdown
# Session 65d Assessment

## Evaluation Results

### Phase 0: Orient
- [ ] SESSION_LOG.md created
- [ ] .claude/current_session.txt set to "65d"

### Phase 1: Disk Space + Upload
- [ ] Disk usage diagnosed: [findings]
- [ ] Temp file cleanup in finally blocks: [files modified]
- [ ] InsightFace model cache controlled: [env var / path]
- [ ] Startup cleanup script created: [path]
- [ ] Dockerfile optimized: [changes]
- [ ] /upload verified in BROWSER with screenshot: [path]
- [ ] /compare/pair upload verified in BROWSER: [path]
- [ ] /estimate upload verified in BROWSER: [path]
- [ ] Test data cleaned up: [evidence]
- [ ] AD entry written: AD-XXX

### Phase 2: GEDCOM Versioning
- [ ] gedcom_versions table created
- [ ] Temporal columns added to existing tables
- [ ] gedcom_change_log table created
- [ ] current_gedcom_individuals view created
- [ ] Import pipeline script works
- [ ] Re-enrichment queue populated on changes
- [ ] Tests passing
- [ ] AD entry written: AD-XXX

### Phase 3: Self-Improving Harness
- [ ] Stop hook created and registered
- [ ] Evaluation script enhanced
- [ ] CLAUDE.md rules updated
- [ ] /compact ban documented

### Phase 4: Docs Sync
- [ ] CHANGELOG updated
- [ ] ROADMAP updated (< 150 lines)
- [ ] BACKLOG updated

### Context Window Management
- [ ] /clear used between ALL phases (not /compact)
- [ ] If /compact was used: [EXPLAIN WHY — RED FLAG]

## Fix-Ups Performed
[List anything that was FAIL and got fixed during evaluation]

## Deferred / Red Flags
[Anything that couldn't be resolved]

## Recommended Next Session Priorities
1. Run enrichment pipeline on 10-20 photos with first_order GEDCOM context
2. Retry 144 rate-limited photos from 64d
3. Portfolio documentation / ML pipeline writeup
4. Experiment: compare enriched vs bare Gemini results to quantify GEDCOM value
```

### 5C: Fix any FAILs right now

### 5D: Write assessment to file
```bash
# Write docs/assessments/session-65d-assessment.md
```

### 5E: Print to console
```bash
echo ""
echo "=============================================="
echo "SESSION 65d SELF-EVALUATION"
echo "=============================================="
cat docs/assessments/session-65d-assessment.md
echo "=============================================="
bash scripts/session_assessment.sh 65d
echo "=============================================="
```

Commit: `docs: session 65d assessment`
git push

---

## TOKEN EFFICIENCY
- `grep -n` not `cat`
- `pytest tests/test_specific.py -x -q` during dev
- /clear between phases, re-read from disk

## CRITICAL REMINDERS
- **Use --chrome browser tool.** Auth is solved via Chrome plugin.
- **DELETE test data** after every verification.
- **NEVER /compact.** Always /clear + re-read.
- **Assessment file is mandatory.** Phase 5 is not optional.
- **Print evaluation to console** so Nolan sees it.
- **Disk space fix MUST include finally-block cleanup** — not just one-time cleanup.

## BEGIN
Start with Phase 0. Read mandatory files. Set `.claude/current_session.txt` to "65d". Execute.
