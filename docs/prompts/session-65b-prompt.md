# SESSION 65b — Production Verification, GEDCOM Linking, Enrichment Pipeline Fix
# Overnight autonomous prompt — run with --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2). This is a system where ML proposes hypotheses and humans adjudicate historical truth. Data loss is the cardinal sin.

Your mission this session: Verify 65a's work actually functions in production, build GEDCOM ↔ Identity linking UX, and fix the GEDCOM enrichment pipeline so future Gemini calls get full context.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-65b-context.md
cat ROADMAP.md
head -80 docs/ALGORITHMIC_DECISIONS.md
cat docs/analysis/prompt_fidelity_64d.md
cat SESSION_LOG.md 2>/dev/null || echo "No prior session log"
```

## NON-NEGOTIABLE RULES
1. **Every prompt must mandate updating ALGORITHMIC_DECISIONS.md** with full decision provenance.
2. Commit after EVERY completed task: `fix(scope): desc` or `feat(scope): desc`
3. Run `pytest tests/ -x -q` before each commit. All must pass.
4. Use `head`, `grep`, `tail` — never cat entire large files into context.
5. Use `/clear` between phases (NOT /compact — /compact is lossy).
6. After /clear, re-read CLAUDE.md + this prompt's current phase section from disk.
7. Deploy via `git push origin main`.
8. Session context file: `docs/session_context/session-65b-context.md`
9. No docs file >300 lines. ROADMAP.md <150 lines.
10. Log all work to SESSION_LOG.md as you go.

## ⚠️ CRITICAL: BROWSER TESTING + DATA SAFETY
This session uses browser automation to verify production UX. Rules:

1. **Use the Claude Chrome browser tool** for all browser verification. If unavailable, fall back to Playwright.
2. **DO NOT create, modify, or delete real heritage photo data.** Production data is irreplaceable.
3. If you must upload a test photo for verification:
   - Generate or use a tiny synthetic image (solid color, clearly not a real photo)
   - Name it `_test_65b_delete_me.jpg`
   - After verifying upload works, **DELETE it** from both the app and R2 storage
4. For all other verification: use **read-only browser checks** (load page, check DOM elements, screenshot).
5. Save all screenshots to `docs/screenshots/session-65b/` for Nolan's review.
6. Auth: if needed, check for existing session cookies or use admin credentials from environment.

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
# Session 65b Checkpoint — [timestamp]
## Completed: Phase X
## Current state: [what's done]
## Next action: [exact next step]
## Tests: [passing] / [total]
```

```bash
git add SESSION_CHECKPOINT.md && git commit -m "wip: session checkpoint" && git push
```

### On resume:
```bash
cat SESSION_CHECKPOINT.md
# Continue from "Next action"
rm SESSION_CHECKPOINT.md
```

---

## PHASE 0 — ORIENT (~5 min)

```bash
cat CLAUDE.md
ls app/ core/ tests/ scripts/ docs/
cat ROADMAP.md
cat docs/session_context/session-65b-context.md
cat docs/analysis/prompt_fidelity_64d.md
head -80 docs/ALGORITHMIC_DECISIONS.md
```

Write `SESSION_LOG.md`:
```markdown
# Session 65b Log
## Plan: Verify 65a → Fix if broken → GEDCOM linking → Enrichment fix → Docs
## Started: [timestamp]
```

Commit: `docs: session 65b plan`

---

## ⚠️ /clear AFTER PHASE 0
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65b-context.md`
Then read SESSION_LOG.md.

---

## PHASE 1 — PRODUCTION VERIFICATION OF 65a (~20 min)

Use browser automation (Chrome plugin preferred, Playwright fallback) to verify everything 65a shipped actually works in production. **Do not skip this phase.** 65a had zero production testing.

### 1A: Upload Verification (~8 min)

1. Open `https://rhodesli.nolanandrewfox.com/upload` in browser
2. Verify the page loads correctly (file drop zone, collection/source fields)
3. Generate a tiny synthetic test image:
   ```bash
   python3 -c "
   from PIL import Image
   img = Image.new('RGB', (200, 200), color='blue')
   img.save('/tmp/_test_65b_delete_me.jpg')
   "
   ```
