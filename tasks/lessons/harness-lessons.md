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

## Lesson 103: Behavioral Enforcement Failed Three Times — Hard Block Required
- **Mistake:** Context management /clear rule was violated in Session 80, Session 89, AND Session 89-continuation. Lesson 89 was written after Session 80. Lesson 102 was written after Session 89. Both were behavioral. Both failed. The UserPromptSubmit hook printed "BLOCKED" but didn't actually exit 2, so it was cosmetic enforcement, not real enforcement.
- **Rule:** When a behavioral rule fails THREE times, escalate to HARD BLOCKING hooks (exit 2). The commit counter system now: (1) UserPromptSubmit HARD BLOCKS at 3+ commits without /clear, (2) PreToolUse Bash REFUSES git commit at 4+ commits, (3) Post-commit gate warns at 2, critical at 3. These are real exit 2 blocks, not warnings.
- **Prevention:** (1) `.claude/commits_since_clear.txt` tracks commits since last /clear (reset by user or manually). (2) UserPromptSubmit: exit 2 at 3+ commits = user prompt rejected. (3) PreToolUse Bash: exit 2 at 4+ commits = git commit refused. (4) Post-commit gate: escalating warnings at 2+, announces upcoming blocks. (5) Test the enforcement: after 3 commits without /clear, verify the system actually blocks. Session 89-continuation.

## Lesson 101: Subagent Work MUST Be Browser-Verified Before Declaring PASS
- **Mistake:** Session 87 used subagents to build scoring unification (AD-200) and card improvements. Self-assessment declared PASS, but scoring was still divergent (62% vs 43% for same distance), discovery cards were missing features, and compare links were broken. The subagent tests passed but the features didn't work end-to-end in the browser.
- **Rule:** Subagent work is NOT verified until the orchestrator or a verification step confirms it in a real browser. Unit tests passing in a subagent is necessary but not sufficient — the integration must be browser-verified before the session declares completion.
- **Prevention:** (1) After merging subagent branches, run browser verification on every changed page. (2) For scoring/display changes, verify the SAME entity shows the SAME score across all surfaces (sidebar, cards, discovery). (3) Never declare a scoring unification "done" without comparing output from multiple code paths on the same input.

## Lesson 107: Session Prep Must Persist All Research Before Writing Prompts
- **Mistake:** Session 96 — extensive research was done on the upload pipeline (cross-community matching mechanics, clustering behavior for Betty/Roland, GEDCOM-first workflow rationale, automated vs manual pipeline steps). Prompt was written but research only existed in conversation context. User had to ask 3 times for proper documentation. Context file, AD entries, and ROADMAP items were created retroactively.
- **Rule:** The prompt is the LAST artifact, not the first. The correct order is: Research → Decisions (AD entries) → Context file → ROADMAP/BACKLOG items → THEN write the prompt. Never write a prompt that references decisions or research that isn't already persisted in a file.
- **Prevention:** `.claude/rules/session-prep-checklist.md` — mandatory checklist before creating any prompt file. Context file must include all research findings, cross-feature implications, known gaps, and pipeline analysis. AD entries must exist for any algorithmic or architectural decisions.

## Lesson 108: Performance Filters Must Preserve Cross-Community Matching
- **Mistake:** Session 96c-cont4 — early community filter in `_compute_discoveries()` also filtered `confirmed_list`, which broke Fox Family → Rhodes cross-community matching. Betty Capeluto and Ray Franco disappeared from Fox Family discoveries because they were Rhodes-only confirmed identities.
- **Rule:** When adding community scope filters for performance, only filter the SOURCE entities (unreviewed faces) by community. Keep TARGET entities (confirmed identities) global — cross-community matching is a core feature.
- **Prevention:** Any community filter on confirmed/target lists must be reviewed against the cross-community matching requirement. Test both same-community AND cross-community discovery scenarios.

