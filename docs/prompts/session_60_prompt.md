# Session 60: Gemini Progressive Refinement + Upload UX + Admin Unification

Read CLAUDE.md. Read .claude/rules/spec-driven-development.md.
Read .claude/rules/verification-gate.md.
Read .claude/rules/feature-reality-contract.md.
Read .claude/rules/harness-decisions.md.
Read .claude/rules/prompt-decomposition.md.
Read .claude/rules/phase-execution.md.
Read CHANGELOG.md (first 10 lines).
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines for recent ADs).
Read BACKLOG.md.
Read ROADMAP.md.
Read docs/session_context/session_60_planning_context.md.

## Session Identity
- **Previous session:** Session 59C (Supabase dual-write migration)
- **Goal:** Three tracks combined for efficiency:
  1. ACT 1 — Gemini progressive refinement ML pipeline
  2. ACT 2 — Upload UX with SSE progressive loading
  3. ACT 3 — Admin/public UX unification + quick-identify
- **Time budget:** ~90 min autonomous (overnight run)
- **Mode:** Fully autonomous. `--dangerously-skip-permissions`.
  DO NOT STOP until all phases attempted. Failures → log + continue.

## ⚠️ CONTEXT MANAGEMENT — CRITICAL FOR OVERNIGHT RUN

This prompt has 3 acts and 15+ phases. Context degradation has
caused failures in Sessions 47, 49C, and others. Follow these rules
WITHOUT EXCEPTION:

1. **Save this prompt** to `docs/prompts/session_60_prompt.md`
2. **Create session log** at `docs/session_logs/session_60_log.md`:
   ```
   # Session 60 Log
   Started: [timestamp]
   
   ## ACT 1: ML — Gemini Progressive Refinement
   - [ ] Phase 0: Orient
   - [ ] Phase 1A: Gemini config centralization
   - [ ] Phase 1B: API logging infrastructure  
   - [ ] Phase 1C: Progressive refinement script
   - [ ] Phase 1D: Evaluation + dry-run test
   
   ## ACT 2: UX — Upload SSE
   - [ ] Phase 2A: SSE endpoint for upload processing
   - [ ] Phase 2B: Progressive UI components
   - [ ] Phase 2C: Error handling + edge cases
   - [ ] Phase 2D: Visual verification
   
   ## ACT 3: UX — Admin/Public Unification
   - [ ] Phase 3A: Admin bar component
   - [ ] Phase 3B: Quick-identify inline flow
   - [ ] Phase 3C: Public-first verification
   - [ ] Phase 3D: Visual verification (mobile + desktop)
   
   ## Wrap-Up
   - [ ] Phase 4A: ROADMAP + BACKLOG sync
   - [ ] Phase 4B: Verification gate
   - [ ] Phase 4C: Final docs + changelog
   ```

3. **After EVERY phase:**
   - Update session log: `- [x] Phase NN: [what was actually done]`
   - Run `pytest tests/ -x -q` — record pass count
   - `git add -A && git commit -m "session 60 phase NN: [description]"`
   - Check context: if above 50%, run `/compact`
   - Re-read ONLY the next phase section from the prompt file

4. **Between acts:** Run `/compact` unconditionally. Acts are
   independent — fresh context for each.

5. **If auto-compact fires mid-phase:**
   - Read `docs/session_logs/session_60_log.md`
   - Read the specific phase section from `docs/prompts/session_60_prompt.md`
   - Continue from last committed state. Do not re-do completed phases.

6. **Each phase must be ≤8 minutes.** If it takes longer, you're
   doing too much — split and commit what you have.

---

# ══════════════════════════════════════════
# PHASE 0: ORIENT (5 min)
# ══════════════════════════════════════════

```bash
head -80 CLAUDE.md
ls .claude/rules/ && for f in .claude/rules/*; do head -10 "$f"; done
git log --oneline -10
head -30 CHANGELOG.md
head -50 ROADMAP.md
pytest tests/ -x -q 2>&1 | tail -5
```

Record baseline: version, test count, git status.

Check if Chrome Extension is available for browser testing:
```bash
# Try Chrome Extension first
which chrome-extension 2>/dev/null || echo "Chrome Extension not available"
```

