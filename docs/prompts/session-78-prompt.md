# Session 78: Integration + Fix-Everything Session

Read CLAUDE.md. Read .claude/rules/*.md (all rules).
Read docs/ml/ALGORITHMIC_DECISIONS.md (last 30 lines for AD-179+).
Read docs/assessments/session-75-assessment.md.
Read docs/assessments/session-76a-assessment.md.
Read docs/session_logs/session_77_assessment.md.
Read docs/session_logs/session_77_audit.md.
Read BACKLOG.md. Read ROADMAP.md.

## Session Identity
- **Previous sessions:** 75 (cleanup), 76a (clustering/UX), 77 (compare)
- **Goal:** Close EVERY open thread from sessions 75-77. No new features.
  Fix what's broken, verify what's unverified, delete what's dead.
- **Time budget:** ~2.5 hours (8 tracks, parallelized)
- **Priority:** CRITICAL — accumulated technical debt is blocking progress

## CONTEXT — WHAT'S BROKEN

Three sessions ran. All shipped code. None fully verified their work.
Here is the complete list of outstanding issues:

### From Session 75
1. Stop hook is broken — "Failed with non-blocking status code: No 
   stderr output." Assessment was skipped because of this.
2. ML test `test_mls_score_range_exceeds_threshold` fails — undiagnosed
3. GEDCOM→Supabase sync missing — production tree shows 24 people,
   local data has 718. This is a 97% visibility gap.

### From Session 76a
4. Backfill produced 0 Tier 1 matches — Big Leon (face 768, dist 1.13+)
   and Nace (face 767, dist 1.18+) STILL don't cluster. The pipeline 
   built to solve this problem doesn't solve it. Thresholds may be too
   conservative.
5. 57 duplicate face IDs — faces exist in BOTH confirmed clusters AND
   inbox. dedup_inbox() misses them because it requires ALL faces to
   match. This inflates inbox count and creates UX confusion.
6. No production deploy or browser verification was done
7. Browse card face sizing changes not visually verified
8. Discoveries page not visually verified
9. ML test `test_only_matched_individuals` fails (20 rels where 0 expected)
10. Test count discrepancy: 75 reported 3216, 76a reports ~3742 (+526
    unexplained by the 15 new tests)
11. PRD/SDD skipped for auto-clustering (prompt requested, session cut)

### From Session 77 (Codex)
12. Pre-existing `test_compare_photos_tab_has_face_overlays` failure
13. Compare uploads untested against running server
14. Compare pair enrichment (archive matches) not browser-verified
15. Scope was ~25% of requested rebuild — broader compare UX still poor

### Cross-Cutting
16. Three different ML tests failing across 3 sessions — portfolio risk
17. No visual verification done in ANY of the three sessions
18. Stop hook enforcement gap — sessions complete without assessments

---

## EXECUTION STRATEGY

Eight parallel tracks via worktrees + subagents. Each track is 
independent. Merge after all complete. /clear between every track.

```
Track 1: harness-fix     — Stop hook + test count audit (on main, first)
Track 2: ml-test-fix     — Diagnose and fix all 3 failing ML tests
Track 3: dedup-fix       — Fix 57 duplicate face IDs + threshold analysis
Track 4: gedcom-sync     — Sync GEDCOM relationships to Supabase
Track 5: deploy-verify   — Push to production + Claude Chrome visual audit
Track 6: compare-verify  — Browser-test compare uploads + pair enrichment
Track 7: docs-cleanup    — PRD for auto-cluster, AD renumbering, test count
Track 8: self-assess     — Automatic assessment + follow-up fixes
```

**Dependency order:**
- Track 1 runs FIRST on main (fixes infrastructure for other tracks)
- Tracks 2, 3, 4, 7 run in parallel (independent code areas)
- Track 5 runs AFTER 2+3+4 merge (needs all fixes before deploy)
- Track 6 runs AFTER Track 5 deploy
- Track 8 runs LAST (evaluates everything)

---

## TRACK 1: HARNESS FIX (on main, ~10 min)

### 1A: Fix the Stop Hook

```bash
cat .claude/settings.json | python3 -m json.tool
# or
cat .claude/hooks.json 2>/dev/null || echo "No hooks file found"
```

Read the current stop hook configuration. The error was:
"Stop hook error: Failed with non-blocking status code: No stderr output"

Root causes to investigate:
- Is the hook checking for assessment file existence?
- Does the hook script have correct exit codes?
- Is jq available? Is the JSON parsing working?

Fix the hook so it:
1. Checks if `docs/assessments/session-NN-assessment.md` exists
2. Exits with error code 1 (blocking) if missing
3. Prints a clear message: "BLOCKED: Assessment file missing"
4. Works with the current session number (parse from git log or prompt)

Test the hook manually:
```bash
# Should fail (no session 78 assessment yet)
bash .claude/hooks/stop_hook.sh 2>&1
echo "Exit code: $?"
```

### 1B: Audit Test Count

```bash
# Get true test counts
python -m pytest tests/ --co -q 2>&1 | tail -3
python -m pytest rhodesli_ml/tests/ --co -q 2>&1 | tail -3
```

Record the actual numbers. Three sessions report three different totals:
- Session 75: 3216 total
- Session 76a: 3205 app + 537 ML = 3742
- Post-merge: 3204 app + 386 ML = 3590
The ML count dropped by 151 between 76a and the merge. Investigate:
are tests being excluded, deleted, or miscounted? Document the real 
count and the reason for each discrepancy.

Commit: `fix(harness): repair stop hook, audit test counts`

**→ /clear → Start parallel tracks**

---

## TRACK 2: ML TEST FIXES (worktree: ml-test-fix, ~20 min)

### 2A: Diagnose test_mls_score_range_exceeds_threshold

```bash
python -m pytest rhodesli_ml/tests/ -k "test_mls_score_range" -v --tb=long 2>&1
```

Read the test. Read the function it tests. Understand:
- What threshold is expected?
- What score range is actually produced?
- Is this a test bug (wrong assertion) or a code bug (wrong output)?
- Was this introduced by a specific session's changes?

Fix it. If the test expectation is wrong, update the test AND add 
a comment explaining the correct behavior. If the code is wrong, fix 
the code. Add AD entry for the decision.

### 2B: Diagnose test_only_matched_individuals

```bash
python -m pytest rhodesli_ml/tests/ -k "test_only_matched_individuals" -v --tb=long 2>&1
```

The error: "20 relationships found where 0 expected." This suggests 
the test expected a filtered result but got all relationships. Check:
- Is the test filtering by matched individuals correctly?
- Did the relationships.json data change (Session 75 merged 1019 rels)?
- Is the function returning unfiltered data?

Fix it.

### 2C: Diagnose test_compare_photos_tab_has_face_overlays

```bash
python -m pytest tests/ -k "test_compare_photos_tab_has_face_overlays" -v --tb=long 2>&1
```

This is a UI test. Check:
- What HTML does the compare tab actually render?
- Is the test checking for the right CSS classes/elements?
- Did Session 77's changes affect this markup?

Fix it.

### 2D: Run full ML test suite

```bash
python -m pytest rhodesli_ml/tests/ -v 2>&1 | tail -20
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -10
```

ALL tests must pass. Zero tolerance. This is a portfolio project.

Commit: `fix(ml): resolve 3 failing tests — [descriptions]`

---

## TRACK 3: DEDUP + THRESHOLD ANALYSIS (worktree: dedup-fix, ~25 min)

### 3-PRE: Define Acceptance Criteria (before any code)
Write to /tmp/track_3_acceptance.md:
- PASS: 57 duplicate face IDs reduced to 0 (or documented exceptions)
- PASS: Faces 768 and 767 either cluster OR analysis proves they shouldn't
- PASS: AD-179 updated with threshold justification from real data
- FAIL: Duplicates remain without explanation
- FAIL: Thresholds changed without per-identity distance analysis
- Tests: dedup count assertion, threshold boundary tests

### 3A: Fix per-face dedup

The current dedup_inbox() requires ALL faces of an inbox identity 
to match a confirmed identity. This misses 57 duplicates where 
individual faces exist in both states.

Read core/auto_cluster.py — find dedup_inbox().

Implement per-face dedup:
1. For each face in inbox identities, compute distance to ALL faces 
   in confirmed identities
2. If distance == 0.0 (exact match), the face is a duplicate
3. If ALL faces of an inbox identity are duplicates of the SAME 
   confirmed identity → merge (current behavior, keep)
4. If SOME faces are duplicates but not all → flag for review, log
5. Run dedup and report: how many of the 57 are resolved?

Update tests in tests/test_auto_cluster.py.

### 3B: Threshold Analysis for Big Leon + Nace

The pipeline was built to solve 768 (Big Leon) and 767 (Nace) not 
clustering. It failed — both are above Tier 2 ceiling of 1.10.

Investigate deeper:
```python
# For Big Leon's confirmed faces, compute ALL pairwise distances
# What's the max within-cluster distance?
# Is 1.13 actually within normal variation for this person?

# For Nace, same analysis
```

Questions to answer (write to /tmp/threshold_analysis.md):
1. What's the actual distance of face 768 to Big Leon's closest face?
2. What's the actual distance of face 767 to Nace's closest face?
3. What's the max within-cluster distance for Big Leon across all 
   his confirmed faces?
4. If Big Leon's max within-cluster is > 1.10, then the Tier 2 
   ceiling of 1.10 is provably too low for this person.
5. Should the threshold be per-identity (adaptive) rather than global?

Based on findings, either:
a) Raise Tier 2 ceiling (e.g., to 1.15 or 1.20) with justification
b) Implement per-identity adaptive thresholds
c) Document why 768/767 genuinely shouldn't cluster (different person?)

Update AD-179 with the analysis and any threshold changes.
Run backfill again if thresholds change.

Commit: `fix(clustering): per-face dedup + threshold analysis for 768/767`

---

## TRACK 4: GEDCOM→SUPABASE SYNC (worktree: gedcom-sync, ~30 min)

### 4-PRE: Define Acceptance Criteria (before any code)
Write to /tmp/track_4_acceptance.md:
- PASS: Supabase relationships count matches local (~1,019)
- PASS: Production /tree shows 718+ people after deploy (not 24)
- PASS: Sync script is idempotent (running twice produces same result)
- FAIL: Any data loss during sync (local data overwritten or truncated)
- FAIL: Production tree count unchanged after deploy
- Tests: sync idempotency, relationship count, identity count

### 4A: Understand the Current Gap

```bash
# What's in local relationships?
python3 -c "
import json
rels = json.load(open('data/relationships.json'))
print(f'Total local: {len(rels)}')
# Count by source
sources = {}
for r in rels:
    src = r.get('source', 'unknown')
    sources[src] = sources.get(src, 0) + 1
print(f'By source: {sources}')
"

# What's in Supabase relationships?
python3 -c "
from supabase import create_client
import os
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
result = sb.table('relationships').select('*', count='exact').execute()
print(f'Supabase relationships: {result.count}')
"
```

### 4B: Create Sync Script

Create `scripts/sync_gedcom_to_supabase.py`:
1. Read all relationships from data/relationships.json
2. For each relationship not in Supabase:
   - Insert with all fields (person1_id, person2_id, type, source, etc.)
   - Log the insert
3. Handle conflicts (upsert on composite key of person1+person2+type)
4. Print summary: inserted N, skipped M, errors K

### 4C: Sync GEDCOM Individuals

The tree page needs GEDCOM individuals in Supabase too, not just 
relationships. Check:
```bash
python3 -c "
import json
idents = json.load(open('data/identities.json'))
gedcom_people = [i for i in idents if i.get('source') == 'gedcom' or 
                 i.get('gedcom_xref')]
print(f'GEDCOM-sourced identities: {len(gedcom_people)}')
print(f'Confirmed: {len([i for i in idents if i.get(\"state\") == \"CONFIRMED\"])}')
"
```

If GEDCOM individuals aren't in Supabase, sync them too.

### 4D: Verify Production Tree Data

After sync, the startup code in supabase_data.py will pull from 
Supabase on next deploy. Verify:
```bash
# Simulate what startup does
python3 -c "
# Read from Supabase, count relationships
from supabase import create_client
import os
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
result = sb.table('relationships').select('*', count='exact').execute()
print(f'Supabase after sync: {result.count} relationships')
# Should be ~1019
"
```

Write tests for the sync script.

Commit: `feat(data): sync GEDCOM relationships + individuals to Supabase`

---

## TRACK 5: DEPLOY + VISUAL AUDIT (on main after merges, ~25 min)

**This track runs AFTER Tracks 2, 3, 4 merge to main.**

### 5A: Merge All Tracks

```bash
git checkout main
git merge ml-test-fix --no-ff -m "merge: Track 2 ML test fixes"
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -5
git merge dedup-fix --no-ff -m "merge: Track 3 dedup + threshold fix"
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -5
git merge gedcom-sync --no-ff -m "merge: Track 4 GEDCOM Supabase sync"
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -5
```

If any merge has test failures, fix before proceeding.

### 5B: Deploy

```bash
git push origin main
```

Wait for Railway deploy (check Railway logs or curl for 200).

### 5C: Visual Audit with Claude Chrome

**Primary method: Claude Chrome extension.**
If Claude Chrome is available, use it to navigate and screenshot 
every page listed below. If not available, fall back to Playwright:

```bash
pip install playwright --break-system-packages
playwright install chromium
```

**Pages to audit (take screenshot of each, evaluate against UX rules):**

1. **/ (Homepage)** — Does it load? Version visible?
2. **/photos** — Browse cards: are faces 200px min? Hover actions work?
3. **/people** — People grid renders?
4. **/tree** — How many people visible? Should be 718+ after GEDCOM sync.
   If still 24, the sync didn't work end-to-end.