4. Upload `_test_65b_delete_me.jpg` with collection="TEST" and source="TEST"
5. Watch the progress bar — does it advance past 0%?
6. **Three outcomes:**
   - **Upload completes:** Photo appears in library → PASS. Screenshot it. Then DELETE the test photo (both from app library and R2).
   - **Upload fails with error message:** The 65a fix is working (error surfaces instead of freezing). Read the error. Log it in SESSION_LOG.md. Proceed to 1A-fix.
   - **Upload freezes (no error, no progress):** The 65a fix didn't deploy correctly or doesn't work. Log it. Proceed to 1A-fix.

### 1A-fix: If Upload Is Still Broken

**Diagnose the actual root cause** — don't patch symptoms:

```bash
# Check Railway deployment logs for recent errors
# Check the upload route handler
grep -n "def.*upload\|@.*upload" app/main.py | head -20

# Check what the subprocess does
grep -rn "subprocess\|Popen\|ingest" app/ core/ --include="*.py" | head -30

# Check R2 upload code
grep -rn "r2\|R2\|boto3\|s3.*upload\|put_object" app/ core/ --include="*.py" | head -20

# Check for environment variable issues on Railway
grep -rn "R2_\|CLOUDFLARE\|AWS_\|BUCKET" app/ core/ --include="*.py" | head -20
```

Common root causes to investigate:
- InsightFace model failing to load (memory issue on Railway)
- R2 credentials expired or misconfigured
- File path issues between local and container filesystem
- Async processing dying before completion
- Missing Python dependency on Railway that exists locally

Fix the root cause. Write tests. Deploy and re-verify with browser.

### 1B: Compare Pair Verification (~5 min)

1. Open `https://rhodesli.nolanandrewfox.com/compare/pair`
2. Screenshot the two-panel layout
3. Verify both panels render with upload zones
4. If upload works (from 1A): upload two different images and verify:
   - Faces detected in both panels
   - Clicking faces highlights them
   - Similarity score displays after selecting one face from each panel
5. If upload doesn't work: verify the page at least loads and renders correctly

### 1C: Face Overlay Toggle (~3 min)

1. Open any photo page: `https://rhodesli.nolanandrewfox.com/photos/[any-photo-id]`
2. Verify the toggle button is visible
3. Click it — do face overlays show/hide?
4. Screenshot both states (on and off)

### 1D: Share Links + Navigation (~4 min)

1. Open a person page: `https://rhodesli.nolanandrewfox.com/person/[any-person-id]`
2. Verify share/copy-link button exists
3. Click it — does it copy the URL? (Check clipboard or look for toast notification)
4. Test navigation: click from photo → person → back to photo
5. Screenshot any broken links or missing navigation

### 1E: Log Results

Update SESSION_LOG.md with verification results:
```markdown
## Phase 1: Production Verification
- Upload: [PASS/FAIL — details]
- Compare pair: [PASS/FAIL — details]
- Face overlay toggle: [PASS/FAIL — details]
- Share links: [PASS/FAIL — details]
- Navigation: [PASS/FAIL — details]
- Screenshots saved to: docs/screenshots/session-65b/
```

Commit: `test: production verification of 65a features — [results summary]`
git push

---

## ⚠️ /clear AFTER PHASE 1
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65b-context.md`
Then read SESSION_LOG.md to see Phase 1 results.

---

## PHASE 2 — GEDCOM ↔ IDENTITY LINKING UX (~30 min)

This is the primary feature for 65b. When an admin identifies a face, they need a way to link that person to their GEDCOM family tree record — without requiring direct database inserts.

### 2A: Audit Current State (~5 min)

```bash
# Check existing identify flow
grep -rn "identify\|Identify\|FE-041\|help.*identify" app/main.py | head -20

