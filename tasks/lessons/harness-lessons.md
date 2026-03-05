# Harness & Process Lessons

## Lesson 72: Context Degradation is Real
- **Mistake:** Session 47 later phases were claimed-but-not-wired (birth_year_estimates.json in wrong directory, BACKLOG breadcrumbs missing)
- **Rule:** Save long prompts to disk and re-read at verification time. ~20-30% performance drop with accumulated vs. fresh context.
- **Prevention:** .claude/rules/prompt-decomposition.md, .claude/rules/verification-gate.md

## Lesson 73: Data in Wrong Directory (3x Pattern)
- **Mistake:** Session 42 (Dockerfile), Session 46 (estimates display), Session 47 (birth year estimates) — data built in one directory but not copied to where app reads it
- **Rule:** Verification gate's "Deployed correctly?" check catches this systematically
- **Prevention:** .claude/rules/verification-gate.md "Common failure patterns"

## Lesson 74: Self-Reported Completion is Unreliable
- **Mistake:** Claude claiming "all features built" when 2/11 were not wired. Same model that produces phantom features cannot reliably verify its own work.
- **Rule:** External verification (test suites, Feature Reality Contract) is mandatory. Never trust "I completed all phases" without checking.
- **Prevention:** .claude/rules/feature-reality-contract.md, .claude/rules/verification-gate.md

## Lesson 75: Harness Decisions Need Provenance
- **Mistake:** Rules copied between sessions without understanding why they exist, leading to blind adherence or inappropriate removal
- **Rule:** HARNESS_DECISIONS.md (HD-NNN) captures WHY each rule exists, enabling replication and iterative improvement
- **Prevention:** docs/HARNESS_DECISIONS.md, .claude/rules/harness-decisions.md

## Lesson 76: Audits Have Blind Spots
- **Mistake:** Session 47B audit marked "Age on face overlays" as "NOT BUILT (not in scope)" — but it WAS explicitly in the prompt (Phase 2F). Audit compared against assumed scope, not actual prompt text.
- **Rule:** Always audit against the ACTUAL PROMPT TEXT, not what you think was in scope. This is why saving prompts to disk (HD-001) is critical.
- **Prevention:** .claude/rules/prompt-decomposition.md (save prompt), .claude/rules/verification-gate.md (re-read prompt)

## Lesson 86: Context Overflow in Long Sessions
- **Mistake:** Session 69 Phase 4 hit context limit and required continuation. Three parallel subagents each returned full transcripts, flooding the orchestrator context.
- **Rule:** Parallelization skill should estimate context budget per subagent. Subagent results should be summarized (not dumped wholesale). If >3 subagents, stagger execution.
- **Prevention:** Prompt-parallelizer skill should include context budget estimation. Orchestrator should use /clear between merging each subagent result.

## Lesson 87: Subagent Commit Discipline
- **Mistake:** Session 69 subagent A test file was not committed in worktree — had to be manually copied to main. Session 64 had a similar issue.
- **Rule:** Every subagent MUST run tests AND commit ALL files before completing. The orchestrator verifies `git status` shows clean working tree in each worktree before merge.
- **Prevention:** Added to parallelization skill anti-patterns and subagent completion criteria.

## Lesson 88: Monolithic App Files Prevent Parallel Worktree Execution
- **Mistake:** Session 71 planning identified that Track A (UX fixes) and Track B (GEDCOM integration) both need to modify `app/main.py` (~6000+ lines). Despite touching different sections, git merge cannot reliably resolve concurrent edits to the same file across worktrees. This forced Track A and B to run sequentially, reducing parallelization savings.
- **Rule:** Any two tracks that both modify the same monolithic file (especially `app/main.py`) MUST run sequentially, not in parallel worktrees. Only tracks with fully disjoint file sets (e.g., docs-only, scripts-only) can safely parallelize. The parallelization skill's "high-conflict files" list in `SKILL.md` is the authoritative reference.
- **Prevention:** When planning parallel tracks, check the file ownership map FIRST. If two tracks share ANY file in the high-conflict list (`app/main.py`, `CLAUDE.md`, `ROADMAP.md`, `CHANGELOG.md`, `SESSION_LOG.md`, data files), they must be sequential. Consider refactoring monolithic files into modules to enable future parallelization.

