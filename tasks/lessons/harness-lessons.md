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

## Lesson 77: Trimming Docs Without Verifying Destination Loses Context
- **Mistake:** Session 54c trimmed ROADMAP.md "Recently Completed" from 14 entries to 5, pointing to SESSION_HISTORY.md — but SESSION_HISTORY.md was missing sessions 47-54B. Session 47B (real audit session with 4 tests) was also never added. Context would have been silently lost if not caught.
- **Rule:** Before removing entries from ANY document, verify the destination file already contains equivalent content. "See [other file]" is only valid if you've confirmed the other file actually has the data.
- **Prevention:** Added to .claude/rules/verification-gate.md as a mandatory pre-trim check. When ROADMAP "Recently Completed" is trimmed, SESSION_HISTORY.md must be updated in the SAME commit.