## Lesson 109: CommunityMiddleware /api/ Skip Creates Dual-Path Problem
- **Mistake:** Session 96c-cont4 — bare `/api/` paths bypass CommunityMiddleware (line 465), so `request.state.community=None`. This caused discoveries timeout (no community filter → ALL identities computed) and required a Rhodes fallback hack.
- **Rule:** Routes called via HTMX must receive community context. Two strategies: (1) HTMX URLs include `/c/{slug}/` prefix (middleware processes them), or (2) Routes fall back to default community when `request.state.community` is None. Prefer (1) — the JS rewriter handles this client-side.
- **Prevention:** When adding new HTMX endpoints, verify the URL includes community prefix. Test from both Rhodes (bare URLs) and non-Rhodes (prefixed URLs) communities.

## Lesson 140: Hooks That Exit 0 Are Advisory Only — Claude Ignores Them
- **Mistake:** Session 104 — The `/clear` enforcement system has hooks at UserPromptSubmit (warns about commits since /clear) and PreToolUse Edit|Write (pre-work-clear-gate.sh). The UserPromptSubmit hook ALWAYS exits 0, so it never blocks — just prints a warning. The pre-work gate only blocks at 2+ commits (threshold too high). Claude routinely ignores the warning text in system-reminders. User said "your hook situation is a mess" and "they produce errors but do not work."
- **Rule:** Hooks that should enforce behavior MUST exit 2 (block) when the condition is violated. Exit 0 with a warning is worse than no hook — it creates the illusion of enforcement while providing none. Advisory hooks are only useful if Claude reliably acts on warnings, which history shows it does not (Lessons 89, 102, 103).
- **Prevention:** (1) Audit all hooks: if the hook is meant to ENFORCE, verify it exits 2 on violation. (2) UserPromptSubmit hooks cannot effectively block because the user needs to be able to type commands like "/clear" — enforcement must happen at PreToolUse instead. (3) Lower pre-work-clear-gate threshold from 2 to 1 commit. (4) Test hooks by triggering the violation condition and confirming the tool call is actually blocked.

## Lesson 143: Hook audit must be exhaustive — partial fixes create false confidence
- **Mistake (Session 104b):** Session 104 fixed 1 hook (UserPromptSubmit threshold). Session 104b found 3 MORE broken hooks (Stop exit 1, PreToolUse Bash swallowed test exit code, PostToolUse Bash exit 0). Each session only fixed the hook that was visibly failing, leaving others broken. The user had to explicitly demand "review each and every hook."
- **Rule:** When ANY hook is found broken, audit ALL hooks in the same pass. Partial fixes create false confidence — "I fixed the hooks" when only 1 of 4 was actually fixed.
- **Prevention:** (1) Hook changes require a full audit table (hook name, event, expected exit, actual exit, verdict). (2) Test each hook by triggering its condition. (3) The audit table goes in the commit message or session log as evidence.

## Lesson 148: 25 commits never pushed — 3 sessions without deploy
- **Mistake (Sessions 106b, 107, 107b):** All three sessions produced code and assessments that claimed "deploy triggered" but git log showed origin/main was 25 commits behind local main. No session end check verified the remote was up to date.
- **Rule:** Every session MUST end with `git push` and then verify `git log origin/main..HEAD` is empty. If any commits are unpushed, the session is not complete.
- **Prevention:** Add push verification to stop-gate.sh: warn (or block) if `git log origin/main..HEAD` is non-empty. The assessment file should include a line confirming the remote SHA matches local HEAD.

## Lesson 110: Existing Data Not Surfaced Is Worse Than Missing Data
- **Mistake:** Session 96c-cont4 — auto-clustering ran correctly, producing 35 proposals (30 Roland Fox, 4 Betty Capeluto Fox, 1 Ray Franco). But the UI showed "0 Proposals" and user concluded "clustering is completely missing." Hours of debugging ensued for what was purely a UI surfacing gap.
- **Rule:** When a data pipeline produces results, the SAME session must verify they appear in the UI. A pipeline that produces results nobody can see is functionally broken. "Data exists in file X" is not shipped — "user sees data in the app" is shipped.
- **Prevention:** Feature Reality Contract (FRC) check: "Data exists? → App loads it? → Route exposes it? → UI renders it?" All 4 must pass for the SPECIFIC community/context the user will view.