If Chrome Extension unavailable, set up Playwright:
```bash
pip install playwright --break-system-packages 2>/dev/null
playwright install chromium 2>/dev/null
```

Save this prompt to `docs/prompts/session_60_prompt.md`.
Create session log at `docs/session_logs/session_60_log.md`.
Save context file to `docs/session_context/session_60_planning_context.md`
(copy from the file already read above).

Commit: `docs: session 60 orientation — baseline recorded`
Update session log. `/compact` if above 50%.

---

# ══════════════════════════════════════════
# ACT 1: ML — GEMINI PROGRESSIVE REFINEMENT
# ══════════════════════════════════════════

Re-read Phase 1A from `docs/prompts/session_60_prompt.md`.
Read `docs/session_context/session_60_planning_context.md` ACT 1 section.

## PHASE 1A: Gemini Config Centralization (5 min)

Find ALL Gemini model references:
```bash
grep -rn "gemini-\|gemini_model\|GEMINI_MODEL\|google.genai\|genai" \
  --include="*.py" --include="*.md" --include="*.json" \
  --include="*.env*" --include="*.toml" \
  . | grep -v node_modules | grep -v __pycache__ | grep -v ".git/" \
  | grep -v session_context | grep -v prompts
```

Create or update centralized config:
```python
# rhodesli_ml/config.py
import os

# Gemini model configuration — single source of truth
# See AD-XXX for model selection rationale
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-preview-05-06")
# Note: Check google.genai for latest available model string
# Prefer the most capable Pro model for vision tasks
# Evidence quality is the UX differentiator — don't compromise

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Cost controls
MAX_COST_DEFAULT = 1.00  # USD, for dry runs
DRY_RUN_PHOTO_LIMIT = 3

# media_resolution options: "low" (fewer tokens) or "high" (more detail)
MEDIA_RESOLUTION = "high"
```

Replace ALL hardcoded model strings across the codebase with imports
from this config. Remove any deprecated model references (gemini-2.0-flash,
gemini-1.5, etc).

**Tests:** Add test for config loading, env var override.

Commit: `feat(ml): centralize Gemini config — single model source of truth`
Update session log. `/compact` if above 50%.

---

## PHASE 1B: API Logging Infrastructure (8 min)

Re-read Phase 1B from the prompt file.

Create `rhodesli_ml/utils/api_logger.py`:

Purpose: Log ALL Gemini API calls for analysis. Every call gets:
- Timestamp
- Model version  
- Full prompt (or hash if too large)
- Full response
- Input/output token count
- Cost estimate
- Input context (which verified facts were provided)
- Comparison to previous result (if re-analysis)
- Photo ID being analyzed

Storage: `rhodesli_ml/data/api_logs/` directory, one JSON file per call.
Naming: `{timestamp}_{photo_id}_{model}.json`

Also create analysis utilities:
- `rhodesli_ml/scripts/analyze_api_logs.py` — summary stats,
  cost tracking, before/after comparison for re-analyses

Add AD entry to ALGORITHMIC_DECISIONS.md:
```
## AD-XXX: API Result Logging for Progressive Refinement

### Problem
Need systematic tracking of all Gemini API calls to:
1. Compare before/after when re-analyzing with verified facts
2. Track costs across model versions
3. Build analytical dataset for which facts improve estimates most

### Decision
Log every API call to rhodesli_ml/data/api_logs/ as JSON.
Include full prompt, response, token counts, cost, and diff
against previous analysis for same photo.

### Breadcrumbs
- Session 50 Phase 4C: architecture documented
- Session 60 Phase 1B: implementation
- Planning context: docs/session_context/session_60_planning_context.md
```

**Tests:** Test logger writes correctly, test log parsing, test
cost calculation.

Commit: `feat(ml): API logging infrastructure for Gemini calls`
Update session log. `/compact` if above 50%.

---

## PHASE 1C: Progressive Refinement Script (8 min)

Re-read Phase 1C from the prompt file.

Create `rhodesli_ml/scripts/progressive_refinement.py`:

This is the core ML feature. When verified facts exist for a photo,
re-run Gemini with enriched context and compare to previous results.

