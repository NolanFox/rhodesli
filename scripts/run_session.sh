#!/bin/bash
# run_session.sh — Runs multi-phase sessions with REAL context isolation
#
# Usage: ./scripts/run_session.sh <prompt-file>
#
# Each phase runs as a separate `claude -p` invocation, giving true
# context window isolation (not just /clear within a session).
#
# The prompt file should have phase markers: ## PHASE N
# Each phase runs with:
#   1. CLAUDE.md context (always loaded by Claude Code)
#   2. The specific phase instructions
#   3. A checkpoint file from the previous phase
#
# After each phase:
#   - Progress is written to a checkpoint file
#   - Git commit is expected (checked but not enforced)

set -euo pipefail

PROMPT_FILE="${1:?Usage: $0 <prompt-file>}"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: Prompt file not found: $PROMPT_FILE"
    exit 1
fi

# Extract session ID from the prompt filename
SESSION_ID=$(basename "$PROMPT_FILE" | grep -oE '[0-9]+[a-z]?' | head -1)
if [ -z "$SESSION_ID" ]; then
    echo "Error: Could not extract session ID from filename: $PROMPT_FILE"
    exit 1
fi

echo "=== Session Runner: Session $SESSION_ID ==="
echo "Prompt: $PROMPT_FILE"
echo "Session ID: $SESSION_ID"

# Set session tracking
echo "$SESSION_ID" > .claude/current_session.txt

CHECKPOINT_FILE=".claude/session_checkpoint.md"

# Split prompt into phases
PHASE_COUNT=$(grep -cE '^## PHASE [0-9]' "$PROMPT_FILE" || echo "0")
echo "Found $PHASE_COUNT phases"

if [ "$PHASE_COUNT" -eq 0 ]; then
    echo "No phase markers found. Running as single phase."
    claude -p "$(cat "$PROMPT_FILE")"
    exit $?
fi

# Extract phase boundaries (line numbers where ## PHASE appears)
PHASE_LINES=$(grep -nE '^## PHASE [0-9]' "$PROMPT_FILE" | cut -d: -f1)
TOTAL_LINES=$(wc -l < "$PROMPT_FILE")

PREV_LINE=0
PHASE_NUM=0

for LINE in $PHASE_LINES; do
    PHASE_NUM=$((PHASE_NUM + 1))

    # Find the end of this phase (start of next phase or end of file)
    NEXT_LINE=$(echo "$PHASE_LINES" | awk "NR>1{print prev} {prev=\$0}" | head -n "$PHASE_NUM" | tail -1)
    if [ -z "$NEXT_LINE" ]; then
        NEXT_LINE=$TOTAL_LINES
    fi

    echo ""
    echo "=== Phase $PHASE_NUM (lines $LINE-$NEXT_LINE) ==="

    # Extract phase content
    PHASE_CONTENT=$(sed -n "${LINE},${NEXT_LINE}p" "$PROMPT_FILE")

    # Build the phase prompt with context
    PHASE_PROMPT="You are running Phase $PHASE_NUM of Session $SESSION_ID.

Read CLAUDE.md for project rules.
Read SESSION_LOG.md for current progress.
$([ -f "$CHECKPOINT_FILE" ] && echo "Read $CHECKPOINT_FILE for previous phase results." || echo "This is the first phase.")

## Phase Instructions
$PHASE_CONTENT

## After completing this phase:
1. Update SESSION_LOG.md with results
2. Commit changes with conventional commit message
3. Write a checkpoint summary to $CHECKPOINT_FILE"

    # Run the phase
    echo "Running phase $PHASE_NUM..."
    if claude -p "$PHASE_PROMPT"; then
        echo "Phase $PHASE_NUM completed."
    else
        echo "Phase $PHASE_NUM FAILED (exit code $?)."
        echo "Check SESSION_LOG.md and $CHECKPOINT_FILE for details."
        exit 1
    fi

    # Check for commit
    LATEST_COMMIT=$(git log --oneline -1 --since="1 minute ago" 2>/dev/null || echo "")
    if [ -n "$LATEST_COMMIT" ]; then
        echo "Commit: $LATEST_COMMIT"
    else
        echo "WARNING: No commit detected for phase $PHASE_NUM"
    fi
done

echo ""
echo "=== All $PHASE_COUNT phases complete ==="
echo "Session $SESSION_ID finished. Check SESSION_LOG.md for results."
