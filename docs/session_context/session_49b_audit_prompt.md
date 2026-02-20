# Session 49B-Audit: Comprehensive Playwright-First Site Audit

Read CLAUDE.md. Read BACKLOG.md. Read ROADMAP.md.
Read docs/session_logs/session_49b_triage.md (from the triage session — contains root causes found).
Read docs/session_context/session_49_interactive_prep.md.

## CONTEXT MANAGEMENT — READ THIS FIRST

This is a long overnight session. **You WILL hit context limits if you don't manage aggressively.**

**Protocol:**
1. **Save this entire prompt** to `docs/session_context/session_49b_audit_prompt.md` before doing anything else
2. **Work one phase at a time.** After completing each phase:
   - Log results to `docs/session_logs/session_49b_audit_log.md` (create on Phase 0)
   - Run `/compact` with instruction: "Preserve: current phase results, audit findings file path, test file paths, what phases remain. Drop: code snippets already committed, file contents already read."
   - Re-read ONLY the next phase from the saved prompt file (use `sed -n '/## PHASE N/,/## PHASE/p'` to extract)
3. **Between phases:** Verify you know what phase you're on by checking the session log
4. **If context gets tight:** The session log is your ground truth. Read it, not the full prompt.
5. **Record as you go.** Every test result, every fix, every finding goes into the session log IMMEDIATELY — not batched at the end.

**Phase sequence:** 0 (setup) → 1 (write tests) → 2 (run audit) → 3 (fix critical+high) → 4 (documentation)

---

## Context

After the triage session fixed 3 critical failures, this overnight session audits EVERY page and EVERY user action across the entire site. The goal is to produce a definitive list of what works and what doesn't, then fix everything fixable.

**Triage findings to verify:**
- Bug 1 (Upload stuck at 0%): FIXED — subprocess stderr=DEVNULL caused silent death. Now has timeout + status file.
- Bug 2 (Compare): Triage said "works, no fix needed" but Nolan experienced a clear failure. **The audit MUST investigate this further.** Possible causes: no progress indicator during 5-10s processing, results render below fold, browser timeout vs curl timeout difference, transient Railway issue. Test with BOTH curl AND Playwright to compare behavior.
- Bug 3 (Sort routing): FIXED — _sort_control() now includes view_mode parameter.

**Architecture:** All agents hit production — limit concurrency to avoid crashing Railway's single worker.

---

## PHASE 0: Setup (~5 min)

### 0-FIRST: Save this prompt to the repo
```bash
cp [this prompt file] docs/session_context/session_49b_audit_prompt.md
git add docs/session_context/session_49b_audit_prompt.md
```
This is your reference for the entire session. When you `/compact`, you can re-read specific phases from this file.

### 0A: Verify triage fixes landed
```bash
git log --oneline -5
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/health
```

### 0B: Create audit infrastructure
```bash
mkdir -p tests/e2e/audit
mkdir -p docs/ux_audit/session_findings
```

### 0B2: Create session log (YOUR GROUND TRUTH FOR THE WHOLE SESSION)
Create `docs/session_logs/session_49b_audit_log.md` NOW with phase headers.

### 0C: Verify Playwright
```bash
npx playwright --version || npm install --save-dev @playwright/test
npx playwright install chromium
```

### 0D: Create the test config
Create `tests/e2e/playwright.config.js` (if not exists).

### 0E: Create post-deploy hook (54G/54H never created it)

---

## PHASE 1: Write Comprehensive Playwright Tests (~30 min)

Write one test file per route group. Each test verifies BOTH page load AND user interactions.

### 1A: Public Routes (logged-out user)
`tests/e2e/audit/public-routes.spec.js`

Test every public page:
- `GET /` — loads, has photos, has navigation
- `GET /photos` — photo grid renders, photos have face count badges
- `GET /photos/{id}` — photo detail loads, face overlays render, names shown on identified faces
- `GET /person/{id}` — person page loads, photos shown, birth year if available
- `GET /timeline` — loads, has photo cards, person filter works
- `GET /map` — loads, markers render
- `GET /tree` — loads, renders with data
- `GET /compare` — loads, upload form present
- `GET /estimate` — loads, face grid renders with correct counts, pagination works
- `GET /connect` — loads (if exists)
- `GET /nonexistent` — returns 404 page (not a crash)
- `GET /person/99999` — returns 404 (not a crash)
- `GET /photos/99999` — returns 404 (not a crash)

For each: verify no console errors, no broken images, no raw HTML entities in text.

### 1B: Navigation and Linking
`tests/e2e/audit/navigation.spec.js`

- Click a photo in the grid → photo detail opens
- Click a person name on a photo → person page opens
- Click "back" or breadcrumb → returns to previous view
- Sidebar links all work (each section navigates correctly)
- Sort options on /?section=to_review produce different orderings (THE BUG WE JUST FIXED — verify)
- Sort by faces vs sort by date vs sort by name: verify results actually differ
- URL includes sort_by parameter AND handler respects it
- Photo lightbox: left/right arrows work, keyboard arrows work
- Incognito/logged-out: all public routes accessible, no admin controls visible

### 1C: Compare Upload Flow (THE CRITICAL PATH)
`tests/e2e/audit/compare-flow.spec.js`

**IMPORTANT: Triage said compare "works, no fix needed" but Nolan experienced a clear failure.** The audit must determine exactly what happens from the USER's perspective, not just the backend's.

Test:
- Upload form present and functional
- Any feedback appears within 5 seconds after upload
- Results are visible in viewport without scrolling
- Results contain actual photo thumbnails
- Invalid file handling
- Large photo timeout behavior

### 1D: Photo Upload Flow
`tests/e2e/audit/upload-flow.spec.js`

Test the /upload page (admin-only, may need auth).

### 1E: Estimate Flow
`tests/e2e/audit/estimate-flow.spec.js`

- Page loads with face grid
- Correct face counts (not 0)
- Pagination works

### 1F: Admin Routes (authenticated)
`tests/e2e/audit/admin-routes.spec.js`

### 1G: Edge Cases
`tests/e2e/audit/edge-cases.spec.js`

---

## PHASE 2: Run the Audit (~20 min)

Run all tests serially (workers: 1) against production. Parse results into findings file.

Create `docs/ux_audit/session_findings/session_49b_audit.md` with categorized results.

---

## PHASE 3: Fix Critical + High Priority (~60 min)

Work through audit findings in priority order. For each fix:
1. Reproduce with specific Playwright test
2. Fix the code
3. Re-run that test to verify
4. Commit with descriptive message

After all fixes: re-run full audit, full pytest, push to main, verify production.

---

## PHASE 4: Documentation + Wrap Up (~10 min)

### 4A: Update findings file (mark FIXED items)
### 4B: Update session log with final results
### 4C: Update BACKLOG with unfixed items
### 4D: Update HARNESS_DECISIONS.md if new lessons
### 4E: Check for stderr=DEVNULL pattern across codebase
### 4F: Verification gate — re-read full prompt, cross-check every phase

---

## Do NOT:
- Run Playwright with workers > 1 against production
- Fix medium/low items before all critical+high are done
- Touch GEDCOM or birth year features
- Modify ML models or pipeline architecture
- Skip the diagnosis step and jump to fixing
- Mark a test as "passing" by weakening the assertion