5. **/tree?person=[Big Leon UUID]** — Does Big Leon's tree render 
   with family connections?
6. **/discoveries** — Two-tier layout? 7 Tier 2 suggestions showing?
   Tier borders (emerald/blue) correct?
7. **/compare** — Upload zone renders? "Compare Two Photos" layout?
8. **/compare/pair** — Photo A/B drop zones? "Compare Selected Faces" 
   button?
9. **/connect** — Does it render or still Internal Server Error?
10. **/map** — Does it render or still Internal Server Error?
11. **/estimate** — Does it render?

**For each page, evaluate against .claude/rules/ux-evaluation.md:**
1. Can a community member take action from this page?
2. Is there a clear path to the next action?
3. Does it look professional or broken?
4. Mobile viewport (375px wide) — does it render acceptably?

Save screenshots to `docs/session_context/session_78_screenshots/`.
Write findings to `docs/session_context/session_78_ux_evaluation.md`.

### 5D: Fix Quick Wins

Any UX issues that are < 5 min to fix: fix them now.
CSS spacing, broken links, missing images, wrong text.
Commit after each quick fix.

Commit: `fix(ux): visual audit fixes — [descriptions]`

---

## TRACK 6: COMPARE VERIFICATION (after Track 5 deploy, ~15 min)

