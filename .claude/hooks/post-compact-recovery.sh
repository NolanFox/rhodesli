#!/bin/bash
# post-compact-recovery.sh — Fires when session resumes after compaction
# Re-injects ALL critical context from disk
# Registered as SessionStart hook with "compact" matcher

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

echo "WARNING: COMPACTION OCCURRED — RE-READING ALL CONTEXT FROM DISK"
echo ""
echo "=== CLAUDE.md ==="
cat "$PROJECT_DIR/CLAUDE.md" 2>/dev/null
echo ""
echo "=== Current Session ==="
SESSION_ID=$(cat "$PROJECT_DIR/.claude/current_session.txt" 2>/dev/null | tr -d '[:space:]')
echo "Session: $SESSION_ID"
echo ""
if [ -n "$SESSION_ID" ] && [ -f "$PROJECT_DIR/docs/prompts/session-${SESSION_ID}-prompt.md" ]; then
    echo "=== Session Prompt ==="
    cat "$PROJECT_DIR/docs/prompts/session-${SESSION_ID}-prompt.md" 2>/dev/null
    echo ""
fi
echo "=== SESSION_LOG.md ==="
cat "$PROJECT_DIR/SESSION_LOG.md" 2>/dev/null
echo ""
echo "REMINDER: /compact is BANNED. Use /clear instead. This compaction was logged as a RED FLAG."
