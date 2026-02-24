# SESSION 65a — Upload Fix, Compare Overhaul, Prompt Fidelity, UX Polish
# Overnight autonomous prompt — run with --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2). This is a system where ML proposes hypotheses and humans adjudicate historical truth. Data loss is the cardinal sin.

Your mission this session: Fix critical upload breakage, overhaul Compare to beat FamilySearch, investigate whether 64d prompt data is actually rich, and polish sharing UX.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-65a-context.md
cat ROADMAP.md
head -60 docs/ALGORITHMIC_DECISIONS.md
```

## NON-NEGOTIABLE RULES
1. **Every prompt must mandate updating ALGORITHMIC_DECISIONS.md** with full decision provenance — accepted, rejected, why, source.
2. Commit after EVERY completed task: `fix(scope): desc` or `feat(scope): desc`
3. Run `pytest tests/ -x -q` before each commit. All must pass.
4. Use `head`, `grep`, `tail` — never cat entire large files into context.
5. Use `/clear` between phases (NOT /compact — /compact is lossy).
6. After /clear, re-read CLAUDE.md + this prompt's current phase section from disk.
7. Deploy via `git push origin main` (not Railway dashboard).
8. Session planning context file: `docs/session_context/session-65a-context.md`
9. No docs file >300 lines. ROADMAP.md must stay lean (<150 lines).
10. Log all work to SESSION_LOG.md as you go.

## CHECKPOINT & RESUME PROTOCOL

### When to checkpoint:
- Between phases (always)
- If context feels heavy
- If ANY test fails unexpectedly and you can't fix in 3 attempts

### How to checkpoint:
```bash
git add -A && git commit -m "wip: checkpoint before [reason]"
```

Write `SESSION_CHECKPOINT.md`:
```markdown
# Session 65a Checkpoint — [timestamp]
## Completed: Phase X
## Current state: [what's done, what's in progress]
## Next action: [exact next step]
## Tests: [passing count] / [total]
```

```bash
git add SESSION_CHECKPOINT.md && git commit -m "wip: session checkpoint" && git push
```

### On resume (if interrupted by usage limits):
```bash
cat SESSION_CHECKPOINT.md
# Continue from "Next action"
rm SESSION_CHECKPOINT.md
```

---

## PHASE 0 — ORIENT + QUICK FIXES (~8 min)

### 0A: Orient
```bash
cat CLAUDE.md
ls app/ core/ tests/ scripts/ docs/
cat ROADMAP.md
head -80 docs/ALGORITHMIC_DECISIONS.md
cat docs/session_context/session-65a-context.md
```

Write `SESSION_LOG.md`:
```markdown
# Session 65a Log
## Plan: Upload fix → Compare overhaul → Prompt fidelity → UX polish → Docs
## Started: [timestamp]
```

### 0B: Pre-commit Hook Regex Fix
In `.claude/settings.json`, the hook regex `^git commit` misses chained commands like `cd repo && git commit`.
Change to `\bgit commit\b` or equivalent.

### 0C: Verify 64d Production Data
Quick verification only — do NOT deep-dive yet:
```bash
# Check Supabase tables still have data
# Query gemini_alignments count — should be ~269
# Query gemini_api_calls count — should be ~156
# Check for duplicate entries
# Verify the 2 failing photos (Image 914, Image 018) don't error
```

If data looks fine, note in SESSION_LOG.md and move on.

### 0D: AD Update — Batch API Findings
Update AD-157 with actual 64d findings:
- Batch API was extremely slow (>20 min for 1 request)
- Sync pipeline completed 136 photos in 20 min
- Batch API not worth it for <200 photos, backup only for 500+

Commit: `fix: pre-commit hook regex, verify 64d data, update AD-157`
git push

---

## ⚠️ /clear AFTER PHASE 0
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65a-context.md`
Then read SESSION_LOG.md to see what Phase 0 completed.

---

## PHASE 1 — FIX UPLOADS (CRITICAL, ~25 min)

This is the #1 blocker. Uploads freeze at "Processing 0/1 (0%)" and never complete. A user dropped morris_mazal_ancestry_murry_army.jpeg and the progress bar stuck indefinitely.