## Lesson 89: /clear Between Acts is Non-Negotiable — REPEAT OFFENDER (Sessions 80 AND 89)
- **Mistake (Session 80):** Prompt explicitly said "MANDATORY /clear between every Act." Instead of clearing, rationalized: "context is fine." Compacted at 2% remaining, forced session restart.
- **Mistake (Session 89):** SAME EXACT FAILURE despite this lesson existing. Ran all 5 acts without /clear, context compacted, user had to restart conversation. User called this a "big fuck up" and a trust violation. The lesson was written but not followed — proof that lessons alone are insufficient without mechanical enforcement.
- **Rule:** After EVERY act commit, the VERY NEXT action must be /clear. Not "read the next act first." Not "check something quickly." /clear IMMEDIATELY. No exceptions. No rationalizations.
- **Prevention:** (1) After git commit, type /clear BEFORE doing anything else. (2) If you find yourself thinking "I'll just do one more thing before clearing" — STOP. That thought is the bug. (3) Use subagents for heavy implementation to keep orchestrator lean. (4) If context is above 40%, /clear is OVERDUE.

## Lesson 77: Trimming Docs Without Verifying Destination Loses Context
- **Mistake:** Session 54c trimmed ROADMAP.md "Recently Completed" from 14 entries to 5, pointing to SESSION_HISTORY.md — but SESSION_HISTORY.md was missing sessions 47-54B. Session 47B (real audit session with 4 tests) was also never added. Context would have been silently lost if not caught.
- **Rule:** Before removing entries from ANY document, verify the destination file already contains equivalent content. "See [other file]" is only valid if you've confirmed the other file actually has the data.
- **Prevention:** Added to .claude/rules/verification-gate.md as a mandatory pre-trim check. When ROADMAP "Recently Completed" is trimmed, SESSION_HISTORY.md must be updated in the SAME commit.

## Lesson 97: Self-assessment must include visual verification evidence — "PASS" without screenshots is theater
- **Mistake:** Session 81 self-assessment declared "12/12 PASS" for browser verification, but 3 visually obvious issues (face label prefix, blank Leaflet map, 7-node tree instead of 17) were immediately found when the user actually looked. The verification checked "page returns 200" not "feature works visually." This is the same pattern the session-evaluator caught in Session 66 (Phases 4/5/6 self-assessed PASS but were actually PARTIAL).
- **Rule:** Every browser verification PASS must be backed by either (a) a screenshot saved to `docs/screenshots/session-NNx/`, or (b) a specific DOM query result proving the feature rendered correctly (e.g., "17 name labels found" not just "page loaded"). A 200 status code is necessary but NOT sufficient.
- **Prevention:** (1) Stop hook should check for screenshot evidence when browser verification is claimed. (2) For visual features (maps, trees, charts), verify element count/content, not just page load. (3) When self-assessing, ask "would this pass if someone else looked at the screen?" not "did the page load?"

## Lesson 98: UUID and ID fields must be validated before write — truncated IDs cause silent cascade failures
- **Mistake:** 21 entries in `data/gedcom_matches.json` had truncated 8-character identity IDs instead of full 36-character UUIDs (e.g., `fd43c9dd` instead of `fd43c9dd-8558-4305-8bda-90c3f320daac`). This caused tree lookups to silently fail — `_build_tree_person_lookup()` stored full UUIDs but the truncated keys never matched. The tree showed 7 nodes instead of 17, and the bug went undetected until manual Chrome verification.
- **Rule:** Any function that writes identity IDs or GEDCOM xrefs to data files must validate the format before write. UUIDs must be 36 chars with 4 hyphens. GEDCOM xrefs must match `@I\d+@`. Truncated or malformed IDs should raise an error, not silently persist.
- **Prevention:** (1) Add a `validate_identity_id(id)` helper that asserts UUID format. (2) Call it in any write path to `gedcom_matches.json`, `relationships.json`, or Supabase face links. (3) Add a data integrity test that scans all ID fields in data files for format compliance.

## Lesson 99: Session log + INDEX.md update must happen atomically with session completion
- **Mistake:** Session 81 completed across 4 sub-sessions (81/81B/81C/81D) with full assessments, but the session log file (`docs/session_logs/session-81-log.md`) was never created. The INDEX.md hadn't been updated since session 77 — sessions 75 through 80 were also missing from the index. The stop hook is supposed to enforce this but didn't catch it.
- **Rule:** Session log creation and INDEX.md update are part of the mandatory session outputs (alongside assessment). They must be committed in the same commit as the session assessment or immediately after.
- **Prevention:** (1) Add INDEX.md to the stop hook's checklist alongside assessment file. (2) When committing an assessment, always also commit the session log and INDEX update. (3) At session start, check that the PREVIOUS session's log exists in the index — backfill if missing.

