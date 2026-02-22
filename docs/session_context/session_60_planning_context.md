# Session 60 Planning Context: Gemini Progressive Refinement + UX Overhaul

Save this file to: `docs/session_context/session_60_planning_context.md`

---

## Why This Session Exists

Session 60 combines three previously separate planned sessions into one
compaction-resistant overnight run:

- **Session 60 (original):** Gemini Progressive Refinement (ML track)
- **Session 61 (original):** Interactive Upload UX with SSE
- **Session 62 (original):** Admin/Public UX Unification

Combined because: all three are complementary and the phase isolation
pattern means they can run sequentially in one prompt without
cross-contamination. The ML track is data-safe (rhodesli_ml/ only,
no app data mutations). The UX tracks are additive (new routes and
components, not modifying existing data).

### Breadcrumbs
- ML plan sequence: AD in ALGORITHMIC_DECISIONS.md (date estimation → 
  similarity calibration → progressive refinement → LoRA)
- Similarity calibration: Session 55/55b (completed, ONNX exported)
- CORAL date estimation: Session 57 (completed, deployed)
- MLflow registry: Session 58 (completed)
- Face Compare Standalone: Session 59 (completed, /facecompare route)
- Supabase dual-write: Session 59C (data loss fix, may be in progress)
- Progressive refinement architecture: AD in docs (Session 50 Phase 4)
- Upload UX SSE: discussed in Session 54F feedback, PRD context exists
- Admin/Public UX: deferred since Session 47, design decided as 
  "Progressive Enhancement" pattern

---

## ACT 1: Gemini Progressive Refinement (ML Track)

### What It Is

Every time a verified fact is confirmed (identity, date, location,
GEDCOM data), re-run Gemini analysis with new context. Compare 
before/after results. Log everything. This is the "Fact-Enriched
Re-Analysis" pattern from AD documentation.

### Research Foundation (from prior sessions)

**Core pattern:** SELF-REFINE (Madaan et al. 2023) adapted with
EXTERNAL verified facts rather than self-generated feedback:
- SELF-REFINE: generate → self-critique → refine
- Our approach: generate → community verifies facts → re-analyze
  with verified context → compare → admin approves

**Geographic-cultural dating:** When Gemini learned a postcard was
from Rhodes, it narrowed date range by analyzing region-specific
hairstyles and studio conventions. This is a form of context-enriched
VLM analysis with domain-specific calibration.

**Combined API call:** Date + faces + location should be ONE Gemini 
call. More cost-efficient and produces better cross-referenced results.
Example: "Military uniforms suggest WWII, 'WELCOME HOME' banner 
confirms post-war, menorah symbol confirms Jewish community."

### Model Selection

Use **Gemini 3.1 Pro** for all vision work (or latest available):
- 2x reasoning improvement over 3 Pro
- Bounding box capability confirmed
- `media_resolution` parameter for token cost control
- Cost for full library (271 photos): ~$7.60
- Evidence quality is the UX differentiator — don't compromise

### What To Build

1. **Gemini config centralization:** Single model config, no hardcoded
   model strings scattered across files

2. **Progressive refinement pipeline:**
   - Script: `rhodesli_ml/scripts/progressive_refinement.py`
   - Input: photo + all verified facts (identities, dates, locations)
   - Output: enriched analysis with comparison to previous results
   - Logging: full prompt, response, model version, token cost

3. **API result logging infrastructure:**
   - All Gemini calls logged with: prompt, response, model, cost,
     input context (verified facts), comparison to previous estimate
   - Purpose: build analytical dataset to understand which facts
     improve estimates most

4. **Dry-run safety:** `--dry-run` flag (3 photos max), `--max-cost`
   flag (default $1.00), env var check for GEMINI_API_KEY

5. **Evaluation script:** Compare old vs new estimates for photos
   where we have verified facts. Quantify improvement.

### Ground Truth Available

From Session 49B interactive work and community contributions:
- 28+ confirmed birth years (ground truth anchors)
- 9 identity confirmations from Facebook community
- Carey Franco's 8 identifications from Thanksgiving Eve photo
- GEDCOM data if uploaded
- These feed directly into enriched prompts

