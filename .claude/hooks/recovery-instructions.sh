#!/bin/bash
# Inject recovery instructions into compacted session context.
# Fires BEFORE auto-compaction, adding context that survives compression.

INPUT=$(cat)
SESSION_ID=$(cat "$CLAUDE_PROJECT_DIR/.claude/current_session.txt" 2>/dev/null | tr -d '[:space:]' || echo "unknown")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "POST-COMPACTION RECOVERY: You are in Session ${SESSION_ID} of the Rhodesli project. Read docs/prompts/session-${SESSION_ID}-prompt.md for full session instructions. Read SESSION_LOG.md for current progress. Resume from the next unchecked phase. RULES: commit per phase, run BOTH test suites (pytest tests/ AND pytest rhodesli_ml/tests/), deploy via git push, no doc over 300 lines, /clear between phases NEVER /compact."
  }
}
EOF

exit 0
