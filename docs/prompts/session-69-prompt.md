# Session 69 Prompt
## Mission: Fix broken user loop + design audit + discovery notifications + parallelization skill
## Predecessor: Session 68 (v0.73.1 — hook hardening, LoRA audit, UX-103)
## Context: docs/session_context/session-69-context.md
## Rule: /clear between phases, NEVER /compact

---

## Pre-Session Manual Tasks (Nolan does BEFORE launching session)

1. **Railway deploy**: Check webhook config. Manually trigger deploy if broken. Verify session 68 commits (UX-103) are live.
2. **`run_session.sh` test**: Run outside Claude session. Note what breaks.
3. **LoRA identity review**: In admin, review Vida, Big Leon, Victor. Confirm or reject.

---

## Phase 0: Archive + Orient (10 min)
- [ ] Read: CLAUDE.md, docs/session_context/session-69-context.md, ROADMAP.md, LESSONS_LEARNED.md, ALGORITHMIC_DECISIONS.md (head), HARNESS_DECISIONS.md (head)
- [ ] Archive session 68 log to docs/session_logs/
- [ ] Update INDEX.md
- [ ] Set .claude/current_session.txt to "69"
- [ ] Create SESSION_LOG.md for session 69
- [ ] Confirm Railway deploy status
- [ ] Review parallel-optimizer subagent (.claude/agents/parallel-optimizer.md) — assess current capabilities

## Phase 1: Fix BUG-1 — Create Identity [P0] (15 min)
- [ ] Open browser console, reproduce the "Create [Name]" click — capture error
- [ ] Trace click handler in Photo Context modal code (likely app/static/js/ or inline in template)
- [ ] Identify root cause: dead handler? failed POST? missing route?
- [ ] Fix the root cause
- [ ] Add integration test: "creating a new identity from photo context modal succeeds"
- [ ] Verify fix locally (curl or test)
- [ ] AD entry: document bug, root cause, fix

## Phase 2: Diagnose + Fix BUG-2 — Clustering Pipeline [P0] (15 min)
- [ ] Trace post-upload pipeline: upload → face detection → embedding → clustering → matching
- [ ] Determine: is auto-clustering intentionally disabled (Gatekeeper) or broken?
- [ ] If Gatekeeper by design:
  - [ ] Document in AD entry with full rationale
  - [ ] The notification system (Phase 4 subagent) will address the UX gap
- [ ] If broken:
  - [ ] Reconnect clustering to Supabase backend
  - [ ] Test: upload a photo, verify face gets cluster assignment
- [ ] Either way: ensure the review UX makes high-confidence matches obvious and one-click confirmable
- [ ] AD entry: document pipeline architecture, decision, and rationale

## Phase 3: Fix BUG-3 — Collection Dropdown [P1] (10 min)
- [ ] Find collection dropdown on photo detail page
- [ ] Compare with upload flow's collection picker — identify data source difference
- [ ] Wire photo detail dropdown to same data source (all existing collections)
- [ ] Test: existing collections appear in dropdown on photo detail page
- [ ] AD entry if needed

## /clear — Read context file + SESSION_LOG before continuing

## Phase 4: Parallel Execution (30 min)

Three worktree-isolated subagents. All start AFTER Phase 3 merges to avoid app/main.py conflicts.

### Subagent A: Design Audit + Face Card Redesign
**Worktree:** `session-69/design-audit`
**Context to load:**
- /mnt/skills/public/frontend-design/SKILL.md (MANDATORY — read first)
- docs/session_context/session-69-context.md section 1 (DESIGN-1) and section 3
- Current CSS files and templates for face cards, photo detail, browse views

**Tasks:**
- [ ] Audit current site against frontend-design skill principles
- [ ] Identify top 5 design improvements (prioritize face cards, photo detail page)
- [ ] Implement improvements following "editorial archival" aesthetic:
  - Warm, respectful of historical content
  - Museum exhibition catalog feel
  - Serif display fonts for headings
  - Parchment/cream accents, subtle shadows evoking physical photographs
- [ ] Fix single-photo face card wasted space
- [ ] Create docs/DESIGN_DECISIONS.md with DD-001 (aesthetic direction), DD-002 (face card layout)
- [ ] Update CLAUDE.md key docs table to include DD file
- [ ] Write tests for any layout changes

### Subagent B: Discovery Notification System
**Worktree:** `session-69/notifications`
**Context to load:**
- docs/session_context/session-69-context.md section 2 (notifications)
- Current app/main.py routes for matching/review
- Gatekeeper pattern documentation

