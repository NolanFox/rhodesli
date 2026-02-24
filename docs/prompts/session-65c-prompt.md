# SESSION 65c — Upload Fix (MANDATORY), Verification Sweep, Harness Enforcement
# Overnight autonomous prompt — run with --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2).

Your #1 mission this session: **MAKE UPLOAD WORK IN PRODUCTION.** Upload has been broken since Feb 23. Two prior sessions (65a, 65b) failed to fix it. This is the single biggest blocker to the app being usable. You do not proceed past Phase 1 until upload is confirmed working with browser evidence.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-65c-context.md
cat ROADMAP.md
cat SESSION_LOG.md 2>/dev/null || echo "No prior log"
cat docs/analysis/prompt_fidelity_64d.md
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task: `fix(scope): desc` or `feat(scope): desc`
2. Run `pytest tests/ -x -q` before each commit. All must pass.
3. Use `head`, `grep`, `tail` — never cat entire large files into context.
4. Use `/clear` between phases (NOT /compact). After /clear, re-read CLAUDE.md + context file + SESSION_LOG.md.
5. Deploy via `git push origin main`.
6. Update ALGORITHMIC_DECISIONS.md with full provenance for every decision.
7. Session context file: `docs/session_context/session-65c-context.md`
8. Log all work to SESSION_LOG.md as you go.
9. Save all browser screenshots to `docs/screenshots/session-65c/`.
10. **Write `docs/assessments/session-65c-assessment.md` in Phase 5. This is mandatory. Do not skip.**

## BROWSER TESTING — MANDATORY TOOLING
**Primary: Use the Claude Chrome browser tool.** Nolan is logged in as admin in Chrome. The Chrome plugin inherits his session. This solves auth.

**If Chrome tool unavailable:** Fall back to Playwright. To handle auth:
- Export cookies from environment or use Supabase auth API to get session token
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are in environment — use them to authenticate programmatically
- DO NOT skip browser testing with "auth required" as an excuse. Solve it.

**Data safety:**
- Use synthetic test images only (e.g., solid blue 200x200 JPEG)
- Name: `_test_65c_delete_me_[N].jpg`
- After verification: DELETE all test data from app + R2
- Screenshot every step

## CHECKPOINT & RESUME PROTOCOL
```bash
# Between phases:
git add -A && git commit -m "wip: checkpoint before [reason]"
cat > SESSION_CHECKPOINT.md << 'EOF'
# Session 65c Checkpoint — [timestamp]
## Completed: Phase X
## Current state: [what's done]
## Next action: [exact next step]
## Tests: [passing] / [total]
EOF
git add SESSION_CHECKPOINT.md && git commit -m "wip: checkpoint" && git push
```
On resume: `cat SESSION_CHECKPOINT.md` → continue → `rm SESSION_CHECKPOINT.md`

---

## PHASE 0 — ORIENT (~5 min)

```bash
cat CLAUDE.md
cat docs/session_context/session-65c-context.md
ls app/ core/ tests/ scripts/ docs/
cat ROADMAP.md
```

Write `SESSION_LOG.md`:
```markdown
# Session 65c Log
## Mission: Fix upload (MANDATORY), verification sweep, harness enforcement
## Started: [timestamp]
## Rule: Phase 1 does not end until upload works in production with browser evidence.
```

Commit: `docs: session 65c plan`

---

## ⚠️ /clear AFTER PHASE 0
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65c-context.md && cat SESSION_LOG.md`

---

## PHASE 1 — FIX UPLOAD (MANDATORY — DO NOT PROCEED UNTIL WORKING) (~35 min)

**THIS PHASE IS THE ENTIRE POINT OF THIS SESSION.** Everything else is secondary. Upload has been "fixed" twice and still doesn't work. This time: diagnose → fix root cause → verify in production with browser → all upload surfaces.

### 1A: Deep Diagnosis (~10 min)

Do NOT read just the route handler. Read the ENTIRE upload pipeline end-to-end:

```bash
# 1. Find the upload route
grep -n "def.*upload\|@.*route.*upload\|post.*upload" app/main.py | head -20

# 2. Read the upload handler — FULL function, not just the signature
# (use view_range or head/tail to read the complete function)

# 3. Find what happens after file is received
grep -rn "ingest\|process.*photo\|detect.*face\|save.*photo" app/ core/ --include="*.py" | head -30

# 4. Find the subprocess that 65a added PID tracking for
grep -rn "subprocess\|Popen\|Process\|multiprocessing" app/ core/ --include="*.py" | head -20