---

## ACT 2: Interactive Upload UX with SSE

### Problem

Upload processing takes 10-28 seconds depending on face count.
Currently: silent waiting with no feedback. Users think it's broken.

### Solution: Server-Sent Events (SSE) for Progressive Loading

FastHTML + HTMX naturally supports SSE. Architecture:

1. User uploads photo → immediate acknowledgment
2. Server streams events as each stage completes:
   - "Detecting faces..." → "Found 3 faces"
   - "Generating embeddings..." → "Comparing to 1061 faces"
   - "Searching for matches..." → "2 potential matches found"
   - "Estimating date..." → "Circa 1935"
3. Results appear progressively, not all-at-once after long wait

### Technical Pattern

```python
@rt('/api/upload/stream')
async def upload_stream(request):
    # Return SSE endpoint
    async def event_generator():
        yield f"data: {json.dumps({'stage': 'detecting', 'message': 'Detecting faces...'})}\n\n"
        faces = await detect_faces(photo)
        yield f"data: {json.dumps({'stage': 'detected', 'count': len(faces)})}\n\n"
        # ... progressive stages
    return StreamingResponse(event_generator(), media_type='text/event-stream')
```

HTMX SSE extension handles client-side:
```html
<div hx-ext="sse" sse-connect="/api/upload/stream" sse-swap="message">
  <!-- Progressive results appear here -->
</div>
```

### Breadcrumbs
- Session 54F feedback: identified silent processing as UX problem
- Serving Path Contract (AD-110): user-facing requests must not run
  heavy ML inference synchronously
- Current compare flow: 65s→10.5s after Session 54F optimizations
  (buffalo_sc model + 640px resize)
- SSE is the right pattern because HTMX has native SSE support

### Scope

BUILD THIS SESSION:
- SSE endpoint for photo upload processing
- Progressive UI feedback with stage indicators
- Face detection results shown incrementally
- Loading states and error handling
- Works for both /compare and /facecompare routes

DO NOT BUILD:
- Background job queue (Redis/Celery — premature at current scale)
- WebSocket fallback (SSE is sufficient)
- Concurrent multi-photo upload (defer to later)

---

## ACT 3: Admin/Public UX Unification

### Design Decision (from Session 47 research)

**Pattern chosen:** Progressive Enhancement (Option E)
- Public view is the canonical layout
- Admin capabilities layered on top when authenticated
- No separate admin URL scheme or layout

**Long-term target:** Expert's three-mode system (Option G)
- Explore (public browsing)
- Curate (admin editing — identify, merge, correct)
- Analyze (ML tools — estimate, compare, cluster review)

### What To Build

1. **Admin bar / mode indicator:**
   - Subtle top bar when logged in as admin
   - Shows current mode, quick actions
   - Never visible to public users

2. **Inline admin actions:**
   - On photo pages: "Edit metadata" button (admin only)
   - On person pages: "Merge", "Correct birth year" (admin only)
   - On face cards: "Identify" directly without navigation

3. **Quick-Identify flow:**
   - Click face → type name → submit → done
   - No page navigation required
   - This is the #1 community-driven UX request (from Carey Franco's
     8 names taking 15 minutes instead of 2)

4. **Public-first verification:**
   - Every page must look correct to unauthenticated users
   - Admin features must not leak or break public layout
   - Test in incognito after every change

### Breadcrumbs
- Session 47 research: compared 7 UX patterns (A-G)
- Session 49B interactive session found "Name These Faces" was
  invisible when not admin
- Session 51 fixed auth/visibility issues
- UX_ISSUE_TRACKER.md has 25+ items, many are admin/public gaps

---

## Compaction Mitigation Strategy

### Why This Matters

Sessions 47, 49C, and others lost later phases to context degradation.
Research confirms ~20-30% performance drop when operating with
accumulated vs fresh context. Claude Code hits auto-compact at ~167K
tokens (33K buffer on 200K window).

### Strategy: Micro-Phases + Disk-Based State