### 1A: Diagnose (~10 min)

Investigate the upload pipeline end-to-end. Do NOT guess — read the code:

```bash
# Find the upload route handler
grep -rn "upload\|Upload" app/main.py | head -30
grep -rn "upload" app/ --include="*.py" | head -40

# Find the progress/SSE mechanism
grep -rn "sse\|SSE\|progress\|EventSource\|hx-trigger" app/ --include="*.py" | head -20
grep -rn "sse\|progress\|EventSource" app/ --include="*.html" | head -20

# Find where InsightFace / face detection runs during upload
grep -rn "insightface\|FaceAnalysis\|face_detection\|detect_faces" app/ core/ --include="*.py" | head -20

# Check for error handling in upload route
grep -rn "try\|except\|error\|Error" app/main.py | grep -i upload | head -20

# Check Railway logs if possible
# (May need to check Railway dashboard for recent error logs)
```

Document the root cause in SESSION_LOG.md before writing any fix.

### 1B: Fix (~12 min)

Based on diagnosis, fix the upload pipeline. Common patterns to check:
- **If timeout:** Make face detection async (queue for background processing, return upload success immediately)
- **If R2 failure:** Check credentials, bucket name, upload path
- **If SSE disconnect:** Ensure the EventSource connection stays alive, add reconnection logic
- **If OOM:** Defer InsightFace to background task, or load model lazily
- **If unhandled exception:** Add try/except, surface error to UI with clear message

Requirements for the fix:
- Single photo upload (JPG/PNG) must complete within 30 seconds
- Progress bar must show real progress OR a spinner with status text
- Errors must surface to the user (not silent freeze)
- After upload: photo appears in library
- Face detection can be deferred to background if needed for performance

### 1C: Test (~3 min)

Write or update tests:
```python
# Test: upload route accepts valid image
# Test: upload route rejects invalid file types
# Test: upload error surfaces to user (mock a failure)
# Test: upload with metadata (collection, source, source_url) saves correctly
```

```bash
pytest tests/ -x -q
```

Commit: `fix(upload): [description of root cause and fix]`
git push

### 1D: Smoke Test Production

After deploy, verify upload works:
```bash
# Use curl to test upload endpoint
curl -X POST https://rhodesli.nolanandrewfox.com/upload \
  -F "file=@test_image.jpg" \
  -F "collection=Test" \
  -F "source=Test" \
  -H "Cookie: [auth cookie if needed]"
```

Or use Playwright to automate the browser upload flow.
Document result in SESSION_LOG.md.

**AD entry:** AD-XXX: Upload pipeline fix — [root cause], [solution chosen], [alternatives considered].

---

## ⚠️ /clear AFTER PHASE 1
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65a-context.md`
Then read SESSION_LOG.md.

---

## PHASE 2 — COMPARE FACE OVERHAUL (~30 min)

The Compare page must support comparing faces between two photos. This is a core use case and a key portfolio feature. Target: beat FamilySearch's Compare-a-Face.

### 2A: Audit Current Compare (~5 min)
```bash
grep -rn "compare\|Compare" app/main.py | head -30
grep -rn "compare" app/ --include="*.py" | head -20
# Read the current compare route and template
```

Document what currently exists vs what's needed.

### 2B: Build Two-Photo Compare (~20 min)

**Required UX flow:**
1. User sees two side-by-side panels (Photo A / Photo B)
2. Each panel: upload a photo OR select from library (dropdown/search)
3. Faces auto-detected in both panels (show face bounding boxes)
4. User clicks a face in Panel A → highlighted
5. User clicks a face in Panel B → highlighted
6. System computes cosine similarity between the two InsightFace embeddings
7. Display result: side-by-side face crops, similarity score (0-100%), confidence label (Low/Medium/High/Very High based on calibrated thresholds)
8. "Compare another pair" button to reset selections
9. Show all detected faces in both photos so user can compare additional pairs

**Technical approach:**
- Face detection: use existing InsightFace pipeline
- Embedding comparison: cosine similarity on 512-dim embeddings
- Thresholds: use calibrated similarity thresholds from the kinship calibration work (check AD entries and `rhodesli_ml/` for calibrated cutoffs)
- For uploaded photos: detect faces server-side, return face crops + embeddings
- For library photos: faces already detected, pull from existing data

**Design notes:**
- Clean, modern layout — this is a portfolio showcase feature
- Side-by-side panels with clear visual hierarchy
- Similarity result should be prominent and easy to understand
- Include a brief explanation of what the score means
- Mobile-friendly: stack panels vertically on small screens

### 2C: Test
```python
# Test: compare route loads
# Test: face detection on uploaded image returns faces
# Test: similarity computation between two embeddings returns valid score
# Test: compare with library photos works
```

```bash
pytest tests/ -x -q
```

Commit: `feat(compare): two-photo face comparison with similarity scoring`
git push

**AD entry:** AD-XXX: Compare face overhaul — two-photo workflow, cosine similarity on InsightFace embeddings, calibrated thresholds from [source], FamilySearch as design reference.

---

## ⚠️ /clear AFTER PHASE 2
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65a-context.md`
Then read SESSION_LOG.md.