```python
"""
Progressive Refinement: Re-analyze photos with verified facts.

Usage:
  python -m rhodesli_ml.scripts.progressive_refinement --dry-run
  python -m rhodesli_ml.scripts.progressive_refinement --photo-id P001
  python -m rhodesli_ml.scripts.progressive_refinement --all --max-cost 5.00
"""
```

Key components:
1. **Fact gatherer:** For a given photo, collect all verified facts:
   - Confirmed identities (name, birth year if known)
   - Confirmed date or date range
   - Confirmed location
   - GEDCOM relationships between identified people
   - Previous Gemini analysis (for comparison)

2. **Enriched prompt builder:** Construct prompt that includes:
   - The photo
   - All verified facts as structured context
   - Instruction to provide updated analysis
   - Request for: date estimate, per-face descriptions,
     location analysis, confidence levels
   - Decade probabilities (probability mass over all decades)
   - Cultural context instruction: "Rhodes diaspora fashion
     lagged 5-15 years behind mainstream European/American trends"

3. **Combined analysis:** Single API call for date + faces + location.
   Cross-referencing evidence produces better results.

4. **Comparison engine:** Diff old vs new analysis, highlight
   what changed and why (which facts drove the change).

5. **Gatekeeper integration:** Results go to proposals system,
   not directly to production data. Admin reviews before accepting.

6. **Safety:** `--dry-run` (3 photos then stop), `--max-cost` flag,
   GEMINI_API_KEY env check, graceful exit with setup instructions
   if key missing.

DO NOT call Gemini API in this session. Build the pipeline, test
with mocked responses. Real API calls happen when Nolan confirms.

**Tests:** Test fact gathering, prompt building, comparison engine,
dry-run limits, missing API key handling. Use mocked API responses.

Commit: `feat(ml): progressive refinement pipeline — fact-enriched re-analysis`
Update session log. `/compact` if above 50%.

---

## PHASE 1D: Evaluation + Dry-Run Verification (5 min)

Re-read Phase 1D from the prompt file.

Create `rhodesli_ml/scripts/gemini_eval.py` (or update existing):

Purpose: Evaluate improvement from progressive refinement.
- Select photos with the most verified facts
- Show what the enriched prompt would look like
- Compare to existing date estimates
- Output: "Photo P001: old estimate 1920s, new context includes
  3 confirmed identities with known birth years"

Run the dry-run to verify the pipeline works end-to-end (mocked):
```bash
python -m rhodesli_ml.scripts.progressive_refinement --dry-run --mock
```

Verify:
- Pipeline runs without errors
- API logger captures the mocked call
- Comparison engine produces sensible diff
- Cost estimator reports expected cost
- Gatekeeper proposals would be created correctly

**Tests:** Integration test for full pipeline with mocked API.

Commit: `test(ml): progressive refinement dry-run verification`
Update session log. 

---

# ═══════════════════════════════════════════════
# ACT TRANSITION: ML → UX
# ═══════════════════════════════════════════════

Run `/compact` unconditionally. ACT 1 is complete.
Re-read session log to confirm all Phase 1 items checked off.
Re-read the ACT 2 section from `docs/prompts/session_60_prompt.md`.

---

# ══════════════════════════════════════════
# ACT 2: UX — UPLOAD SSE PROGRESSIVE LOADING
# ══════════════════════════════════════════

## PHASE 2A: SSE Endpoint for Upload Processing (8 min)

Re-read Phase 2A from the prompt file.

Check existing upload/compare routes:
```bash
grep -n "upload\|compare\|facecompare\|stream\|sse\|event-stream" \
  app/main.py | head -30
```

Build an SSE endpoint that streams upload processing progress.
The endpoint receives the uploaded photo and returns Server-Sent
Events as each processing stage completes:

```
Stage 1: "Detecting faces..." → "Found N faces" (with face count)
Stage 2: "Generating embeddings..." → "Comparing to archive"
Stage 3: "Searching for matches..." → "N potential matches found"
Stage 4: "Estimating date..." → "Circa 19XX"
Stage 5: "Complete" → full results payload
```

Implementation approach:
- New route: `/api/upload/stream` (POST, returns text/event-stream)
- Each stage yields an SSE event with structured JSON data
- Existing processing logic wrapped in async generator
- Error events for failures at any stage
- Timeout handling (max 60 seconds)

Ensure this works for BOTH `/compare` and `/facecompare` flows.
The SSE endpoint is shared; the UI components differ.

