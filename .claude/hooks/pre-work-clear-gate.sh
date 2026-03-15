#!/bin/bash
# pre-work-clear-gate.sh — Block work if commits outstanding without /clear
#
# Called as PreToolUse hook on Edit|Write. If commits_since_clear > 0,
# BLOCKS the edit with exit 2, forcing Claude to /clear first.
#
# Why Edit|Write and not Bash? Because:
# - Blocking Bash would prevent `git status`, `cat`, etc. needed for /clear prep
# - Edit/Write is the first thing Claude does when starting real work on a new phase
# - This catches the "I'll just do one more thing" pattern that causes context stuffing
#
# The counter is reset to 0 by:
# - run_session.sh (each phase is a separate process, counter is irrelevant)
# - The user manually: echo 0 > .claude/commits_since_clear.txt
# - A UserPromptSubmit hook after /clear (conversation restarts fresh)
#
# See: HD-025

COUNTER_FILE=".claude/commits_since_clear.txt"
CURRENT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")

# Block after 1+ commits without /clear
# Any commit means a phase was completed — /clear before starting the next.
# Threshold was 2 but that was too lenient (Lesson 140).
if [ "$CURRENT" -ge 1 ]; then
    echo "BLOCKED: $CURRENT commits since last /clear." >&2
    echo "You MUST /clear before editing any more files." >&2
    echo "After /clear, reset counter: echo 0 > .claude/commits_since_clear.txt" >&2
    exit 2
fi

exit 0