---

## PHASE 3 — PROMPT FIDELITY INVESTIGATION (~15 min)

We need to know if the 64d Gemini alignment prompts actually included rich context (GEDCOM + InsightFace coordinates) or if they were silently simplified.

### 3A: Pull API Call Records
```bash
# Connect to Supabase and pull 3 representative API calls
# 1 GEDCOM-enriched photo, 2 non-enriched
# For each: examine prompt_text, token counts, model_used
```

### 3B: Reconstruct Prompts
For the GEDCOM-enriched call:
- Does the prompt include full family context (names, birth years, relationships, residence)?
- Does it include InsightFace face coordinates (bounding boxes, landmarks)?
- Or is it a stripped-down "describe this photo" prompt?

For non-enriched calls:
- Do prompts include InsightFace coordinates?
- Or just the image with no metadata?

### 3C: Compare Token Counts
- GEDCOM-enriched calls should have noticeably higher input token counts
- If all calls have similar token counts (~1,640 input) → GEDCOM context isn't being included

### 3D: Verify Model
```sql
SELECT DISTINCT model_used FROM gemini_api_calls WHERE batch_id LIKE 'session-64d%';
```
Should be ONLY gemini-3.1-pro-preview.

### 3E: Document Findings

Write findings to `docs/analysis/prompt_fidelity_64d.md`:
- Were prompts rich or stripped?
- Token count comparison (enriched vs non-enriched)
- Model verification
- If stripped: what's missing and what needs fixing
- Impact assessment on the 269 alignments

**AD entry:** AD-XXX: Session 64d prompt fidelity audit — [findings]. Impact: [assessment].

Commit: `docs: prompt fidelity investigation for session 64d`
git push

---

## ⚠️ /clear AFTER PHASE 3
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65a-context.md`
Then read SESSION_LOG.md.

---

## PHASE 4 — UX QUICK WINS (~20 min)

Small improvements from the walkthrough that make the app more usable for sharing with community members.

### 4A: Face Overlay Toggle (~8 min)
On photo view pages, add a toggle button to show/hide face bounding box overlays. The overlays make it hard for community members to see the actual photo when looking closely.

- Add a button/toggle in the photo viewer toolbar: "Show/Hide Faces"
- Default: overlays ON for admin, OFF for non-admin visitors
- Use HTMX or vanilla JS to toggle CSS visibility
- Remember preference in localStorage (or just session-scoped)

### 4B: Share Link for People (~6 min)
On person pages (both identified and unidentified), add a "Copy Link" or "Share" button that copies the URL to clipboard. Currently, sharing an unidentified person requires manually typing their ID in the URL.

- Add a share/copy-link icon button on person cards
- On click: copy `https://rhodesli.nolanandrewfox.com/person/{id}` to clipboard
- Show brief "Copied!" toast/feedback
- Works for both identified (named) and unidentified people