**Tests:** Test SSE endpoint returns correct content-type, test
each stage event is emitted, test error handling, test timeout.

Commit: `feat(ux): SSE endpoint for progressive upload processing`
Update session log. `/compact` if above 50%.

---

## PHASE 2B: Progressive UI Components (8 min)

Re-read Phase 2B from the prompt file.

Build the client-side UI that connects to the SSE endpoint:

Using HTMX SSE extension:
```html
<!-- Include SSE extension -->
<script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>

<!-- Upload form triggers SSE connection -->
<form hx-post="/api/upload/stream" 
      hx-ext="sse"
      hx-target="#results">
  <input type="file" name="photo" accept="image/*">
  <button type="submit">Analyze Photo</button>
</form>

<!-- Progressive results area -->
<div id="results">
  <!-- Stage indicators appear here progressively -->
</div>
```

Each stage should show:
- Animated indicator (spinner/pulse) for current stage
- ✓ checkmark for completed stages
- Face count badge when detection completes
- Match cards appearing one by one as found
- Date estimate with confidence when available
- Error state with retry option if any stage fails

Mobile-first: all touch targets ≥44px, readable on 375px viewport.

**Tests:** Test that UI components render correctly, test HTMX
attributes are properly set, test mobile viewport sizing.

Commit: `feat(ux): progressive upload UI with SSE — stage indicators`
Update session log. `/compact` if above 50%.

---

## PHASE 2C: Error Handling + Edge Cases (5 min)

Re-read Phase 2C from the prompt file.

Handle these edge cases:
- No face detected in uploaded photo → friendly message + suggestions
- Photo too large (>10MB) → client-side validation before upload
- Invalid file type → client-side + server-side validation
- SSE connection drops → reconnection logic or fallback
- Multiple faces detected → face selector (existing from Session 32)
- Server timeout → "Processing is taking longer than expected"
- API key missing → degrade gracefully (skip Gemini stages)

Each error must show a clear, actionable message to the user.
Never show raw error text or empty states.

**Tests:** Test each error case produces correct error event.

Commit: `feat(ux): upload error handling — all edge cases covered`
Update session log. `/compact` if above 50%.

---

## PHASE 2D: Visual Verification (5 min)

Re-read Phase 2D from the prompt file.

Use Chrome Extension (preferred) or Playwright to verify:

1. Navigate to `/compare` (or `/facecompare`)
2. Upload a test photo
3. Screenshot the progressive loading experience
4. Verify each stage indicator appears
5. Screenshot on mobile viewport (375px)
6. Look at the screenshots — note any visual issues

```python
# Playwright fallback
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    # Desktop viewport
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://localhost:PORT/facecompare")
    page.screenshot(path="/tmp/s60_upload_desktop.png")
    
    # Mobile viewport
    page = browser.new_page(viewport={"width": 375, "height": 812})
    page.goto("http://localhost:PORT/facecompare")
    page.screenshot(path="/tmp/s60_upload_mobile.png")
    
    browser.close()
```

Review screenshots. Add any visual issues to UX_ISSUE_TRACKER.md.
Log results in session log.

Commit: `test(ux): visual verification — upload SSE flow`
Update session log.

---

# ═══════════════════════════════════════════════
# ACT TRANSITION: Upload UX → Admin Unification
# ═══════════════════════════════════════════════

Run `/compact` unconditionally. ACT 2 is complete.
Re-read session log. Re-read ACT 3 from prompt file.

---

# ══════════════════════════════════════════
# ACT 3: UX — ADMIN/PUBLIC UNIFICATION
# ══════════════════════════════════════════

## PHASE 3A: Admin Bar Component (8 min)

Re-read Phase 3A from the prompt file.

Check current admin detection:
```bash
grep -n "admin\|is_admin\|require_auth\|ADMIN_EMAILS" app/main.py | head -20
```

Build an admin bar that appears at the top of every page when
the user is authenticated as admin:

```html
<!-- Admin bar — only rendered for admin users -->
<div class="admin-bar" style="
  background: #1a1a2e; 
  padding: 8px 16px; 
  display: flex; 
  align-items: center;
  border-bottom: 1px solid #333;
  font-size: 13px;
  color: #aaa;
">
  <span>🔧 Admin Mode</span>
  <span style="margin-left: auto;">
    <a href="/admin/pending">Pending (N)</a> |
    <a href="/admin/proposals">Proposals (N)</a> |
    Quick Actions ▾
  </span>
</div>
```