# 5. Find R2 upload code
grep -rn "r2\|R2\|boto3\|s3.*client\|put_object\|upload_file" app/ core/ --include="*.py" | head -20

# 6. Find progress/SSE mechanism
grep -rn "sse\|SSE\|EventSource\|status_file\|write_status" app/ core/ --include="*.py" | head -20

# 7. Find the InsightFace model loading
grep -rn "FaceAnalysis\|insightface\|model.*load\|get_model" app/ core/ --include="*.py" | head -20

# 8. Check Railway container resources
grep -rn "memory\|Memory\|ram\|RAM\|oom\|OOM" Dockerfile Procfile railway.toml 2>/dev/null | head -10

# 9. Check recent Railway deploy logs if accessible
# (environment may have Railway CLI or API access)

# 10. Check error logs — what actually fails
grep -rn "logger\|logging\|log.*error\|traceback\|exception" app/ core/ --include="*.py" | grep -i "upload\|ingest\|process" | head -20
```

**Document in SESSION_LOG.md before writing any code:**
```markdown
## Phase 1A: Upload Diagnosis
### Upload pipeline steps:
1. [what happens first]
2. [what happens second]
...N. [what happens last]

### Root cause identified:
[SPECIFIC reason upload fails — not "subprocess dies" but WHY it dies]

### Evidence:
[code references, error messages, resource limits]
```

### 1B: Fix Root Cause (~10 min)

Based on diagnosis, fix the ACTUAL root cause. Common suspects:

**If InsightFace OOM on Railway:**
- Defer face detection to background task — return upload success immediately after R2 upload
- Or: load InsightFace model once at app startup (not per-request)
- Or: use a lighter model for initial detection, full model for batch processing

**If R2 upload fails:**
- Check credentials: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`
- Test R2 connection directly: `python -c "import boto3; ..."`
- Check if bucket exists and is writable

**If subprocess/process management issue:**
- Consider replacing subprocess with in-process async (avoid the PID tracking complexity entirely)
- If subprocess is needed: ensure it has access to all env vars and can reach R2/Supabase

**If file handling / path issue:**
- Check temp file paths in Railway container vs local dev
- Ensure uploaded file persists long enough for processing

**If timeout:**
- Split upload into two phases: (1) receive + store file in R2 (fast, <5 sec), (2) process faces (async, background)
- Return success after phase 1, show "processing" status that updates when phase 2 completes

**The fix MUST:**
- Handle errors gracefully (show error to user, not freeze)
- Work on Railway (not just locally)
- Complete within 30 seconds for a single photo
- Surface progress or status to the user

### 1C: Test Locally (~3 min)

```python
# Test: upload route accepts valid JPEG
# Test: upload route accepts valid PNG
# Test: upload rejects invalid file types (txt, exe)
# Test: upload with metadata (collection, source) saves correctly
# Test: upload error surfaces user-friendly message
# Test: upload timeout does not freeze UI
```

```bash
pytest tests/ -x -q
```

Commit: `fix(upload): [root cause] — [solution]`
git push

### 1D: Verify /upload in Production with Browser (~5 min)

**USE CLAUDE CHROME BROWSER TOOL.** You are logged in as admin.

1. Generate synthetic test image:
   ```bash
   python3 -c "
   from PIL import Image
   img = Image.new('RGB', (200, 200), color='blue')
   img.save('/tmp/_test_65c_upload_delete_me.jpg')
   "
   ```

2. Navigate to `https://rhodesli.nolanandrewfox.com/upload`
3. Screenshot the page (BEFORE upload)
4. Upload `_test_65c_upload_delete_me.jpg` with collection="TEST-DELETE-ME"
5. **Watch the progress bar.** Screenshot during processing.
6. **Wait for completion.** Screenshot the result.
7. Three outcomes:
   - **Completes successfully:** Screenshot. Proceed to 1E.
   - **Shows error message:** The error detection works. Read the error. Screenshot it. Fix the underlying issue. Re-deploy. Re-test. DO NOT proceed until it works.
   - **Freezes:** The fix didn't deploy or doesn't work. Check Railway deploy status. Check server logs. Fix. Re-test. DO NOT proceed until it works.

### 1E: Verify ALL Upload Surfaces (~5 min)

Upload exists in multiple places. Test each one:

1. **Find all upload surfaces:**
   ```bash
   grep -rn "upload\|file.*input\|drop.*zone\|multipart\|enctype" app/ --include="*.py" --include="*.html" | head -30
   ```

