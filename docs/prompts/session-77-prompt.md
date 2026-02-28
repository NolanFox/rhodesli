# RHODESLI — Session 77: Compare Feature Rebuild

## SETUP (do this before any coding)

### Step 1: Read the repo

Read these files in order. Do NOT skip any:
1. `AGENTS.md` (repo root)
2. `CLAUDE.md` (repo root — yes, read it even though you're Codex)
3. `docs/ROADMAP.md`
4. `docs/ALGORITHMIC_DECISIONS.md`
5. `docs/session_context/session-77x-context.md`

### Step 2: Understand the tech stack from actual code

Read `app/main.py` (at least the first 200 lines and the compare-related routes).
Read `app/services/` directory listing and skim key service files.
Run `grep -rn "compare\|/compare" app/main.py | head -40` to find all compare routes.
Run `grep -rn "upload" app/main.py | head -40` to find upload handling.

**CRITICAL:** This is FastHTML + HTMX. If you see Python functions returning HTML
elements like `Div()`, `Form()`, `Input()` — that IS the framework. Do NOT introduce
React, Next.js, Flask, Django, or Node.js. If you're tempted to, stop and re-read
`app/main.py` to understand the pattern.

### Step 3: Create feature branch

```bash
git checkout -b feature/session-77-compare-rebuild
git push -u origin feature/session-77-compare-rebuild
```

### Step 4: Baseline test run

```bash
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -5
python -m pytest rhodesli_ml/tests/ -x -q --timeout=60 2>&1 | tail -5
```

Record the pass/fail counts. This is your baseline. Do not break these.

---

## PHASE 1: Read-Only Audit (~15 min)

**Goal:** Deep understanding of what exists. No code changes.

### 1A: Map the compare feature

Find every file, route, template, and test related to compare:
```bash
rg -l "compare" app/ tests/ --type py
rg -l "upload" app/ tests/ --type py
rg "def.*compare\|def.*upload" app/main.py
```

Create `docs/session_logs/session_77_audit.md` documenting:
- Every compare-related route and what it does
- Every upload-related function and its current state
- Where face detection is triggered for uploaded photos
- Where embeddings are compared to the archive
- Where results are rendered
- Where uploads are (or should be) saved to R2
- What tests exist for compare functionality

### 1B: Trace the upload flow end-to-end

Follow the code path from the upload form → POST handler → file processing →
face detection → embedding comparison → result rendering. Document every step.
Note where it breaks or where error handling is missing.

### 1C: Audit the UX

Look at the HTML generation for `/compare` and `/compare/pair`. Assess:
- Is there a clear upload zone?
- Is there a loading indicator during processing?
- Do results show calibrated confidence labels?
- Is there a shareable URL for results?
- Is there a "Compare Another" flow?
- Does it work on mobile (touch targets, layout)?

### 1D: Do your own research

Search the web for current best practices in face comparison UX. Look at:
- MyHeritage, FamilySearch, Betaface, PimEyes (for UX patterns only)
- Face comparison API documentation (for feature ideas)
- Heritage/genealogy photo tools (for domain-specific patterns)

Document findings in `docs/session_logs/session_77_audit.md` under a
"Competitive Research" section. **I want your fresh perspective.** If you
find ideas that could improve our approach, document them clearly.

### 1E: Create the improvement plan

Based on your audit and research, write a prioritized plan in
`docs/session_logs/session_77_audit.md` under "Improvement Plan":
- Critical fixes (things that are broken)
- UX improvements (things that work but poorly)
- New features (things we should add)
- Test improvements (gaps in coverage, speed issues)

**Commit:** `docs: session 77 phase 1 — compare audit and improvement plan`

---

## PHASE 2: Fix the Upload Pipeline (~20 min)

**Goal:** Make uploads actually work. This is the #1 priority.

### 2A: Fix single-photo upload

The upload at `/compare` must:
1. Accept a photo via drag-drop or file picker
2. Show a loading indicator immediately
3. Run InsightFace face detection on the upload
4. Generate embeddings for each detected face
5. Compare embeddings against `data/face_index.json`
6. Return results sorted by confidence (highest first)
7. Display results with calibrated confidence tiers

If the upload handler is missing error handling, add it. If it silently
fails, add explicit error messages. If it hangs, add timeouts.

### 2B: Fix two-photo comparison

The upload at `/compare/pair` must:
1. Accept two photos
2. Detect faces in both
3. Compare all faces in photo A against all faces in photo B
4. Also compare all faces against the archive
5. Show cross-comparison results AND archive matches

### 2C: Fix upload persistence

Every uploaded photo must be saved (not just processed and discarded):
1. Save to R2 `uploads/compare/{timestamp}_{filename}`
2. Write metadata to Supabase (or JSON file if Supabase isn't available):
   - upload timestamp, original filename, face count, processing status
3. Queue for admin review

If R2 isn't configured in the environment, save to local filesystem as
fallback and log a warning. Do NOT let missing R2 break the upload flow.

### 2D: Add loading indicator

When a user submits a photo, they must see IMMEDIATE feedback:
- Disable the upload button
- Show a spinner or progress message ("Analyzing faces...")
- Use `hx-indicator` for HTMX-based loading states

### 2E: Test the fixes

```bash
python -m pytest tests/ -x -q --timeout=60 -k compare
```

If no compare tests exist, that's a Phase 4 problem. For now, verify
manually that the upload flow works by reading the code path.

**Commit:** `fix(compare): upload pipeline — detection, comparison, persistence`

---

## PHASE 3: UX Rebuild (~25 min)

**Goal:** Make compare look and feel like a real product.

### 3A: Redesign the compare landing page (`/compare`)

The page should have:
1. Clear headline: "Compare Faces" or similar
2. Large, obvious upload zone (drag-drop + click)
3. Brief explanation of what happens ("Upload a photo to find matches in our historical archive")
4. Mobile-first layout (works on 375px viewport)

### 3B: Redesign the results display

Results should show:
1. The uploaded photo with detected faces highlighted
2. Match cards sorted by confidence (highest first)
3. Each match card shows:
   - Archive photo thumbnail
   - Person name (if identified) or "Unidentified"
   - Confidence tier with color coding (🟢🟡🟠⚪)
   - Calibrated percentage
   - Link to the person's archive page
4. If no matches above threshold: friendly "No strong matches found" message
5. "Compare Another Photo" button

### 3C: Add Gemini enrichment display

If Gemini analysis is available for the uploaded photo, show a
"Photo Detective" section with evidence cards:
- Clothing/Fashion evidence
- Setting/Architecture evidence
- Estimated date range with reasoning
- Photo format/quality indicators

If Gemini API isn't available, skip this gracefully — don't break the page.

### 3D: Add shareable results

Each comparison result should have a unique URL that can be shared.
When someone visits a result URL, they see the same results page
(minus the ability to re-upload).

### 3E: Add bridge CTAs

At the bottom of results:
- "Explore the full archive →" (links to main browse page)
- "Know someone in this photo? Help identify them →" (links to identification flow)
- "Upload more photos to contribute to the archive →"

**Commit:** `feat(compare): UX rebuild — landing page, results, evidence display`

---

## PHASE 4: Test Writing (~15 min)

**Goal:** Comprehensive test coverage for compare, plus speed improvements.

### 4A: Write compare golden tests

Create or update `tests/test_compare.py` with:

```python
def test_compare_upload_returns_results():
    """Upload a photo → get face match results back."""
    # This is the GOLDEN TEST. If this breaks, compare is broken.

def test_compare_pair_cross_matches():
    """Upload two photos → get cross-comparison results."""

def test_compare_upload_persists_photo():
    """Uploaded photo is saved (R2 or local fallback)."""

def test_compare_results_have_shareable_url():
    """Each result set has a unique, accessible URL."""

def test_compare_no_matches_shows_friendly_message():
    """When no faces match, show helpful message not error."""

def test_compare_loading_indicator_present():
    """Upload form has hx-indicator for loading state."""

def test_compare_confidence_tiers_calibrated():
    """Confidence labels match calibrated score ranges."""

def test_compare_mobile_layout():
    """Compare page renders acceptably at 375px width."""
```

### 4B: Audit test speed

```bash
python -m pytest tests/ -q --timeout=60 --durations=20 2>&1 | tail -30
```

Identify the 20 slowest tests. For each one, determine:
- Is it slow because of model loading? (acceptable)
- Is it slow because of network calls? (mock them)
- Is it slow because of bad test design? (fix it)

Document findings and fix what you can without breaking tests.

### 4C: Run full test suite

```bash
python -m pytest tests/ -x -q --timeout=60
python -m pytest rhodesli_ml/tests/ -x -q --timeout=60
```

All baseline tests must still pass. New tests must pass.

**Commit:** `test(compare): golden tests + speed audit`

---

## PHASE 5: Documentation & Harness (~10 min)

**Goal:** Full provenance trail per project conventions.

### 5A: Update ALGORITHMIC_DECISIONS.md

For each significant decision made in this session, add an AD-NNN entry:
- What was decided
- What alternatives were considered
- Why this approach was chosen
- Evidence/sources
- Revisit conditions

### 5B: Update CHANGELOG.md

Add session 77 entry with all changes made.

### 5C: Write self-assessment

Create `docs/session_logs/session_77_assessment.md`:

```markdown
# Session 77 Self-Assessment

## Scores (1-5)
- Stack Comprehension: X/5 — [did I correctly use FastHTML+HTMX?]
- Self-Verification: X/5 — [test counts, commands run]
- Harness Compliance: X/5 — [AD entries, commits, docs]
- Code Quality: X/5 — [patterns followed, errors handled]
- Data Safety: X/5 — [data/ files untouched]

## Accomplished
- [list]

## NOT Accomplished
- [list with reasons]

## Test Results
- Before: X passed, Y failed
- After: X passed, Y failed
- New tests: N

## Fresh Ideas from Research
- [list any novel approaches discovered]

## Recommendations for Session 78
- [what should come next]
```

### 5D: Update SESSION_HISTORY.md

Add Session 77 summary.

### 5E: Final commit and tag

```bash
git add -A
git commit -m "docs: session 77 phase 5 — assessment, changelog, harness updates"
```

---

## What Success Looks Like

1. ✅ User uploads photo at `/compare` → sees face matches IMMEDIATELY
2. ✅ User uploads two photos at `/compare/pair` → sees similarity score
3. ✅ Comparison results have shareable URLs that WORK
4. ✅ Confidence labels are calibrated (not misleading)
5. ✅ Uploaded photos are saved for potential contribution
6. ✅ Test suite has golden tests that catch upload chain breaks
7. ✅ Test suite runs faster than before (or slowness is documented)
8. ✅ All harness files updated with full provenance
9. ✅ Every phase has its own commit
10. ✅ Fresh ideas from your own research are incorporated

---

## IMPORTANT RULES

1. **This is FastHTML + HTMX.** No React. No Next.js. No Node.js. Server-rendered
   HTML with HTMX attributes for dynamic behavior. Vanilla JS only where HTMX
   cannot handle it.

2. **Pre-computed embeddings are the key insight.** The entire compare performance
   fix comes down to: don't re-detect faces on archive photos. Use stored embeddings
   from `data/face_index.json`.

3. **Commit after every phase.** Small, atomic commits with descriptive messages.

4. **Run tests after every code change.** `python -m pytest tests/ -x -q --timeout=60`

5. **Never modify `data/` files.** Code changes only.

6. **Document decisions.** Every non-trivial choice gets an AD-NNN entry in
   `docs/ALGORITHMIC_DECISIONS.md`.

7. **If stuck, read more code first.** `rg` is your friend. Read existing patterns
   before inventing new ones.

8. **Do your own research.** You have internet access. Use it to look up face
   comparison UX best practices, FastHTML/HTMX patterns, and anything else that
   helps you build a better product. Document what you find.

9. **Your fresh perspective is valuable.** If you see something in the codebase
   that could be done better — even if it's outside the compare feature — note it
   in the assessment. We want novel ideas, not just execution.

10. **Don't deploy.** Build on the feature branch. Deployment is a manual step
    after human review.