# Check GEDCOM data structures
grep -rn "gedcom\|GEDCOM\|gedcom_face_links\|gedcom_individuals" app/ core/ --include="*.py" | head -30

# Check if gedcom_face_links table exists
grep -rn "gedcom_face_links" app/ core/ scripts/ --include="*.py" | head -10

# Check GEDCOM search/lookup capabilities
grep -rn "search.*gedcom\|gedcom.*search\|_build_parsed_gedcom" core/ --include="*.py" | head -10

# How many GEDCOM individuals are loaded?
grep -rn "21809\|individuals\|parsed_gedcom" core/ --include="*.py" | head -10
```

Document what exists, what's missing, and the integration points.

### 2B: Build GEDCOM Search API (~8 min)

Create an API endpoint that searches GEDCOM individuals by name:

**Route:** `GET /api/gedcom/search?q={name}`

**Response:** Top 10 matches, each with:
- `xref_id` (GEDCOM individual ID)
- `full_name`
- `birth_year` (if known)
- `death_year` (if known)
- `spouse_name` (for disambiguation)
- `parent_names` (for disambiguation)
- `ancestry_id` (if available)

**Search behavior:**
- Fuzzy match on name (Sephardic names have spelling variants: Capeluto/Capuano/Capueto, Israel/Yisrael)
- Case-insensitive
- Search both given name and surname
- Rank by relevance (exact match > starts-with > contains)
- Fast: this should query in-memory GEDCOM data, not hit Supabase per request
- Only search the relevant Rhodes/Capeluto subset if filtering is implemented, otherwise search all

### 2C: Build GEDCOM Link Step in Identify Flow (~12 min)

After an admin confirms a face identification (names a person), show a "Link to Family Tree" step:

**UX flow:**
1. Admin identifies face → types name → confirms
2. **NEW STEP:** Modal or inline section appears: "Link to Family Tree?"
3. Auto-search GEDCOM with the name just entered
4. Show top matches in a selectable list, each showing:
   - Full name + birth/death years
   - Spouse name (key disambiguator for common names)
   - Parent names
   - Small "Link" button per match
5. "No match — skip" button (prominently placed — not every person has a GEDCOM record)
6. On link: save to `gedcom_face_links` table (create if needed):
   - `face_id` → GEDCOM `xref_id` mapping
   - `linked_by` (admin user ID)
   - `linked_at` (timestamp)
   - `confidence` (admin-confirmed = 1.0)
7. On skip: close the step, identification is complete without GEDCOM link
8. Show success feedback: "Linked to [Full Name] (b. 1895 - d. 1972)"

**Admin-only:** Non-admin users never see this step. The Gatekeeper pattern means non-admin suggestions go to the queue first.

**Reversible:** Add an "Unlink" button on the person page for admins (in case of mistakes).

### 2D: Create/Verify Database Table

If `gedcom_face_links` doesn't exist in Supabase, create it:

```sql
CREATE TABLE IF NOT EXISTS gedcom_face_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  face_id TEXT NOT NULL,           -- references face identity
  gedcom_xref_id TEXT NOT NULL,    -- GEDCOM individual xref
  linked_by UUID,                  -- admin user who created the link
  linked_at TIMESTAMPTZ DEFAULT NOW(),
  unlinked_at TIMESTAMPTZ,         -- NULL = active link, set = unlinked
  confidence FLOAT DEFAULT 1.0,    -- 1.0 = admin confirmed
  notes TEXT,                       -- optional admin notes
  UNIQUE(face_id, gedcom_xref_id)  -- prevent duplicate links
);
```

### 2E: Test

```python
# Test: GEDCOM search API returns results for known names
# Test: GEDCOM search handles no-match gracefully
# Test: GEDCOM search is case-insensitive
# Test: GEDCOM link creation saves to database
# Test: GEDCOM unlink sets unlinked_at (soft delete)
# Test: non-admin cannot access GEDCOM link step
# Test: identify flow still works without GEDCOM linking (skip path)
```

```bash
pytest tests/ -x -q
```

Commit: `feat(gedcom): identity-to-GEDCOM linking UX with fuzzy search`
git push

### 2F: Browser Verify

Use browser automation to verify:
1. Identify a face (if possible in a non-destructive way — or just verify the UI renders)
2. Verify the "Link to Family Tree" step appears after identification
3. Verify GEDCOM search returns results
4. Verify "No match — skip" works
5. Screenshot the flow

**AD entry:** AD-XXX: GEDCOM ↔ Identity linking — admin-only post-identification step, fuzzy name search on in-memory GEDCOM, `gedcom_face_links` table with soft-delete unlink, non-admins never see this step.

---

## ⚠️ /clear AFTER PHASE 2
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65b-context.md`
Then read SESSION_LOG.md.