2. **Test /compare/pair upload:** Navigate to `https://rhodesli.nolanandrewfox.com/compare/pair`. Upload a test image into Panel A. Screenshot. Does face detection run?

3. **Test /estimate upload:** Navigate to `https://rhodesli.nolanandrewfox.com/estimate`. Upload a test image. Screenshot. Does it process?

4. **Any other upload surfaces:** Test each one found in step 1.

5. **If any upload surface uses a different code path** than /upload and is broken: fix it too.

### 1F: Clean Up Test Data

**MANDATORY — do not skip:**
```bash
# Delete test photo from app library
# Delete test photo from R2 storage
# Verify it's gone
```

Screenshot the library AFTER cleanup to confirm no test data remains.

### 1G: Log Results

```markdown
## Phase 1: Upload Fix
### Root cause: [specific cause]
### Fix applied: [specific fix]
### Production verification:
- /upload: [PASS/FAIL — screenshot path]
- /compare/pair upload: [PASS/FAIL — screenshot path]
- /estimate upload: [PASS/FAIL — screenshot path]
- Other surfaces: [list with results]
### Test data cleaned up: [YES/NO]
### AD entry: AD-XXX
```

**AD entry:** AD-XXX: Upload pipeline root cause and fix — [root cause], [fix], [alternatives considered], [production verification results]. Breadcrumb: Session 65c Phase 1. Previous attempts: 65a (PID tracking — symptom fix), 65b (skipped — auth excuse).

Commit: `docs: upload fix verification screenshots and session log`
git push

---

## ⚠️ /clear AFTER PHASE 1
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65c-context.md && cat SESSION_LOG.md`

---

## PHASE 2 — VERIFICATION SWEEP + REMAINING 65b GAPS (~15 min)

### 2A: GEDCOM Linking End-to-End Browser Test (~8 min)

65b built GEDCOM ↔ Identity linking but never browser-verified the full flow.

Using Chrome browser tool:
1. Navigate to a photo with an unidentified face
2. As admin, initiate the identify flow
3. Name the person (use a clearly fake test name like "Test Person 65c Delete Me")
4. **Verify the "Link to Family Tree" step appears**
5. **Verify GEDCOM search returns results** (search for a known name like "Capeluto")
6. **Verify "No match — skip" works**
7. Screenshot each step
8. **UNDO the test identification** — remove the fake name. Do not leave test data.

If the GEDCOM linking step doesn't appear or doesn't work: fix it, deploy, re-test.

### 2B: Enrichment Pipeline Sample Run (~7 min)

Run the fixed enrichment pipeline on a small sample to validate:

```bash
# Run 5 photos through the fixed pipeline (not 271 — just validation)
# Pick photos that have GEDCOM-linked individuals
# Verify:
# 1. GEDCOM context in prompt is 400-1000+ tokens (not 106)
# 2. gemini_config field is populated with enrichment_level, token count
# 3. response_summary field is populated
# 4. Gemini response references family context from GEDCOM

# If running against real API costs money, use --dry-run if available
# to verify prompt assembly without sending to Gemini
```

If a dry-run mode doesn't exist, create one:
```python
# Add --dry-run flag to pipeline that:
# 1. Assembles the full prompt (with GEDCOM enrichment)
# 2. Logs the prompt and token count
# 3. Does NOT call Gemini API
# 4. Saves the assembled prompt to a file for review
```

Log results: enrichment token counts per photo, enrichment_level distribution.

Commit: `test: GEDCOM linking browser verification + enrichment pipeline sample`
git push

---

## ⚠️ /clear AFTER PHASE 2
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65c-context.md && cat SESSION_LOG.md`

---

## PHASE 3 — HARNESS ENFORCEMENT (~15 min)

Fix the harness gaps so future sessions don't lose assessment files or skip verification.

### 3A: Add Assessment File Rule to CLAUDE.md (~3 min)

Add to CLAUDE.md (in the session management / rules section):

```markdown
## Mandatory Session Outputs
Every session MUST produce these files before the final commit:
1. `docs/assessments/session-NNx-assessment.md` — Self-evaluation of every phase
2. Updated `SESSION_LOG.md` — Running log of work performed
3. Updated `ALGORITHMIC_DECISIONS.md` — All decisions with provenance
4. Updated `CHANGELOG.md`, `ROADMAP.md`, `BACKLOG.md`

The assessment file is NOT optional. If context compaction occurs, re-read
this rule from CLAUDE.md and produce the assessment file.
```

### 3B: Create Prompt-Writing Template (~5 min)

Create `docs/templates/session-prompt-template.md`:

```markdown
# Session [NN][x] — [Title]
# [Overnight autonomous / Interactive] prompt

## Checklist for prompt authors (remove before running):
- [ ] Phases are small enough to fit in context (<30 min each)
- [ ] /clear mandated between every phase
- [ ] Browser verification mandated for all UX changes (Chrome plugin primary, Playwright fallback)
- [ ] Data safety rules included for any production testing
- [ ] Assessment file mandated in final phase
- [ ] Self-evaluation phase with visible console output
- [ ] AD entries required for all decisions
- [ ] Session context file referenced
- [ ] CHECKPOINT protocol included for overnight runs

## Template structure:
[Include the standard sections: ROLE, READ FIRST, NON-NEGOTIABLE RULES,
BROWSER TESTING, CHECKPOINT, then PHASES, then SELF-EVALUATION]
```

Fill in the template with our actual patterns from sessions 65a/65b/65c. This becomes the reference for future prompt writing.

### 3C: Create Self-Evaluation Script (~5 min)

Create `scripts/session_assessment.sh` that can be run at session end:

```bash
#!/bin/bash
# Session self-evaluation helper
# Usage: bash scripts/session_assessment.sh <session-id> <prompt-file>

SESSION_ID=$1
PROMPT_FILE=$2

echo "=== SESSION $SESSION_ID SELF-EVALUATION ==="
echo ""

# Check mandatory outputs exist
echo "--- Mandatory Outputs ---"
[ -f "docs/assessments/session-${SESSION_ID}-assessment.md" ] && echo "✅ Assessment file" || echo "❌ Assessment file MISSING"
[ -f "SESSION_LOG.md" ] && echo "✅ Session log" || echo "❌ Session log MISSING"
echo ""

# Check screenshots exist (if UX work was done)
SCREENSHOT_DIR="docs/screenshots/session-${SESSION_ID}"
if [ -d "$SCREENSHOT_DIR" ]; then
    COUNT=$(ls "$SCREENSHOT_DIR" | wc -l)
    echo "✅ Screenshots: $COUNT files in $SCREENSHOT_DIR"
else
    echo "⚠️  No screenshots directory (OK if no UX work)"
fi
echo ""

# Run tests
echo "--- Test Suite ---"
pytest tests/ -x -q 2>&1 | tail -5
echo ""

# Check recent commits
echo "--- Commits This Session ---"
git log --oneline -10
echo ""

echo "=== END EVALUATION ==="
```

### 3D: Add CLAUDE.md Rule for Browser Verification

Add to CLAUDE.md:

```markdown
## Browser Verification Rule
All UX changes MUST be verified in the production browser before the session ends.
- Primary tool: Claude Chrome browser plugin (Nolan is logged in as admin)
- Fallback: Playwright with programmatic auth via Supabase API
- "Auth required" is NOT a valid reason to skip browser verification
- Screenshots saved to docs/screenshots/session-NNx/
```

Commit: `feat(harness): assessment mandate, prompt template, evaluation script, browser verification rule`
git push

---

## ⚠️ /clear AFTER PHASE 3
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65c-context.md && cat SESSION_LOG.md`

---

## PHASE 4 — DOCS SYNC (~5 min)

### 4A: CHANGELOG.md
Add session 65c entry:
- Upload pipeline: root cause identified and fixed, verified in production
- All upload surfaces tested (upload, compare, estimate)
- GEDCOM linking: browser-verified end-to-end
- Enrichment pipeline: sample run validated
- Harness: assessment mandate, prompt template, evaluation script, browser verification rule

### 4B: ROADMAP.md
Update version, test count, completed items. Plan:
- Session 66: Re-run enriched pipeline (full 271 photos), alignment quality deep dive, portfolio docs
- Session 67: Similarity calibration
- Session 68: Multi-community architecture
Keep under 150 lines.

### 4C: BACKLOG.md
Update completed/remaining items.

### 4D: ALGORITHMIC_DECISIONS.md
Verify all AD entries have full provenance.

Commit: `docs: session 65c changelog, ROADMAP, BACKLOG sync`
git push

---

## ⚠️ /clear AFTER PHASE 4
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65c-context.md && cat SESSION_LOG.md`

---

## PHASE 5 — SELF-EVALUATION (MANDATORY — DO NOT SKIP) (~10 min)

This is not optional. This phase exists because previous sessions skipped evaluation.

### 5A: Re-Read the Prompt
```bash
cat docs/session_context/session-65c-context.md
```
Or re-read this prompt from disk if saved to `docs/prompts/`.

