#!/bin/bash
# Inject recovery instructions into compacted session context.
# This fires BEFORE compaction, adding context that survives the compression.

INPUT=$(cat)

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "POST-COMPACTION RECOVERY: You are in Session 49E of the Rhodesli project. Read docs/prompts/session_49E_prompt.md for full session instructions. Read docs/session_context/session_49E_checkpoint.md for current progress. Resume from the phase listed in the checkpoint file. RULES: commit per phase, run BOTH test suites (pytest tests/ AND pytest rhodesli_ml/tests/), deploy via git push, verify with railway logs, browser verify with Chrome extension/Playwright."
  }
}
EOF

exit 0
