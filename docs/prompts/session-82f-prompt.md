# Session 82f Prompt: Completion Audit + Fix Everything

**Goal:** Exhaustively audit ALL work planned across Sessions 82a-82e. Verify what actually shipped, what's broken, what was silently dropped. Fix everything. Ship a complete, verified v0.86.0.

**Version:** v0.85.0 | ~2942 tests | 274 photos | 775 identities | 60 confirmed
**Date:** 2026-03-02
**Branch:** main (direct — this is a fix/completion session, not feature work)

---

## CRITICAL EXECUTION RULES

### Context Management (Non-Negotiable)
- **Run `/clear` after EVERY act commit.** No exceptions. No "context is fine." Session 80 compacted at 2% because of this exact rationalization.
- After `/clear`, re-read this prompt file: `cat docs/prompts/session-82f-prompt.md` and the current act section.
- After `/clear`, re-read session log: `cat docs/session_logs/session-82f-log.md` to restore state.
- If context exceeds 60%, STOP current work, commit, and `/clear` immediately.
- Use subagents with `isolation: "worktree"` for any research or implementation that touches >2 files.

### Testing Strategy
- `make test-fast` before every commit (parallel via pytest-xdist, <30s).
- Do NOT run `make test-full` until Act 4. It takes too long and blocks progress.
- Pre-existing failures to IGNORE (do not fix, do not let them block you):
  - `test_mls_score_range_exceeds_threshold` — ML regression, times out under parallel execution
  - `test_mobile_landing_page[chromium]` — 405px e2e overflow, tracked as UX-134
- If `make test-fast` fails on something NEW, fix it before continuing.

### Autonomous Execution
- This session runs overnight. Do not ask for user input. Make decisions and document them.
- If a fix is ambiguous, choose the simpler option and document the alternative in the assessment.
- If a feature is genuinely impossible (API key missing, infrastructure dependency), document it as BLOCKED and move on.
- You are NOT allowed to defer work to "82g." Everything completable MUST be completed here.

### Parallelization
- Phases 1-4 all touch `app/main.py`. Per Lesson 88, these MUST be sequential.
- Use subagents for: research, test writing, documentation, browser verification.
- Max 3 worktrees active at once.

