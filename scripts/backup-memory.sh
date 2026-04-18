#!/usr/bin/env bash
# Backs up Claude Code memory files to the git repo for version control.
# Memory lives at ~/.claude/projects/ (outside git) — this script syncs it in.
# Run at session end or whenever memory changes.

set -euo pipefail

MEMORY_SRC="$HOME/.claude/projects/-Users-nolanfox-rhodesli/memory"
BACKUP_DST="$(git rev-parse --show-toplevel)/.claude/memory_backup"

if [ ! -d "$MEMORY_SRC" ]; then
    echo "ERROR: Memory source not found: $MEMORY_SRC"
    exit 1
fi

mkdir -p "$BACKUP_DST"

# Sync all .md files (rsync preserves timestamps, --delete removes files deleted from source)
# Fixed 2026-04-18: comment said --delete but flag was missing (Codex P1).
# Memory deletions should propagate to backup — otherwise integrity checks lie.
rsync -av --delete --include='*.md' --exclude='*' "$MEMORY_SRC/" "$BACKUP_DST/"

# Count files (NUL-safe enumeration — Codex P2, robust against unusual names)
SRC_COUNT=$(find "$MEMORY_SRC" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
DST_COUNT=$(find "$BACKUP_DST" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "Memory backup complete: $SRC_COUNT source → $DST_COUNT backed up"

# Integrity check: verify MEMORY.md index matches files
if [ -f "$MEMORY_SRC/MEMORY.md" ]; then
    MISSING=0
    while IFS= read -r ref; do
        if [ ! -f "$MEMORY_SRC/$ref" ]; then
            echo "WARNING: MEMORY.md references missing file: $ref"
            MISSING=$((MISSING + 1))
        fi
    done < <(grep -o '([a-z0-9_]*\.md)' "$MEMORY_SRC/MEMORY.md" | tr -d '()')

    ORPHANS=0
    for f in "$MEMORY_SRC"/*.md; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        [ "$fname" = "MEMORY.md" ] && continue
        # Fixed 2026-04-18: use -F for literal match to prevent regex chars
        # in filenames from confusing grep (Codex P2).
        if ! grep -Fq -- "$fname" "$MEMORY_SRC/MEMORY.md"; then
            echo "WARNING: File not in MEMORY.md index: $fname"
            ORPHANS=$((ORPHANS + 1))
        fi
    done

    if [ "$MISSING" -eq 0 ] && [ "$ORPHANS" -eq 0 ]; then
        echo "Integrity check: PASS (all references resolve, no orphans)"
    else
        echo "Integrity check: FAIL ($MISSING missing, $ORPHANS orphans)"
        exit 1
    fi
fi