---

## PHASE 3 — FIX GEDCOM ENRICHMENT PIPELINE (~20 min)

Session 64d's prompt fidelity investigation found only 12.5% of Gemini API calls received GEDCOM context, and even those got only ~106 tokens. The combined pipeline's key value proposition (rich context → better alignment) was not delivered. Fix this so future runs work correctly.

### 3A: Trace the Enrichment Code Path (~8 min)

```bash
# Find where Gemini prompts are assembled
grep -rn "gemini.*prompt\|build.*prompt\|assemble.*prompt\|create.*prompt" core/ scripts/ --include="*.py" | head -20

# Find where GEDCOM context is injected
grep -rn "gedcom.*context\|enrich\|family.*context\|genealog" core/ scripts/ --include="*.py" | head -20

# Find the combined pipeline entry point
grep -rn "combined_pipeline\|run_combined\|alignment.*pipeline" scripts/ --include="*.py" | head -20

# Check how GEDCOM matching works for a given photo
grep -rn "match.*gedcom\|gedcom.*match\|link.*gedcom" core/ --include="*.py" | head -20
```

Read the actual prompt assembly code. Identify:
1. Where GEDCOM context is supposed to be injected
2. Why it's only happening for 12.5% of photos (likely: only photos with existing GEDCOM links get enrichment, but most photos don't have links yet)
3. Why the enrichment is only ~106 tokens (likely: only sending name, not full family context)

### 3B: Fix the Enrichment (~8 min)

**The fix should ensure:**
1. For photos with known people (identified faces): pull ALL GEDCOM context for each identified person:
   - Full name + aliases
   - Birth year, birth place
   - Death year, death place
   - Spouse(s) name(s) + marriage info
   - Parents' names
   - Children's names
   - Siblings' names (if available)
   - Known residences
   - Ancestry ID
2. For photos with unidentified faces: include available context from the photo's collection, time period, and location to help Gemini make inferences
3. For photos with no GEDCOM connections at all: send the photo with standard instructions (no enrichment — this is expected and fine)

**Token budget target:** A well-enriched prompt should be 400-1000 tokens of GEDCOM context, not 106.

**Verification step in the pipeline:** After assembling each prompt, log:
- `gedcom_token_count`: approximate token count of GEDCOM context portion
- `enrichment_level`: "full" (400+ tokens), "partial" (100-400), "none" (0)
- Save to `gemini_api_calls.gemini_config` field (currently unpopulated)

### 3C: Fix API Call Logging

Update `call_gemini_alignment()` (or equivalent) to populate the currently-empty fields:
- `gemini_config`: JSON with model name, prompt template version, enrichment level, GEDCOM token count
- `response_summary`: JSON with response token count, number of faces described, any errors

This makes future audits trivial instead of requiring manual investigation.

### 3D: Test

```python
# Test: prompt assembly includes GEDCOM context for linked photos
# Test: prompt assembly includes full family context (not just name)
# Test: GEDCOM token count is logged in gemini_config
# Test: enrichment_level correctly categorizes full/partial/none
# Test: response_summary is populated after API call
# Test: photos with no GEDCOM links get standard (unenriched) prompt
```