### 4C: Cross-Page Navigation Consistency (~6 min)
Audit the main navigation paths and add missing links:
- From photo view → click a face → go to that person's page
- From person page → click a photo → go to that photo's view
- From collection → click a photo → go to that photo's view
- Ensure back/breadcrumb navigation is consistent

This is a quick pass — fix the most jarring gaps, don't redesign the whole nav.

### 4D: Test
```bash
pytest tests/ -x -q
```

Commit: `feat(ux): face overlay toggle, share links, navigation consistency`
git push

---

## ⚠️ /clear AFTER PHASE 4
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65a-context.md`
Then read SESSION_LOG.md.

---

## PHASE 5 — DOCS SYNC + SESSION CLOSE (~10 min)

### 5A: CHANGELOG.md
Add v0.65.1 (or appropriate version) entry:
- Upload pipeline fix
- Compare face two-photo overhaul
- Prompt fidelity investigation findings
- Face overlay toggle
- Share links for people
- Navigation improvements

### 5B: ROADMAP.md
Update to reflect:
- Session 65a completed items
- Update version number and test count
- Next planned sessions:
  - Session 65b: GEDCOM ↔ Identity linking UX (FE-041 extension)
  - Session 66: Alignment quality deep dive + portfolio documentation
  - Session 67: Similarity calibration (next ML milestone)

Keep ROADMAP.md under 150 lines.

### 5C: BACKLOG.md
Update with completed items and remaining work from walkthrough:
- Search on browse pages (Photos, Collections, People)
- Map location accuracy fixes (Asheville photo showing in Brooklyn)
- Map/Timeline/Tree page improvements
- GEDCOM loading scoping (filter to relevant branch)
- Chatbot layer (future — LangChain)
- Multi-community architecture (future)

### 5D: ALGORITHMIC_DECISIONS.md
Verify all AD entries from this session were logged with full provenance.
Each entry must have: decision, accepted/rejected, why, source, session breadcrumb.

### 5E: SESSION_HISTORY.md
Update with Session 65a summary.

### 5F: Final Verification Gate

```bash
echo "=== SESSION 65a VERIFICATION ==="

# Phase 1: Upload works
echo "Upload route exists:"
grep -c "upload" app/main.py

# Phase 2: Compare has two-photo flow
echo "Compare two-photo:"
grep -c "compare\|similarity\|cosine" app/main.py

# Phase 3: Prompt fidelity doc exists
ls docs/analysis/prompt_fidelity_64d.md

# Phase 4: Face overlay toggle
grep -c "overlay.*toggle\|toggle.*overlay\|show.*faces\|hide.*faces" app/main.py

# Phase 4: Share links
grep -c "share\|copy.*link\|clipboard" app/main.py

# All tests pass
pytest tests/ -x -q

echo "=== VERIFICATION COMPLETE ==="
```

Commit: `docs: session 65a changelog, ROADMAP, BACKLOG, AD sync`
git push

### 5G: Session Summary
Write final summary in SESSION_LOG.md:
```markdown
## Session 65a Complete
- Phases completed: [list]
- Commits: [count]
- Tests: [passing] / [total]
- Upload: [FIXED/NOT FIXED]
- Compare: [OVERHAULED/PARTIAL]
- Prompt fidelity: [FINDINGS]
- Deploy: [status]
```

---

## TOKEN EFFICIENCY REMINDERS
- Use `grep -n` to find code, not `cat` entire files
- Use `pytest tests/test_specific.py -x -q` during development, full suite only at phase end
- Don't re-read files already in context
- Between phases: /clear (NOT /compact), then re-read CLAUDE.md + context file + SESSION_LOG.md

## PARALLELIZATION NOTES
| Phase | Strategy | Why |
|-------|----------|-----|
| 0 Orient | Sequential | Must understand before acting |
| 1 Upload | Sequential | Critical fix, needs careful diagnosis |
| 2 Compare | Sequential | Complex new feature |
| 3 Prompt Fidelity | Sequential | Investigation, not code |
| 4 UX Wins | Can parallelize 4A/4B/4C | Independent UI changes |
| 5 Docs | Sequential | Depends on all prior work |

## BEGIN
Start with Phase 0. Read the mandatory files. Write SESSION_LOG.md. Execute.
