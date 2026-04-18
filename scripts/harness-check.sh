#!/usr/bin/env bash
# harness-check.sh — Validate Claude Code harness integrity.
#
# Run manually before critical sessions, or wire into CI/session-start.
# Checks:
#   - Hook scripts referenced by settings.json exist + parse (bash -n)
#   - Blocking hooks actually exit 2 on their trigger condition
#   - Memory files referenced by MEMORY.md all exist
#   - CLAUDE.md <= 80 lines, docs/ <= 300 lines each
#
# Exit code: 0 if healthy, 1 if any check fails.

set -uo pipefail

REPO=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$REPO" || exit 1

FAILS=0
check() {
    local name="$1"
    local status="$2"
    local msg="${3:-}"
    if [ "$status" = "OK" ]; then
        printf "  ✓ %s\n" "$name"
    else
        printf "  ✗ %s — %s\n" "$name" "$msg" >&2
        FAILS=$((FAILS + 1))
    fi
}

echo "=== Claude Code Harness Check ==="
echo ""

echo "[1/5] Hook scripts"
for script in .claude/hooks/*.sh; do
    [ -f "$script" ] || continue
    name=$(basename "$script")
    if bash -n "$script" 2>/dev/null; then
        check "$name syntax" "OK"
    else
        check "$name syntax" "FAIL" "bash -n failed"
    fi
done

echo ""
echo "[2/5] Blocking hooks exit 2 on trigger"
# pre-work-clear-gate should exit 2 when transcript is long
tmp_transcript=$(mktemp)
yes "line" | head -700 > "$tmp_transcript"
tmp_mode_backup=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")
echo "implementation" > .claude/session_mode.txt
input=$(printf '{"tool_input":{"file_path":"app/main.py"},"transcript_path":"%s"}' "$tmp_transcript")
echo "$input" | bash .claude/hooks/pre-work-clear-gate.sh >/dev/null 2>&1
status=$?
echo "$tmp_mode_backup" > .claude/session_mode.txt
rm -f "$tmp_transcript"
if [ "$status" = "2" ]; then
    check "pre-work-clear-gate blocks at 600+ lines" "OK"
else
    check "pre-work-clear-gate blocks at 600+ lines" "FAIL" "exited $status, expected 2"
fi

# stop-gate should exit 2 in implementation mode when assessment missing
tmp_s_backup=$(cat .claude/current_session.txt 2>/dev/null || echo "149")
echo "impossible_session_xyz" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
bash .claude/hooks/stop-gate.sh </dev/null >/dev/null 2>&1
status=$?
echo "$tmp_s_backup" > .claude/current_session.txt
echo "$tmp_mode_backup" > .claude/session_mode.txt
if [ "$status" = "2" ]; then
    check "stop-gate blocks missing assessment" "OK"
else
    check "stop-gate blocks missing assessment" "FAIL" "exited $status, expected 2"
fi

echo ""
echo "[3/5] Memory integrity"
MEMORY_DIR="$HOME/.claude/projects/-Users-nolanfox-rhodesli/memory"
if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
    missing=0
    while IFS= read -r ref; do
        if [ ! -f "$MEMORY_DIR/$ref" ]; then
            missing=$((missing + 1))
        fi
    done < <(grep -oE '\([a-z0-9_]+\.md\)' "$MEMORY_DIR/MEMORY.md" | tr -d '()')
    if [ "$missing" -eq 0 ]; then
        check "MEMORY.md links resolve" "OK"
    else
        check "MEMORY.md links resolve" "FAIL" "$missing missing files"
    fi
else
    check "MEMORY.md exists" "FAIL" "not found at $MEMORY_DIR"
fi

echo ""
echo "[4/5] Doc size caps"
claude_md_lines=$(wc -l < CLAUDE.md 2>/dev/null | tr -d ' ')
if [ "${claude_md_lines:-999}" -le 80 ]; then
    check "CLAUDE.md <= 80 lines ($claude_md_lines)" "OK"
else
    check "CLAUDE.md <= 80 lines ($claude_md_lines)" "FAIL" "over cap"
fi
oversized=$(find docs -name '*.md' -type f 2>/dev/null \
    | xargs wc -l 2>/dev/null \
    | awk '$1 > 300 && $2 != "total" { print $2 " (" $1 ")" }')
if [ -z "$oversized" ]; then
    check "docs/ files <= 300 lines" "OK"
else
    count=$(printf "%s\n" "$oversized" | wc -l | tr -d ' ')
    check "docs/ files <= 300 lines" "FAIL" "$count over cap"
fi

echo ""
echo "[5/5] Rules referenced by CLAUDE.md exist"
while IFS= read -r rule_path; do
    if [ -f "$rule_path" ]; then
        check "$rule_path" "OK"
    else
        check "$rule_path" "FAIL" "referenced but missing"
    fi
done < <(grep -oE '`\.claude/rules/[^`]+`' CLAUDE.md | tr -d '`')

echo ""
if [ "$FAILS" -eq 0 ]; then
    echo "=== Harness healthy ($FAILS failures) ==="
    exit 0
else
    echo "=== Harness has $FAILS failure(s) ===" >&2
    exit 1
fi