Requirements:
- Shows pending upload count and proposal count
- Links to admin sections
- Never visible to non-admin users
- Does not affect page layout or push content down excessively
- Dark theme consistent with existing design

**Tests:** Test admin bar renders for admin, hidden for public,
counts are accurate.

Commit: `feat(ux): admin bar — mode indicator with quick actions`
Update session log. `/compact` if above 50%.

---

## PHASE 3B: Quick-Identify Inline Flow (8 min)

Re-read Phase 3B from the prompt file.

This is the #1 community-driven UX request. Currently, identifying
a face requires navigating to the face's identify page. This makes
entering 8 names take 15 minutes instead of 2.

Build inline identification on photo pages and person pages:

1. **On photo pages (admin only):**
   - Each face overlay or face card gets a small "✏️ ID" button
   - Clicking opens an inline text input + submit
   - User types name → submit → HTMX POST to identify endpoint
   - Success: face card updates with name, no page reload
   - Auto-suggest from existing confirmed identities

2. **On person pages (admin only):**
   - "Add name" or "Correct name" inline

3. **On face cards in any context (admin only):**
   - Hover/tap reveals "Identify" option
   - Same inline flow

Implementation: HTMX swap patterns. No full page reloads.

```html
<!-- Face card with inline identify -->
<div class="face-card" id="face-{face_id}">
  <img src="{crop_url}" />
  <span class="face-name">{name or 'Unknown'}</span>
  <!-- Admin only: -->
  <button hx-get="/admin/identify-form/{face_id}" 
          hx-target="#face-{face_id} .identify-area"
          hx-swap="innerHTML"
          class="admin-only">✏️</button>
  <div class="identify-area"></div>
</div>
```

**Tests:** Test identify form renders for admin, hidden for public,
test submission creates proper proposal (Gatekeeper pattern),
test HTMX swap works.

Commit: `feat(ux): quick-identify — inline face naming on photo pages`
Update session log. `/compact` if above 50%.

---

## PHASE 3C: Public-First Verification (5 min)

Re-read Phase 3C from the prompt file.

Open EVERY modified page in incognito/unauthenticated mode:
- Homepage
- Photo page (/photo/{id})
- Person page (/person/{id})
- Compare (/compare or /facecompare)
- Estimate (/estimate)

Verify for each:
- [ ] No admin-only elements visible
- [ ] No broken layout from missing admin bar
- [ ] All public features still work
- [ ] No auth-related errors in console
- [ ] Mobile layout intact

Use Chrome Extension or Playwright. Screenshot each page.

Commit: `test(ux): public-first verification — all pages clean`
Update session log. `/compact` if above 50%.

---

## PHASE 3D: Visual Verification — Mobile + Desktop (5 min)

Re-read Phase 3D from the prompt file.

Screenshot all modified pages at both viewports:
- Desktop: 1280x900
- Mobile: 375x812

Review screenshots carefully. For each page, note in session log:
- Layout correct? Y/N
- Admin features visible when logged in? Y/N
- Admin features hidden in incognito? Y/N
- Touch targets ≥44px on mobile? Y/N

Add any issues to UX_ISSUE_TRACKER.md with severity rating.

Commit: `test(ux): visual verification — desktop + mobile screenshots`
Update session log.

---

# ═══════════════════════════════════════════════
# ACT TRANSITION: UX → Wrap-Up
# ═══════════════════════════════════════════════

Run `/compact` unconditionally.
Re-read session log for full status.

---

# ══════════════════════════════════════════
# PHASE 4A: ROADMAP + BACKLOG Sync (5 min)
# ══════════════════════════════════════════

Re-read ROADMAP.md and BACKLOG.md FULLY before editing.

### ROADMAP Updates:
- Session 60 combines old Sessions 60 + 61 + 62
- Remove separate Session 61 and 62 entries
- Add Session 60 to Recently Completed with description:
  "Gemini progressive refinement + SSE upload UX + admin unification"