### 5B: Evaluate Every Phase

For EACH phase, check against what was promised vs what was delivered:

```markdown
## Self-Evaluation Results

### Phase 0: Orient
- [PASS/FAIL] Session log created
- [PASS/FAIL] Context file read

### Phase 1: Upload Fix
- [PASS/FAIL] Root cause identified: [what was it?]
- [PASS/FAIL] Fix applied and deployed
- [PASS/FAIL] /upload verified in production with screenshot: [path]
- [PASS/FAIL] /compare/pair upload verified: [path]
- [PASS/FAIL] /estimate upload verified: [path]
- [PASS/FAIL] Test data cleaned up
- [PASS/FAIL] AD entry written

### Phase 2: Verification Sweep
- [PASS/FAIL] GEDCOM linking browser-tested end-to-end: [path]
- [PASS/FAIL] Enrichment pipeline sample run: [token counts]
- [PASS/FAIL] Test data cleaned up

### Phase 3: Harness Enforcement
- [PASS/FAIL] Assessment mandate in CLAUDE.md
- [PASS/FAIL] Prompt template created
- [PASS/FAIL] Evaluation script created
- [PASS/FAIL] Browser verification rule in CLAUDE.md

### Phase 4: Docs Sync
- [PASS/FAIL] CHANGELOG updated
- [PASS/FAIL] ROADMAP updated (<150 lines)
- [PASS/FAIL] BACKLOG updated
- [PASS/FAIL] AD entries complete
```

### 5C: Fix Any Failures

**If any item is FAIL or PARTIAL:**
1. Attempt to fix it NOW (apply the same standards: small fix, test, commit, verify)
2. Re-evaluate after fix
3. Document the fix-up in the assessment

**If a fix requires browser verification you cannot do:** Note it as "DEFERRED — requires manual verification" and explain exactly what to check.

### 5D: Write Assessment File

Write `docs/assessments/session-65c-assessment.md` with:

```markdown
# Session 65c Assessment

## Shipped
- [x/partial/fail] Phase 0: [description] — Evidence: [file/screenshot]
- [x/partial/fail] Phase 1: [description] — Evidence: [file/screenshot]
- [x/partial/fail] Phase 2: [description] — Evidence: [file/screenshot]
- [x/partial/fail] Phase 3: [description] — Evidence: [file/screenshot]
- [x/partial/fail] Phase 4: [description] — Evidence: [file/screenshot]

## Fix-Ups Performed During Evaluation
- [list any items that were FAIL/PARTIAL and got fixed in 5C]

## Deferred / Red Flags
- [anything that couldn't be resolved]

## Recommended Next Session Priorities
1. [highest priority]
2. [second priority]
3. [third priority]

## Stats
- Tests: [count] ([new] new)
- Commits: [count]
- Screenshots: [count] in docs/screenshots/session-65c/
- Version: v0.XX.0
```

### 5E: Print Evaluation to Console

**MANDATORY — the evaluation must be visible in the console output, not just in the file:**

```bash
echo ""
echo "=============================================="
echo "SESSION 65c SELF-EVALUATION RESULTS"
echo "=============================================="
cat docs/assessments/session-65c-assessment.md
echo ""
echo "=============================================="
echo "Run scripts/session_assessment.sh for automated checks:"
bash scripts/session_assessment.sh 65c
echo "=============================================="
```

Commit: `docs: session 65c assessment`
git push

---

## TOKEN EFFICIENCY
- `grep -n` to find code, not `cat` entire files
- `pytest tests/test_specific.py -x -q` during dev, full suite at phase end
- /clear between phases, re-read CLAUDE.md + context + log

## PARALLELIZATION
| Phase | Strategy | Why |
|-------|----------|-----|
| 0 Orient | Sequential | Setup |
| 1 Upload | Sequential, BLOCKING | Must complete before anything else |
| 2 Verify | Sequential | Browser automation |
| 3 Harness | Sequential | File creation |
| 4 Docs | Sequential | Depends on prior work |
| 5 Eval | Sequential | Depends on ALL prior work |

## CRITICAL REMINDERS
- **Phase 1 is BLOCKING.** Do not move to Phase 2 until upload works in production with browser screenshot evidence.
- **Use Claude Chrome browser tool.** Nolan is logged in as admin. Auth is solved.
- **Delete all test data** after verification.
- **Write the assessment file.** Phase 5 is mandatory.
- **Print evaluation to console.** So Nolan can verify at a glance.

## BEGIN
Start with Phase 0. Read the mandatory files. Write SESSION_LOG.md. Execute.