### Hook Compliance
- **Stop hook**: Assessment file MUST exist at `docs/assessments/session-82f-assessment.md` before final commit
- **PreToolUse (Bash)**: `make test-fast` runs before git commit
- **PostToolUse (Edit|Write)**: AD reminder for ML/core file edits
- **UserPromptSubmit**: Parallelization reminder (already handled by this prompt's structure)

---

## Act 0: Orient + Full Audit (15 min)

### 0A: Session Setup
1. Read `CLAUDE.md`, `tasks/lessons.md`
2. Set `.claude/current_session.txt` to `82f`
3. Create session log: `docs/session_logs/session-82f-log.md`
4. Save this prompt (already at `docs/prompts/session-82f-prompt.md`)
5. Verify: `make test-fast` passes, git status clean, on main branch

### 0B: Exhaustive Feature Audit

Build a complete inventory of EVERY feature/fix planned across ALL session 82 phases. Cross-reference these source files:

| Source | File |
|--------|------|
| 82a ideation (30 ideas) | `docs/assessments/session-82a-ideation.md` |
| 82a top 5 proposals | `docs/assessments/session-82a-top-proposals.md` |
| 82a implementation plan | `docs/assessments/session-82a-implementation-plan.md` |
| 82b prompt (7 phases) | `docs/prompts/session-82b-prompt.md` |
| 82c prompt (5 phases) | `docs/prompts/session-82c-prompt.md` |
| 82d assessment | `docs/assessments/session-82d-assessment.md` |
| 82d archaeology (7 bugs) | `docs/session_context/session-82d-archaeology.md` |
| 82d verification log | `docs/screenshots/session-82d/VERIFICATION_LOG.md` |
| 82e prompt (7 phases) | `docs/prompts/session-82e-prompt.md` |
| 82e context (GREEN/YELLOW/RED) | `docs/session_context/session-82e-context.md` |
| 82e assessment | `docs/assessments/session-82e-assessment.md` |

For each feature/fix, categorize into one of:
- **SHIPPED** — Code on main, tests pass, verified in production
- **PARTIALLY SHIPPED** — Code exists but broken, untested, or incomplete
- **DROPPED** — Was in scope but never built
- **EXPLICITLY DEFERRED** — Consciously moved to backlog with documented reason
- **NOT IN SCOPE** — Was ideation/future, never intended for 82

Write the full inventory to `docs/session_context/session-82f-audit.md`.

### 0C: Known Issues from 82e Assessment "Next Session Should Verify"

These items from the 82e assessment MUST be checked:
1. Mobile hamburger at 375px viewport — visual rendering verification
2. Masonry grid lazy-loading behavior (pagination sentinels with column layout)
3. Share button clipboard fallback (Web Share API vs clipboard)
4. OG tag tests find INBOX/PROPOSED identity (not skip when CONFIRMED)
5. Landing page mystery faces: spec said "horizontal scroll" but implementation uses flex-wrap

### 0D: Known Issues from 82d Assessment "Next Session Should Verify"

These items from the 82d assessment MUST be checked:
1. Merge action from expansion panel
2. Close button (X) on expansion panel clears content
3. Public/non-admin visitors see full-page link (not HTMX) for Find Similar
4. Expansion panel animation smoothness

**Commit:** `docs: session 82f act 0 — full session 82 audit`
**Then: `/clear`**

---

## Act 1: Browser Verification — Find Everything That's Actually Broken (20 min)

Use Claude Chrome browser tools (admin is logged in) to systematically test the live app at `https://rhodesli.nolanandrewfox.com/`.

### 1A: Test Every Feature from 82d/82e

Navigate and screenshot each:

| Page | What to Test | Expected |
|------|-------------|----------|
| `/?section=to_review&view=browse` | Click "Find Similar" on a face card | Inline expansion panel opens with similar faces |
| `/?section=to_review&view=browse` | Face card design consistency | Cards match People section design |
| `/?section=confirmed&view=browse` | Find Similar works here too | Same inline expansion |
| `/?section=skipped&view=browse` | Find Similar works here too | Same inline expansion |
| `/people` | Face cards in people grid | Consistent design with admin sections |
| `/help` | Help Needed page loads | 50 face cards, quality badges, CTAs |
| `/photos` | Masonry grid renders | Multiple columns, natural aspect ratios |
| `/photo/{id}` (pick one with unidentified faces) | Identify Mode toggle | Dark overlay, pulse on unidentified faces, "?" badges |
| `/identify/{id}` (pick an INBOX identity) | OG tags in page source | og:title, og:image with R2 crop URL |
| `/identify/{id}` | Share button works | Copies URL or opens share dialog |
| Landing page (/) | Help section at bottom | "Help Identify People" + 6 mystery faces |
| Landing page — resize to 375px | Hamburger menu | Menu icon visible, slides from right, all links accessible |
| `/person/{id}` (pick one with many photos) | Photos/Faces toggle | Fast HTMX swap, no full page reload |
| `/person/{id}` | Share button on person page | Works, generates valid URL |

### 1B: Face Card Consistency Audit

The 82b prompt identified that face cards are inconsistent across sections. Check:
- Do face cards in `?section=to_review` look the same as cards in `/people`?
- Do all face cards have: face photo (large), name, confidence, action buttons?
- Are action buttons consistent? (Find Similar, Share, View Photo)
- Is there excessive whitespace or tiny face photos in any section?

Document every discrepancy found.

### 1C: Dead/Broken Links
- Click every navigation link from the hamburger menu
- Check all CTAs on the Help Needed page
- Verify "Find Similar" expansion panel actions (Compare, Not Same)
- Verify person page admin buttons (Edit Name, Find Similar, View in Admin)

### 1D: Screenshot Everything
Save screenshots to `docs/screenshots/session-82f/` with descriptive filenames.

Write findings to `docs/session_context/session-82f-browser-findings.md`:
```markdown
# Session 82f Browser Findings

## BROKEN (must fix)
| Issue | Page | Screenshot | Severity |
|-------|------|------------|----------|

## INCONSISTENT (should fix)
| Issue | Pages Affected | Screenshot |
|-------|---------------|------------|

## WORKING (confirmed)
| Feature | Page | Screenshot |
|---------|------|------------|
```

**Commit:** `docs: session 82f act 1 — browser verification findings`
**Then: `/clear`**

---

## Act 2: Fix All Broken Features (60-90 min)

Re-read: `cat docs/prompts/session-82f-prompt.md` (Act 2 section)
Re-read: `cat docs/session_logs/session-82f-log.md`
Re-read: `cat docs/session_context/session-82f-browser-findings.md`

For each BROKEN item found in Act 1, fix it. Work through them in priority order.

### 2A: Find Similar — Expected Behavior

The user reports that clicking "Find Similar" on a face card in `/?section=to_review&view=browse`:
1. Doesn't actually work
2. Face cards in this section don't match the design of face cards in People section

**Investigation steps:**
1. Read the Find Similar endpoint code: `grep -n "find-similar\|find_similar" app/main.py`
2. Read the face card rendering for `to_review` section vs `people` section
3. Identify why the HTMX expansion panel doesn't trigger
4. Identify the design discrepancy between card types

**Fix criteria:**
- Find Similar MUST work in ALL admin sections (to_review, confirmed, skipped)
- The expansion panel MUST open inline (not navigate away)
- Face cards MUST have consistent styling across all sections
- Each card MUST have: large face photo, name, actions (Find Similar, Share, View Photo)

### 2B: Fix Other Broken Items

For each item from the Act 1 browser findings marked BROKEN:
1. Read the relevant code
2. Write a fix
3. Write a test for the fix
4. Run `make test-fast`
5. Commit individually with descriptive message

### 2C: Fix Inconsistent Items

For each item marked INCONSISTENT:
1. Determine which version is correct (usually the one in `/people`)
2. Make the other sections match
3. Test and commit

### General Fix Guidelines
- Keep fixes minimal. Don't refactor surrounding code.
- Each fix gets its own commit: `fix(scope): description of what was broken and how it's fixed`
- Run `make test-fast` between every commit (the hook enforces this anyway)
- If a fix touches face card rendering, check ALL sections that render face cards

**After all fixes committed: `/clear`**

---

## Act 3: Fix Remaining GREEN Features from 82e Context (45-60 min)

Re-read: `cat docs/prompts/session-82f-prompt.md` (Act 3 section)
Re-read: `cat docs/session_logs/session-82f-log.md`
Re-read: `cat docs/session_context/session-82f-audit.md` (from Act 0)

The 82e context file listed these GREEN features. Check each against the audit inventory. If DROPPED (not EXPLICITLY DEFERRED), implement now:

### GREEN Features Checklist

| # | Feature | 82e Status | Action |
|---|---------|-----------|--------|
| 5 | Mobile Hamburger Menu Fix | SHIPPED (82e) | Verify only |
| 2 | Masonry Adaptive Grid | SHIPPED (82e) | Verify only |
| 28 | Share for Help Button + OG Cards | SHIPPED (82e) | Verify only |
| 25 | Help Needed Page | SHIPPED (82e) | Verify only |
| 17 | Identify Mode Focus State | SHIPPED (82e) | Verify only |
| 22 | Click-to-Target AI Bounding Boxes | DEFERRED to 82f | **Evaluate: implement or formally defer with reasoning** |
| 21 | Missing Info Table View | DEFERRED to 82f | **Evaluate: implement or formally defer with reasoning** |
| 30 | One-Click Bulk Tag Confirmation | DEFERRED to 82f | **Evaluate: implement or formally defer with reasoning** |
| 19 | Relational Context Labels | DEFERRED to 82f | **Evaluate: implement or formally defer with reasoning** |

### Decision Framework for Deferred Features

For each deferred feature:
1. **Is it implementable tonight?** Check: do we have the data? Is the code path clear?
2. **Effort estimate?** Under 30 min = implement. Over 30 min = needs PRD per SDD rules.
3. **Does it need a PRD?** Per spec-driven-development rule, features >30 min need PRD. If yes, create the PRD and implement if time allows, or formally defer to backlog.
4. **Risk?** Does it touch critical paths (face cards, data writes, auth)?

### For Features You Implement

Per spec-driven-development rules:
1. Write brief PRD (can be inline in the commit if <30 min)
2. Write tests FIRST
3. Implement
4. Verify in browser
5. Commit

### For Features You Formally Defer

Write a BACKLOG entry with:
- Feature name and description
- Why deferred (effort, dependency, risk)
- What's needed to unblock
- Estimated effort
- Link to 82a ideation source

**Commit per feature implemented or deferred.**
**After all done: `/clear`**

---

## Act 4: 82b and 82c Audit — What Was Lost? (20 min)

Re-read: `cat docs/prompts/session-82f-prompt.md` (Act 4 section)
Re-read: `cat docs/session_logs/session-82f-log.md`

### 4A: Session 82b (Codex — Face Cards)

82b was assigned to OpenAI Codex. Check what it produced:

```bash
git log --oneline --all --grep="82b" | head -20
git branch -a | grep 82b
```

The 82b prompt specified 7 phases:
1. Archaeology (find regression commit)
2. Fix face card layout (horizontal, large photos)
3. Fix Find Similar (inline panel admin, page public)
4. Fix sharing consistency (single share_button component)
5. Fix Photos/Faces toggle performance
6. Cross-site functionality audit
7. Documentation + PR

**Check:** Did ANY of this work land on main? If not, was it superseded by 82d's work?

82d appears to have addressed:
- Find Similar → inline expansion panel (AD-194)
- Photos/Faces toggle → HTMX partial swap (AD-195)
- Some bug fixes (P0 lazy-load, P1 admin buttons, P1 focus highlight)

**Gap analysis:** What from 82b's scope was NOT covered by 82d or 82e?

Likely gaps:
- Single reusable `face_card()` component (82d noted 14+ inline rendering locations still exist)
- Single reusable `share_button()` component (82d noted it exists but isn't used everywhere)
- Face card consistency across ALL sections (82d's assessment says "14+ face card rendering locations still use bespoke inline code")

If gaps exist that are fixable: fix them.
If gaps require major refactoring: create BACKLOG entry with specific scope.

### 4B: Session 82c (Claude Code — Gemini)

82c was assigned to Claude Code for Gemini re-run with GEDCOM enrichment.

```bash
git log --oneline --all --grep="82c" | head -20
git branch -a | grep 82c
```

The 82c prompt specified:
1. Asheville litmus test (3 GEDCOM variants)
2. Value assessment
3. Batch pipeline preparation
4. Surface results in app
5. Documentation

**Check:** Did any of this work happen? If not, document as DEFERRED with reason.

Note: 82c was explicitly separated from 82d/82e because it's ML pipeline work requiring API keys and real Gemini calls. If the work wasn't done, it should be formally moved to the ML backlog, NOT attempted here.

**Commit:** `docs: session 82f act 4 — 82b/82c gap analysis`
**Then: `/clear`**

---

## Act 5: Comprehensive Test + Deploy (25 min)

Re-read: `cat docs/prompts/session-82f-prompt.md` (Act 5 section)
Re-read: `cat docs/session_logs/session-82f-log.md`

### 5A: Full Test Suite
```bash
source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q
```

Both suites must pass. Known exceptions:
- `test_mls_score_range_exceeds_threshold` — pre-existing, OK to skip
- `test_mobile_landing_page[chromium]` — pre-existing, tracked as UX-134

### 5B: Deploy
```bash
git push origin main
```

Wait for Railway deploy. Check health endpoint:
```bash
curl -s https://rhodesli.nolanandrewfox.com/api/health | python3 -m json.tool
```

### 5C: Post-Deploy Browser Verification

Re-verify ALL fixes from Act 2 in production using Chrome browser:
- Find Similar works in to_review section
- Face cards consistent across sections
- All other broken items from Act 1 are now fixed
- Take screenshots as evidence

**Commit:** `test: session 82f act 5 — full verification`
**Then: `/clear`**

---

## Act 6: Session Documentation + Assessment (15 min)

Re-read: `cat docs/prompts/session-82f-prompt.md` (Act 6 section)
Re-read: `cat docs/session_logs/session-82f-log.md`

### 6A: Assessment

Write `docs/assessments/session-82f-assessment.md`:
```markdown
# Session 82f Assessment: Completion Audit

## Session 82 Full Scope Audit Results
| Feature | Source | Status | Evidence |
|---------|--------|--------|----------|
[... every feature from the 82a-82e scope ...]

## Shipped in 82f
- [list with evidence]

## Formally Deferred (with BACKLOG entries)
- [list with entry IDs]

## Browser Verification Results
| Check | Result | Screenshot |
|-------|--------|------------|

## Red Flags
- [severity] [description]

## Lessons Learned
- [any new lessons from this session]
```

### 6B: Update All Docs

1. `CHANGELOG.md` — Add v0.86.0 entry
2. `ROADMAP.md` — Update Recently Completed, check boxes
3. `docs/BACKLOG.md` — Update status for completed items, add new deferrals
4. `docs/ml/ALGORITHMIC_DECISIONS.md` — Any new AD entries
5. `docs/session_logs/session-82f-log.md` — Final status
6. `docs/sessions/SESSION_082f.md` — Session summary for stop hook
7. `docs/roadmap/SESSION_HISTORY.md` — Verify session 82 entries exist

### 6C: Dual-Update Rule Verification

Per `.claude/rules/dual-update-rule.md`:
- Every ROADMAP checkbox has a corresponding BACKLOG status update
- Every BACKLOG status change has a ROADMAP reference
- SESSION_HISTORY.md has entries for sessions 82a-82f

### 6D: Final Commit
```
docs: session 82f — assessment, changelog v0.86.0
```

---

## Master Feature Inventory (Reference)

This is the complete list of everything planned across Session 82. Use this to build the audit in Act 0.

### From 82a Ideation (30 ideas)
1. Global Command Palette
2. Masonry Adaptive Grids ← SHIPPED 82e
3. "Surprise Me" Module
4. Power-User Keyboard Shortcuts
5. Robust Mobile Hamburger Menu ← SHIPPED 82e
6. Interactive Radial Family Tree ← ALREADY EXISTS (Sessions 75-81)
7. "Recently Viewed" Breadcrumb Trail
8. Advanced Filtering Sidebar
9. Infinite Scroll
10. Persistent Visual Breadcrumbs
11. Before & After Enhancement Slider
12. Audio Narrative Snippets
13. Historical Context Sidebar
14. Integrated LifeStory Vertical Timelines ← PARTIALLY EXISTS (timeline page)
15. Inline Map View Toggle ← ALREADY EXISTS (Session 81)
16. Ken Burns Slideshows
17. "Identify Mode" Focus State ← SHIPPED 82e
18. Semantic Pin Drops
19. Relational Context Labels ← GREEN, DEFERRED to 82f
20. "On This Day" Module
21. "Missing Info" Table View ← GREEN, DEFERRED to 82f
22. Click-to-Target AI Bounding Boxes ← GREEN, DEFERRED to 82f
23. Contributor Gamification Profile
24. "Low Confidence" Suggestion Mode
25. Help Needed Landing Page ← SHIPPED 82e
26. Categorized AI Rejection Reasons
27. "Guess Who?" Micro-Interactions
28. Share for Help Button ← SHIPPED 82e
29. Contextual Discussion Threads
30. One-Click Bulk Tag Confirmation ← GREEN, DEFERRED to 82f

### From 82b Prompt (Face Cards — Codex)
- B1: Archaeology — find face card regression commit
- B2: Fix face card layout (horizontal, large photos, less whitespace)
- B3: Fix Find Similar (inline admin panel, shareable public page)
- B4: Fix sharing consistency (single share_button everywhere)
- B5: Fix Photos/Faces toggle performance
- B6: Cross-site functionality audit
- B7: Documentation + PR

### From 82c Prompt (Gemini — Claude Code)
- C0: Gemini state audit
- C1: Asheville litmus test (3 GEDCOM variants)
- C2: Value assessment + batch decision
- C3: Batch pipeline preparation
- C4: Surface results in app
- C5: Documentation + PR

### From 82d Delivered
- D-P0: Lazy-load face counts fix ← SHIPPED
- D-P1a: Person page admin button differentiation ← SHIPPED
- D-P1b: Focus mode face highlight fix ← SHIPPED
- D-P4: Inline Find Similar expansion panel (AD-194) ← SHIPPED
- D-P5: Person page gallery HTMX toggle (AD-195) ← SHIPPED
- D-P6: Visual modernization CSS ← SHIPPED

### From 82d Deferred
- Face card consistency audit (14+ inline rendering locations)
- Cross-site regression audit (not done in browser)

### From 82e Delivered
- E1: Mobile hamburger (768px breakpoint) ← SHIPPED
- E2: Masonry photo grid (CSS columns) ← SHIPPED
- E3: Help Needed page + OG cards + landing section ← SHIPPED
- E4: Identify Mode focus state ← SHIPPED

### From 82e "Next Session Should Verify"
- Mobile hamburger at 375px (visual rendering)
- Masonry grid lazy-loading with pagination sentinels
- Share button clipboard fallback
- OG tag test for INBOX/PROPOSED identity
- Landing page mystery faces: horizontal scroll vs flex-wrap

### From 82d "Next Session Should Verify"
- Merge action from expansion panel
- Close button (X) on expansion panel
- Public/non-admin Find Similar link (not HTMX)
- Expansion panel animation smoothness

---

## Session Log Template

```markdown
# Session 82f Log
Started: [timestamp]
Prompt: docs/prompts/session-82f-prompt.md

## Act Checklist
- [ ] Act 0: Orient + Full Audit
- [ ] Act 1: Browser Verification — Find Broken Features
- [ ] Act 2: Fix All Broken Features
- [ ] Act 3: Fix Remaining GREEN Features
- [ ] Act 4: 82b/82c Gap Analysis
- [ ] Act 5: Test + Deploy + Verify
- [ ] Act 6: Documentation + Assessment

## Act Progress
### Act 0
- Started:
- Completed:
- Findings:

### Act 1
- Started:
- Completed:
- BROKEN count:
- INCONSISTENT count:
- WORKING count:

### Act 2
- Started:
- Completed:
- Fixes shipped:

### Act 3
- Started:
- Completed:
- Features implemented:
- Features formally deferred:

### Act 4
- Started:
- Completed:
- 82b gaps:
- 82c status:

### Act 5
- Started:
- Completed:
- Test results:
- Deploy status:
- Verification results:

### Act 6
- Started:
- Completed:
```

---

## Scope Control

**In scope:**
- Everything broken from 82d/82e
- GREEN features deferred to 82f (evaluate and implement or formally defer)
- 82b/82c gap analysis
- All "Next Session Should Verify" items from 82d and 82e
- Full documentation and harness compliance

**Out of scope (do NOT touch):**
- ML pipeline code (face detection, embeddings, CORAL)
- Gemini API calls (requires key + budget approval)
- Data migrations or schema changes
- YELLOW/RED features from 82e context
- Any feature that requires infrastructure changes (custom SMTP, CI/CD, Sentry)

---

## Key References

| File | Purpose |
|------|---------|
| `docs/prompts/session-82f-prompt.md` | This file — re-read after every `/clear` |
| `docs/session_logs/session-82f-log.md` | Session progress — re-read after every `/clear` |
| `docs/session_context/session-82f-audit.md` | Feature inventory (created in Act 0) |
| `docs/session_context/session-82f-browser-findings.md` | Browser test results (created in Act 1) |
| `docs/assessments/session-82e-assessment.md` | 82e's "Next Session Should Verify" list |
| `docs/assessments/session-82d-assessment.md` | 82d's "Next Session Should Verify" list |
| `docs/session_context/session-82d-archaeology.md` | 7 bugs cataloged in 82d |
| `docs/session_context/session-82e-context.md` | GREEN/YELLOW/RED feature ranking |
| `CLAUDE.md` | Project rules and references |
| `tasks/lessons.md` | 99 lessons — read at session start |
