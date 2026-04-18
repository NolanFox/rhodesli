# Session Protocol Rules

## CRITICAL: /clear After Every Commit (Lesson 89 — violated TWICE)
"Act" = single atomic commit (not a multi-commit phase). After EVERY commit,
/clear IMMEDIATELY. This is the VERY NEXT action.
- Do NOT read the next phase first. Do NOT "check one thing." /clear FIRST.
- If you think "I'll just do one more thing" — STOP. That thought is the bug.
- Sessions 80 AND 89 both compacted from not clearing.
- Opus 4.7 makes this WORSE, not better: MRCR v2 recall drops to 32.2%
  (vs 4.6's 78.3%). Long context on 4.7 is actively harmful.

## Enforcement: Transcript-Based Detection (HD-032, Session 143, tightened 2026-04-18)
- PreToolUse hook on Edit|Write reads the transcript file (ungameable by agent)
- At **600+** transcript lines: BLOCKS edits with exit 2 (was 800)
- At **300+** transcript lines: advisory warning (was 400)
- Thresholds tightened for Opus 4.7 token inflation (1x–1.35x vs 4.6)
- Parse failures and missing python3 now fail CLOSED (exit 2), not open
- Session-doc allowlist is canonicalized via realpath (no more `../` bypass)
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