### 6-PRE: Define Acceptance Criteria (before any testing)
Write to /tmp/track_6_acceptance.md:
- PASS: Single photo upload → faces detected → archive matches shown
- PASS: Pair compare → score + archive context for both faces
- PASS: Shareable result URL works for unauthenticated user
- PASS: Upload persisted in pending_uploads (auto-queue working)
- FAIL: Any upload silently fails or returns error
- FAIL: Pair compare shows no archive matches (Session 77 regression)
- Tests: Playwright/Chrome screenshots of each flow step

### 6A: Test Compare Upload End-to-End

Using Claude Chrome or Playwright:
1. Navigate to /compare
2. Upload a test photo (use any photo from data/photos/)
3. Verify: faces detected, archive matches displayed, confidence labels shown
4. Verify: upload persisted (check pending_uploads.json or Supabase)
5. Verify: loading indicator appears during processing

### 6B: Test Pair Compare End-to-End

1. Navigate to /compare/pair
2. Upload Photo A (any photo with faces)
3. Upload Photo B (different photo with faces)
4. Select one face from each
5. Click "Compare Selected Faces"
6. Verify: similarity score displayed
7. Verify: archive matches shown for both faces (Session 77 feature)
8. Verify: bridge CTAs to archive/help-identify present

### 6C: Test Shareable Results

