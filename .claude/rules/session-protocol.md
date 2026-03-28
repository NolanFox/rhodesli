# Session Protocol Rules

## CRITICAL: /clear After Every Act (Lesson 89 — violated TWICE)
- After EVERY act commit, /clear IMMEDIATELY. This is the VERY NEXT action.
- Do NOT read the next act first. Do NOT "check one thing." /clear FIRST.
- If you think "I'll just do one more thing" — STOP. That thought is the bug.
- This rule exists because Sessions 80 AND 89 both compacted from not clearing.
- Behavioral reminders failed twice. If this fails a third time, escalate to user.

## Enforcement: Transcript-Based Detection (HD-032, Session 143)
- PreToolUse hook on Edit|Write reads the transcript file (ungameable by agent)
- At 800+ transcript lines: BLOCKS edits with exit 2
- At 400+ transcript lines: advisory warning
- Session docs (assessments, logs, CHANGELOG, etc.) are always allowed
- Interactive/continuation modes skip enforcement entirely

## Standard Protocol
- NEVER use /compact — blocked by hook
- Commit after every phase
- Run tests before every commit
- If context > 40%, /clear is OVERDUE
- If context < 20%, STOP and log progress
- Update SESSION_HISTORY.md at session end
- Update ROADMAP.md — never silently drop items