**Tasks:**
- [ ] Create discovery detection: when a face has HIGH confidence match (Dist < 1.0) to a CONFIRMED identity, flag as "discovery"
- [ ] Add sidebar badge: "N New Discoveries" (distinct from existing "New Matches")
- [ ] Create /discoveries route showing: new face, confirmed match, confidence score, one-click confirm/reject
- [ ] Wire into existing Gatekeeper approval flow
- [ ] Write tests for discovery detection + route
- [ ] DD-003 entry: discovery notification UX decisions

### Subagent C: Harness + Parallelization Skill
**Worktree:** `session-69/harness`
**Context to load:**
- HARNESS_DECISIONS.md
- /mnt/skills/examples/skill-creator/SKILL.md (read for skill creation best practices)
- .claude/agents/parallel-optimizer.md (existing agent)
- Session 68 assessment (carryover items)

**Tasks:**
- [ ] Trim regression suite: define 5-item smoke test vs 15-item full regression
- [ ] Document: when to use smoke vs full (smoke = normal sessions, full = harness changes only)
- [ ] Create parallelization skill draft: .claude/skills/prompt-parallelizer/SKILL.md
  - Analyzes multi-phase prompts for parallel vs sequential dependencies
  - Identifies file-level conflicts between phases
  - Outputs dependency graph and suggested worktree plan
  - Auto-generates subagent context briefs
- [ ] Document 2 Gemini content-safety-blocked photos as case study material
  - Create docs/case_studies/content_safety_edge_cases.md
  - Frame: historical photo preservation vs modern content filters
- [ ] HD entry: parallelization skill rationale and design
- [ ] Remove run_session.sh as numbered phase — add to BACKLOG with "manual test only" tag

## /clear — Read context file + SESSION_LOG before continuing

## Phase 5: Merge + Test + Deploy (10 min)
- [ ] Merge design-audit worktree (CSS/template changes, no Python conflicts expected)
- [ ] Run test suite — verify no regressions
- [ ] Merge notifications worktree (new routes + new file)
- [ ] Run test suite — verify no regressions
- [ ] Merge harness worktree (docs only, no conflicts expected)
- [ ] Full test suite: should be 3064+ (new tests from all subagents)
- [ ] Clean up worktrees and branches
- [ ] Push to main
- [ ] Verify Railway deploy triggers
- [ ] Browser verify:
  - [ ] Create Identity flow works (BUG-1 fix)
  - [ ] Collection dropdown populated (BUG-3 fix)
  - [ ] Face cards look improved (design audit)
  - [ ] Discovery badge appears if any high-confidence matches exist
  - [ ] UX-103 from session 68 also visible (back nav, metadata overlay, mobile menu)

## Phase 6: Docs + Evaluation (10 min)
- [ ] Update: CHANGELOG.md, ROADMAP.md, BACKLOG.md
- [ ] Update: ALGORITHMIC_DECISIONS.md (all AD entries from this session)
- [ ] Update: HARNESS_DECISIONS.md (HD entries)
- [ ] Verify: DESIGN_DECISIONS.md created with DD-001 through DD-003
- [ ] Update: SESSION_LOG.md with all phase results
- [ ] Write: session-69-assessment.md (use session-evaluator subagent)
- [ ] Archive: session log to docs/session_logs/session-69-log.md
- [ ] Update: INDEX.md

---

## Success Criteria

**Must have:**
- BUG-1 fixed: Create Identity works from Photo Context modal
- BUG-2 diagnosed: either fixed or documented-as-designed with UX improvement plan
- BUG-3 fixed: Collection dropdown shows all collections
- DESIGN_DECISIONS.md created

**Should have:**
- Design audit with face card improvements shipped
- Discovery notification system (at least badge + basic view)
- Parallelization skill draft created
- Regression suite trimmed
- All deployed and browser-verified

**Nice to have:**
- Full editorial archival CSS pass across site
- Content safety case study documented
- Parallelization skill tested against this session's own prompt

---

## Naming Convention
- Prompt: session-69-prompt.md
- Context: session-69-context.md (copy to docs/session_context/)
- Log: SESSION_LOG.md (archived to docs/session_logs/session-69-log.md)

---

## MANDATORY RULES (from CLAUDE.md — repeated for emphasis)
- Update ALGORITHMIC_DECISIONS.md for every ML/algorithm decision
- Update DESIGN_DECISIONS.md for every UX/design decision (NEW — create if missing)
- Update HARNESS_DECISIONS.md for every workflow/tooling decision
- No doc file over 300 lines
- ROADMAP.md under 150 lines
- Deploy via git push, NOT Railway dashboard
- /clear between phases, NEVER /compact
- Commit after every phase
- Run smoke test after deploys