## Lesson 166: Worktree Agents Must Commit Before Returning
- **Mistake:** Session 147 — all 4 worktree subagents completed code changes and tests but left changes uncommitted. The orchestrator had to manually `git add && git commit` in each worktree directory, wasting time and risking lost work. Additionally, Track C's uncommitted changes leaked to the main working directory because the worktree shared the git index, requiring `git checkout --` to clean main before merging.
- **Rule:** Every worktree subagent MUST commit all changes before returning control to the orchestrator. The orchestrator MUST verify `git status` shows a clean working tree in each worktree before proceeding to merge. Uncommitted worktree changes can leak to the main working directory.
- **Prevention:** (1) Subagent prompts must include explicit "commit all changes before completing" instruction. (2) Orchestrator runs `git -C <worktree> status --porcelain` after each subagent returns — if non-empty, the subagent failed its contract. (3) Before merging, verify main working directory is clean with `git status`. See also Lesson 87 (same pattern, Session 69).

## Lesson 167: Git Lock Contention When Launching 3+ Worktree Agents Simultaneously
- **Mistake:** Session 147 — when 3 worktree agents launched simultaneously via `git worktree add`, the 3rd agent got `error: could not lock config file .git/config: File exists`. The agent failed completely and had to be relaunched manually, breaking the parallel execution plan.
- **Rule:** Never launch more than 2 `git worktree add` commands simultaneously. Stagger worktree creation with a brief delay between each, or create all worktrees sequentially in the orchestrator before launching parallel agents.
- **Prevention:** (1) Create all worktree branches sequentially in the orchestrator BEFORE dispatching agents (eliminates lock contention entirely). (2) If agents must create their own worktrees, limit to 2 concurrent `git worktree add` calls. (3) Add retry logic with backoff for git lock errors.

## Lesson 182: Pre-flight Budget Canary Before Parallel Subagents
- **Mistake (Session 157):** The orchestrator launched two Track A worktree subagents in parallel. Both returned within 5-10 seconds with `You've hit your limit` and 0-2 tokens consumed each — Anthropic's user-level usage limit had silently throttled them at launch. The session lost ~1 hour of productive work and had to roll all 6 deferred items into Session 157b. The failure mode is invisible: subagents return cleanly but with empty work products, and the orchestrator can mistake "no commits" for "agents are still running" or "agents had nothing to do."
- **Rule:** Before spawning a parallel subagent group (2+ subagents), launch ONE agent first as a canary. If it returns with **wall-clock < 30 seconds AND total_tokens < 100**, that's the usage-limit failure pattern — abort the second launch, recover the canary's intended work inline (or via a single sequential subagent), and reschedule the remaining parallel work to the next session. If the canary succeeds (does real work, commits, returns honest report), THEN launch the second subagent in parallel. This sacrifices ~5-10 minutes of theoretical parallel time for certainty that the budget will hold.
- **Prevention:**
  1. Session prompts that plan parallel subagent work MUST include a pre-flight canary section (see `docs/prompts/session-157b-prompt.md` "Pre-flight budget check" for the canonical template).
  2. Subagent prompts MUST include an "On budget exhaustion" section instructing the agent to commit-what-they-have and return an honest report rather than silently fail.
  3. The canary's return report MUST include: total tokens consumed, wall-clock time, and an explicit canary-verdict line.
  4. If the user-level usage limit is the constraint: schedule heavy parallel sessions ≥4 hours apart (Anthropic resets daily but tight back-to-back sessions can drain it).
  5. Document the failure pattern in the assessment so future sessions calibrate. Session 157b confirmed the canary pattern works: Subagent #1 returned 123,791 tokens / 18-min wall-clock — clear PASS — and Subagent #2 launched without issue.
- **See also:** Lesson 178 (subagent token-budget hazard for multi-phase tasks).