- Update test count and version
- Renumber subsequent sessions if needed
- Future sessions should be: 
  61 → Landing Page Refresh
  62 → Next ML track work (LoRA or active learning)
  63+ → as needed

### BACKLOG Updates:
- Mark completed items from this session
- Add any new issues discovered during visual testing
- Update priorities based on current state
- Add breadcrumbs to Session 60 for completed items

### CRITICAL: Do not delete any existing items from either file.
Read both files fully before editing. Only add/update/reorder.

Commit: `docs: ROADMAP + BACKLOG sync — sessions 60-62 combined`
Update session log.

---

# ══════════════════════════════════════════
# PHASE 4B: Verification Gate (5 min)
# ══════════════════════════════════════════

Re-read `docs/prompts/session_60_prompt.md` (this prompt).
Check EVERY phase against the session log checklist:

```bash
echo "=== SESSION 60 VERIFICATION GATE ==="

# ACT 1: ML
echo "--- Gemini Config ---"
grep -c "GEMINI_MODEL" rhodesli_ml/config.py 2>/dev/null || echo "MISSING"

echo "--- API Logger ---"
ls rhodesli_ml/utils/api_logger.py 2>/dev/null && echo "✓" || echo "✗ MISSING"

echo "--- Progressive Refinement ---"
ls rhodesli_ml/scripts/progressive_refinement.py 2>/dev/null && echo "✓" || echo "✗ MISSING"

echo "--- No deprecated Gemini refs ---"
grep -rn "gemini-2.0-flash\|gemini-1.5" --include="*.py" . | \
  grep -v __pycache__ | grep -v ".git/" | grep -v session_context | \
  grep -v prompts | wc -l
echo "(should be 0)"

# ACT 2: Upload UX
echo "--- SSE endpoint ---"
grep -c "text/event-stream\|event-stream\|sse" app/main.py 2>/dev/null
echo "(should be >0)"

echo "--- Progressive UI ---"
grep -c "sse-connect\|hx-ext.*sse\|EventSource" app/main.py 2>/dev/null
echo "(should be >0)"

# ACT 3: Admin
echo "--- Admin bar ---"
grep -c "admin-bar\|admin.bar\|Admin Mode" app/main.py 2>/dev/null
echo "(should be >0)"

echo "--- Quick identify ---"
grep -c "identify-form\|quick.identify\|inline.*identify" app/main.py 2>/dev/null
echo "(should be >0)"

# Docs
echo "--- Session log complete ---"
grep -c "\[x\]" docs/session_logs/session_60_log.md 2>/dev/null
echo "phases completed"

# Tests
echo "--- All tests pass ---"
pytest tests/ -x -q 2>&1 | tail -5

echo "=== END VERIFICATION GATE ==="
```

Any FAIL → fix before proceeding. Update session log with
PASS/FAIL per item.

Commit: `test: session 60 verification gate`

---

# ══════════════════════════════════════════
# PHASE 4C: Final Docs + Changelog (5 min)
# ══════════════════════════════════════════

- CHANGELOG.md: v0.60.0 — list all features built
- Session log: finalize with all results, total test count
- ALGORITHMIC_DECISIONS.md: ensure AD numbers are sequential
- Update CLAUDE.md if any new patterns were established
- Ensure all new files have proper breadcrumbs

Commit: `docs: changelog v0.60.0, session 60 complete`
git push origin main

---

## DO NOT:
- Call Gemini API with real money (mock only)
- Implement LoRA fine-tuning
- Build batch upload or concurrent multi-photo processing
- Delete items from ROADMAP or BACKLOG
- Skip `/compact` between acts
- Skip visual verification phases
- Declare done without re-reading the original prompt
- Deploy without all tests passing
- Modify confirmed identity data

## IMPORTANT:
- The context management pattern is MANDATORY. Previous sessions
  lost later phases to context degradation.
- Phase isolation means: only read the current phase from the
  prompt file, not the full prompt.
- Chrome Extension first, Playwright fallback for visual testing.
- ALWAYS look at screenshots and note UX issues.
- Session log is your lifeline if compaction fires.
- Each phase ≤8 minutes. If longer, split and commit.
- Atomic commits per phase. Verification gate at the end.
- Update ALGORITHMIC_DECISIONS.md with decision provenance
  for every architectural decision.