## Lesson 100: Planning Sessions Must Create Session Artifacts BEFORE Implementation
- **Mistake:** Session 87 planning phase created the plan but initially missed creating the context file, prompt file, and session log. The /clear discipline, subagent strategy, and skill usage (ux-review, session-review) were also not included in the first plan draft. Existing rules describe WHAT to create but don't enforce WHEN.
- **Rule:** Every session plan MUST include: context file, prompt file, session log, /clear points, verification strategy, skills to invoke (ux-review, session-review), and subagent/worktree strategy. These must be created BEFORE implementation begins. Breadcrumbs (predecessor link, deferred work, decision IDs) are mandatory.
- **Prevention:** Validate this checklist before exiting plan mode. Consider `.claude/rules/planning-checklist.md` to enforce during plan mode.

## Lesson 96: Multi-layered rendering pipeline bugs require iterative fix-verify cycles — don't assume one fix is enough
- **Mistake:** Session 81B tree bug on photo fb6a846971b30f4b required 3 separate commits because the failure had 3 layers: (1) `compute_subtree_for_photo()` excluded disconnected people from `path_union`, (2) `if pid in lookup` filter silently dropped GEDCOM xrefs not in the lookup dict, (3) focal person wasn't in the returned node set so JS `buildHierarchy()` BFS started from nothing. Each fix only revealed the next layer. After fix 1, the API returned nodes but not the right ones. After fix 2, the API returned more nodes but still not the focal person. After fix 3, it finally worked.
- **Rule:** When fixing a data-to-rendering pipeline (API → JS → DOM), expect multiple failure layers. After EACH fix, verify the FULL pipeline end-to-end in Chrome (not just the API response). Don't commit + push + move on after fixing one layer — the next layer may be hiding. Budget time for iterative debugging.
- **Prevention:** (1) After fixing a rendering pipeline bug, test in Chrome immediately (before committing if possible) to see if the fix is sufficient. (2) Add logging at each pipeline stage (API response shape, JS nodeMap contents, SVG element count) so you can see exactly where the pipeline breaks. (3) For multi-person tree bugs specifically: always verify focal person is in the node set, node count matches expected, and BFS can reach all nodes from the focal point. Session 81B.

## Lesson 102: Behavioral Instructions Are Insufficient — Only Mechanical Enforcement Works
- **Mistake:** Lesson 89 was written after Session 80 with explicit prevention steps. Session 89 violated it anyway. The lesson existed, the rule existed, the memory existed — all behavioral. None prevented the failure. This is the same pattern as HD-021 (worktree enforcement): behavioral instructions are routinely ignored under context pressure.
- **Rule:** Any rule that has been violated twice MUST get mechanical enforcement (hooks, scripts, gates) — not just another written lesson. Written lessons are necessary for understanding but insufficient for compliance.
- **Prevention:** (1) For /clear: the UserPromptSubmit hook should remind about /clear after commits. (2) For context management: delegate heavy acts to subagents so orchestrator stays lean. (3) When writing a lesson, ask: "can this be enforced mechanically?" If yes, build the enforcement. If no, accept the risk and document it.

## Lesson 101: Subagent Work MUST Be Browser-Verified Before Declaring PASS
- **Mistake:** Session 87 used subagents to build scoring unification (AD-200) and card improvements. Self-assessment declared PASS, but scoring was still divergent (62% vs 43% for same distance), discovery cards were missing features, and compare links were broken. The subagent tests passed but the features didn't work end-to-end in the browser.
- **Rule:** Subagent work is NOT verified until the orchestrator or a verification step confirms it in a real browser. Unit tests passing in a subagent is necessary but not sufficient — the integration must be browser-verified before the session declares completion.
- **Prevention:** (1) After merging subagent branches, run browser verification on every changed page. (2) For scoring/display changes, verify the SAME entity shows the SAME score across all surfaces (sidebar, cards, discovery). (3) Never declare a scoring unification "done" without comparing output from multiple code paths on the same input.
