# Session 49D: P0 + P1 Bug Fixes with Visual Verification

Read CLAUDE.md. Read docs/session_protocols/overnight.md.
Read docs/session_context/session_49b_browser_automation_context.md.
Read .claude/rules/verification-gate.md.

## SESSION TYPE: Overnight (autonomous, no human available)

Save this prompt to docs/prompts/session_49d_prompt.md per overnight protocol.

## Goal
Fix 6 P0 bugs and 6 P1 bugs from Session 49B. Visually verify every
fix using the Chrome extension. Log any additional issues discovered
during verification screenshots.

Total: 12 fixes. Estimated time: 60-90 min.

## Key References (read these, don't duplicate their content)
- Full bug details: docs/ux_audit/UX_ISSUE_TRACKER.md
- Root cause context: docs/session_context/session_49b_interactive_log.md
  (Sections 3 and 6 have the most detail on identity tagging + Name
  These Faces bugs)
- Data divergence warning: tasks/lessons.md Lesson 78
- ML serving contract: docs/ml/ALGORITHMIC_DECISIONS.md → AD-110

## Browser Verification Protocol
Start this session with `claude --chrome`. After EVERY fix:
1. Navigate to the affected route using Chrome extension
2. Screenshot the fix in action → save to docs/browser_audit/screenshots/
   Naming: `49d_[UX-ID]_[route]_[state].png`
3. While screenshotting, **actively look for additional issues** —
   layout problems, broken elements, console errors, anything unexpected
4. Log any NEW issues to docs/ux_audit/UX_ISSUE_TRACKER.md as UX-103+
   with `📋 BACKLOG` disposition and `(Found during S49D verification)` note

If Chrome extension is not available, fall back to Playwright MCP per
the browser automation context file. Log which tool was used.

---

## PHASE 0: Orient (~5 min)

Verify starting test count. All must pass before we begin.

### Data Sync Check
Read Lesson 78 in tasks/lessons.md. Production has data from
Session 49B Sections 1-3 (birth years, GEDCOM, identity tagging)
that local may not have.

Review the dry-run. If it shows data to pull, run without --dry-run.
Do NOT proceed with code changes until data is synced.

### Browser Connection Test
If connection fails, follow troubleshooting in
docs/session_context/session_49b_browser_automation_context.md
(max 3 minutes). Fall back to Playwright if needed.

Commit: `chore: session 49D orient — data synced, browser connected`

---

## PHASE 1: P0 Fixes — Core Workflow Blockers (~25 min)

Read UX_ISSUE_TRACKER.md sections for UX-036, UX-070-072, UX-044/052.
Read session_49b_interactive_log.md Section 3 (identity tagging)
and Section 6 (Quick-Identify test) for root cause details.

### 1A: UX-036 — Merge Button 404
Session log says: `focus_suffix` starts with `&` not `?` at app/main.py:5780.
Fix, add test, then visually verify.

### 1B: UX-070/071/072 — Name These Faces Broken (shared root cause)
Session log Section 6 says: `hx_target="#photo-modal-content"`
doesn't exist on /photo/ pages. Only exists in lightbox modal.
Fix must work on BOTH /photo/ direct pages AND lightbox modal.
Done button must work regardless of context.

### 1C: UX-044/052 — Uploads Not Queued / Misleading Message
Read AD-110 (Serving Path Contract) first. If AD-110 says uploads
are ephemeral (not persisted), the fix is MESSAGING, not queuing.

Commit after phase.

---

## PHASE 2: P1 Fixes — High-Value Quick Wins (~30 min)

### 2A: UX-092 — Birth Year Save Edit Race Condition
### 2B: UX-080 + UX-081 — 404 Page and About Page Templates
### 2C: UX-042 — /identify/ Page Missing Source Photo Link
### 2D: UX-100 + UX-101 — Birth Year Review Page Polish

Commit after phase.

---

## PHASE 3: Update Harness Files (~10 min)

Update: UX_ISSUE_TRACKER.md, ALGORITHMIC_DECISIONS.md, BACKLOG.md,
ROADMAP.md, CHANGELOG.md, session log, tasks/lessons.md

---

## PHASE 4: Deploy + Verify (~5 min)

Push code only (no data/ files). Smoke test production.

---

## PHASE 5: Verification Gate (MANDATORY)

Re-read prompt. Verify every deliverable. All tests pass. Gate results logged.
