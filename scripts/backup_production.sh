#!/bin/bash
# Back up local data files.
# Keeps the last 10 backups.
#
# Usage:
#   bash scripts/backup_production.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="$DATA_DIR/backups/$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

for f in identities.json photo_index.json golden_set.json; do
    if [ -f "$DATA_DIR/$f" ]; then
        cp "$DATA_DIR/$f" "$BACKUP_DIR/"
        echo "Backed up $f"
    fi
done

echo "Backup saved to $BACKUP_DIR"

# Keep only last 10 backups
cd "$DATA_DIR/backups"
# shellcheck disable=SC2012
ls -dt */ 2>/dev/null | tail -n +11 | xargs rm -rf 2>/dev/null || true
echo "Cleaned old backups (keeping last 10)"