```bash
pytest tests/ -x -q
```

Commit: `fix(pipeline): GEDCOM enrichment now sends full family context + API call logging`
git push

**Do NOT re-run the full pipeline.** Just fix the code. A re-run should be planned separately (Session 66 or later) after verifying the fix on a small sample.

**AD entry:** Update AD-159 with: root cause of thin enrichment, fix applied, expected token counts, logging additions. Breadcrumb to Session 65b.

---

## ⚠️ /clear AFTER PHASE 3
Re-read: `cat CLAUDE.md && cat docs/session_context/session-65b-context.md`
Then read SESSION_LOG.md.

---

## PHASE 4 — DOCS SYNC + SESSION CLOSE (~10 min)

### 4A: CHANGELOG.md
Add entry for this session:
- Production verification of 65a features (results)
- GEDCOM ↔ Identity linking UX
- GEDCOM enrichment pipeline fix
- API call logging improvements

### 4B: ROADMAP.md
Update:
- Session 65b completed items
- Version number + test count
- Next planned sessions:
  - Session 66: Re-run enriched pipeline on sample (10-20 photos), alignment quality deep dive, portfolio docs
  - Session 67: Similarity calibration (next ML milestone)
  - Session 68: Multi-community architecture planning

Keep under 150 lines.

### 4C: BACKLOG.md
Update with completed and remaining items:
- GEDCOM linking: COMPLETED
- Enrichment pipeline: FIXED (re-run deferred to 66)
- Remaining from walkthrough: search on browse pages, map accuracy, Timeline/Tree improvements
- GEDCOM loading scoping (filter to relevant branch) — still pending

### 4D: ALGORITHMIC_DECISIONS.md
Verify all AD entries from this session have full provenance.

### 4E: Final Verification Gate

```bash
echo "=== SESSION 65b VERIFICATION ==="

# Phase 1: Production screenshots exist
ls docs/screenshots/session-65b/ 2>/dev/null | head -10

# Phase 2: GEDCOM linking
echo "GEDCOM search API:"
grep -c "gedcom.*search\|/api/gedcom" app/main.py
echo "GEDCOM link table:"
grep -c "gedcom_face_links" app/ core/ --include="*.py" -r

# Phase 3: Enrichment fix
echo "GEDCOM enrichment tokens logged:"
grep -c "gedcom_token_count\|enrichment_level\|gemini_config" core/ scripts/ --include="*.py" -r

# All tests pass
pytest tests/ -x -q

echo "=== VERIFICATION COMPLETE ==="
```

Commit: `docs: session 65b changelog, ROADMAP, BACKLOG, AD sync`
git push

### 4F: Session Summary

```markdown
## Session 65b Complete
- Phases completed: [list]
- Commits: [count]
- Tests: [passing] / [total] ([new] new)
- Production verification: [results per feature]
- Upload status: [WORKING/STILL BROKEN — details]
- GEDCOM linking: [SHIPPED/PARTIAL]
- Enrichment pipeline: [FIXED/PARTIAL]
- Screenshots: docs/screenshots/session-65b/
```

---

## TOKEN EFFICIENCY
- Use `grep -n` to find code, not `cat` entire files
- Use `pytest tests/test_specific.py -x -q` during dev, full suite at phase end
- Don't re-read files already in context
- Between phases: /clear then re-read CLAUDE.md + context + SESSION_LOG.md

## PARALLELIZATION
| Phase | Strategy | Why |
|-------|----------|-----|
| 0 Orient | Sequential | Must understand before acting |
| 1 Verify | Sequential | Browser automation, depends on deploy state |
| 2 GEDCOM Link | Can parallelize 2B/2C if API and UI are independent | But safer sequential |
| 3 Enrichment | Sequential | Depends on understanding current pipeline |
| 4 Docs | Sequential | Depends on all prior work |

## BEGIN
Start with Phase 0. Read the mandatory files. Write SESSION_LOG.md. Execute.
