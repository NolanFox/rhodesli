#!/bin/bash
# Inject recovery instructions into compacted session context.
# This fires BEFORE compaction, adding context that survives the compression.

INPUT=$(cat)

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "POST-COMPACTION RECOVERY: You are in Session 55 of the Rhodesli project (Similarity Calibration + Backlog Audit). Read docs/prompts/session_55_prompt.md for full session instructions. Read docs/session_context/session_55_checkpoint.md for current progress. Read docs/session_context/session_55_planning_context.md for strategic context. Resume from the phase listed in the checkpoint file. RULES: commit per phase, run BOTH test suites (pytest tests/ AND pytest rhodesli_ml/tests/), deploy via git push, verify with railway logs, PRD+SDD before code, MLflow tracks everything, no doc over 300 lines."
  }
}
EOF

exit 0