1. Complete a compare flow
2. Get the shareable result URL
3. Open it in a new incognito context
4. Verify: result renders for unauthenticated user

Log all results to `docs/session_context/session_78_compare_test.md`.

If any test fails, fix the issue and re-test.

Commit: `fix(compare): end-to-end verification fixes`

---

## TRACK 7: DOCS CLEANUP (worktree: docs-cleanup, ~15 min)

### 7A: Auto-Clustering PRD

The prompt for 76a requested a PRD/SDD for auto-clustering. It was 
skipped. Create it now:

Create `docs/prds/024_auto_clustering.md`:
- Problem: inbox faces accumulate without matching to confirmed identities
- Solution: two-tier automatic clustering pipeline
- Thresholds: Tier 1 < 0.85 (auto-add), Tier 2 0.85-1.10 (suggest)
- Data flow: upload → detect → embed → compare → cluster/suggest
- Active learning: confirm/reject signals feed back to calibration
- Acceptance criteria: dedup runs, Tier 1 auto-adds, Tier 2 shows in Discoveries

### 7B: AD Renumbering Verification

The merge session already renumbered: 77's AD-179→AD-181, AD-180→AD-182.
VERIFY (don't redo) that the file is clean:
- AD-179 = auto-clustering thresholds (76a)
- AD-180 = (76a)
- AD-181 = pair-compare archive-context (77)
- AD-182 = compare pipeline decisions (77)
- No duplicate AD numbers
- No orphan references to old numbers in code comments or docs

### 7C: Update ROADMAP + BACKLOG

Read both files. Update with:
- Sessions 75-77 marked complete
- Session 78 in progress
- Outstanding items added to BACKLOG with breadcrumbs:
  - GEDCOM sync follow-up (verify production tree count)
  - Compare full rebuild (77 only did 25% of scope)
  - Per-identity adaptive thresholds (if Track 3 analysis supports)
  - /connect and /map internal server errors (if still broken)

Verify: ROADMAP.md < 150 lines. No docs file > 300 lines.

Commit: `docs: PRD-024 auto-clustering, AD renumber verify, ROADMAP+BACKLOG sync`

---

## TRACK 8: SELF-ASSESSMENT + AUTO-FIX (on main, LAST, ~20 min)

**This is the "automatic B session" pattern. It runs after all other
tracks are merged and deployed.**

### 8A: Re-Read Original Prompt

```bash
cat docs/prompts/session-78-prompt.md
```

For every track, verify:
- Was it completed? (grep for expected artifacts)
- Was it tested? (check test output, screenshots, curl results)
- Were there silent deferrals?

### 8B: Run Full Test Suite

```bash
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -10
python -m pytest rhodesli_ml/tests/ -v 2>&1 | tail -20
```

ZERO failures allowed. If any test fails, fix it before proceeding.

### 8C: Production Smoke Test

```bash
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/photos
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/tree
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/discoveries
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/compare
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/compare/pair
```

All should return 200. Any non-200 is a red flag to investigate.

### 8D: Critical Questions Assessment

Answer each question with evidence (not claims):

**Red Flags:**
1. Are there any failing tests? (paste test output)
2. Are there any routes returning non-200? (paste curl output)
3. Did any track silently skip work? (diff prompt vs. delivered)
4. Is the stop hook working now? (test it)
5. How many people on the production tree? (screenshot or count)
6. Are the 57 duplicate faces resolved? (query count)
7. Do 768/767 cluster now? (query their status)

**Concerns:**
8. Is the test count consistent with reality? (paste --co count)
9. Are all AD entries numbered correctly with no collisions?
10. Are ROADMAP and BACKLOG in sync and under line limits?

**UX Status:**
11. Does every audited page look professional? (reference screenshots)
12. Are there any "Internal Server Error" pages remaining?
13. Does mobile viewport render acceptably?

### 8E: Auto-Fix Red Flags

For each red flag found in 8D:
- If fixable in < 10 min: fix it NOW
- If not fixable: add to BACKLOG as P0 with full breadcrumb

### 8F: Write Assessment

Create `docs/assessments/session-78-assessment.md` following the 
template in `.claude/rules/self-assessment.md`.

Include:
- All shipped items with evidence
- All deferred items with reason and BACKLOG entry
- All red flags with severity
- Answers to all 13 questions from 8D
- Screenshot inventory (reference files in session_78_screenshots/)
- Next session recommendations

Also create `docs/session_context/session_78_ux_evaluation.md` with 
findings from Track 5's visual audit, following the template in 
`.claude/rules/ux-evaluation.md`.

### 8G: Verify Stop Hook Works on This Session

Before declaring session complete, deliberately trigger the stop hook:
```bash
# Test that the hook would block without assessment
# (assessment should exist by now, so this should pass)
ls docs/assessments/session-78-assessment.md && echo "PASS" || echo "FAIL"
```

Commit: `docs: session 78 assessment, UX evaluation, auto-fix results`

---

## FINAL: Push + Close

```bash
git push origin main
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -5
echo "Session 78 complete. $(git log --oneline -1)"
```

---

## RULES (read these, follow them, no exceptions)

1. **This is FastHTML + HTMX.** No React. No Next.js. Server-rendered.
2. **Commit after every track.** Small, atomic commits.
3. **Run tests after every merge.** Zero failures tolerated.
4. **Never modify data/ files** unless the task specifically requires it
   (Track 3 dedup and Track 4 sync are exceptions — those DO touch data).
5. **Use /clear between tracks, NOT /compact.** Re-read from disk.
6. **Use Claude Chrome for visual testing** (Playwright as fallback).
7. **Update ALGORITHMIC_DECISIONS.md** for every non-trivial decision.
   Include: what was decided, why, what was rejected, source.
8. **No docs file > 300 lines. ROADMAP.md < 150 lines.**
9. **Do NOT add new features.** This session is fix + verify only.
10. **The stop hook must pass before session ends.** If it doesn't, 
    that's the FIRST thing to fix.
11. **Use subagents for independent investigation work** — ML test 
    diagnosis, threshold analysis, and doc writing can all run as 
    background agents while the main thread handles merges.
12. **Save this prompt to docs/prompts/session-78-prompt.md** at the 
    start of the session.