1. **Every phase is 5-8 minutes max.** If a phase would take longer,
   split it into sub-phases. This keeps individual phase context small.

2. **Session log is the source of truth.** After every phase, write
   what was actually done to `docs/session_logs/session_60_log.md`.
   If compaction happens, Claude Code re-reads the session log to
   know where it left off.

3. **Mandatory `/compact` at 50% context usage** (not 60% like before).
   More aggressive clearing means more headroom for each phase.

4. **Phase isolation:** Only read the relevant phase section from
   the prompt file. Don't carry forward the full prompt in context.

5. **Atomic commits per phase:** Each phase gets its own git commit.
   If something breaks, we can bisect to the exact phase.

6. **Act transitions clear context:** Between ACT 1 (ML) and ACT 2
   (UX), run `/compact` unconditionally. These are completely
   independent tracks.

7. **Progress breadcrumbs in session log:** Each phase entry includes:
   - What was planned
   - What was actually built
   - Files touched
   - Test count before/after
   - Any deviations or issues found

### Recovery Protocol

If auto-compact fires mid-phase:
1. Read `docs/session_logs/session_60_log.md`
2. Read `docs/prompts/session_60_prompt.md`
3. Identify which phase was in progress
4. Re-read that specific phase section
5. Continue from last committed state

---

## Visual Testing Strategy

### Primary: Claude Chrome Extension (if available)

The Chrome Extension provides real browser screenshots without
Playwright setup overhead. For each UX change:
1. Navigate to the affected page
2. Capture screenshot
3. Review for visual issues
4. Log any UX/UI issues to `docs/UX_ISSUE_TRACKER.md`

### Fallback: Playwright (headless Chromium)

If Chrome Extension is unavailable or fails:
```bash
pip install playwright --break-system-packages
playwright install chromium
```

For each UX change, write a verification script that:
1. Opens the page in headless Chromium
2. Simulates the user action
3. Takes a screenshot
4. Asserts the expected outcome

### ALWAYS: Review Screenshots

Whether using Chrome Extension or Playwright, Claude Code MUST:
- Actually look at the screenshots (not just save them)
- Note any visual issues in the session log
- Add persistent issues to UX_ISSUE_TRACKER.md
- Test both desktop (1280x900) and mobile (375x812) viewports

---

## Scope Boundaries

### This Session Does:
- Gemini progressive refinement pipeline (rhodesli_ml/)
- API logging infrastructure
- SSE upload progress for /compare and /facecompare
- Admin bar with inline quick-identify
- Public/admin layout unification
- Visual testing of all UX changes
- ROADMAP + BACKLOG updates (combine sessions 60-62 → 60)

### This Session Does NOT:
- Call Gemini API with real money (dry-run only, unless confirmed)
- Implement LoRA fine-tuning
- Build batch upload or multi-photo concurrent processing
- Deploy to production (git push only, verify post-deploy)
- Modify any confirmed identity data
- Build GEDCOM import flow (requires interactive session)

---

## Files Expected To Be Modified

### ML Track (ACT 1)
- `rhodesli_ml/scripts/progressive_refinement.py` (new)
- `rhodesli_ml/scripts/gemini_eval.py` (new or updated)
- `rhodesli_ml/config.py` (Gemini model centralization)
- `rhodesli_ml/utils/api_logger.py` (new)
- `docs/ALGORITHMIC_DECISIONS.md` (new ADs)

### UX Track (ACT 2-3)
- `app/main.py` (SSE endpoints, admin bar, quick-identify)
- `app/templates/` or inline HTML (progressive loading UI)
- `static/css/` (admin bar styles)
- `static/js/` (SSE client handling, if needed beyond HTMX)

### Harness
- `ROADMAP.md` (combine sessions 60-62 → 60)
- `BACKLOG.md` (update priorities and completed items)
- `CHANGELOG.md` (v0.60.0)
- `docs/session_logs/session_60_log.md` (new)
- `docs/prompts/session_60_prompt.md` (saved copy of prompt)
- `docs/UX_ISSUE_TRACKER.md` (updated with findings)
