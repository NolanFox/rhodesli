# Proactive Context Management

Triggers: At any point in a session when context usage exceeds 60% OR
when ≥10 parallel subagents have been launched.

## Rule

The assistant MUST proactively recommend a wrap-up to the user when ANY of:

1. Context usage is above 60% (visible in the assistant's own status)
2. Two or more rounds of parallel subagent launches have happened in the same session
3. The session has produced more than 5 commits
4. Opus 4.7's MRCR v2 recall range is being exceeded (>300 transcript lines since last `/clear`)

The wrap-up recommendation should include:
- Current commit count and status (how many ahead of origin/main)
- Which parallel agents are still running and whether their work can carry to next session
- A draft session-NN+1-prompt.md with the handoff
- Which user-facing decisions are still outstanding (awaiting authorization, awaiting review)

## Why this exists

Session 153 (2026-04-18): The user had to explicitly tell the assistant
"this is getting long, we should wrap" after 15+ commits and 4 rounds of
parallel agent launches. The assistant should have proactively flagged the
context pressure because Opus 4.7's recall drops sharply past 300 lines.

Specifically the user said: "this is likely some harness failing. Please
fix that."

## Enforcement

Currently behavioral — the `.claude/hooks/pre-work-clear-gate.sh` already
blocks edits at 600+ transcript lines. But *blocking* is downstream; the
assistant should have proactively told the user the session was getting
long BEFORE the hook needed to fire.

Future enforcement: consider a hook that fires at 300 transcript lines and
ECHOES a reminder to the user (not just to Claude), so the user knows the
session is approaching the recall cliff.

See: session-defaults.md (Opus 4.7 Behavioral Adjustments), Lesson 89 (/clear
between acts), session-protocol.md (clear after every commit).
