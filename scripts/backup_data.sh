#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +%Y-%m-%d-%H%M)
BACKUP_DIR="data_backup_${TIMESTAMP}"

echo "Backing up data to ${BACKUP_DIR}/"
cp -r data/ "${BACKUP_DIR}/"
echo "✓ $(find "${BACKUP_DIR}" -name '*.json' | wc -l) JSON files backed up"

# Verify critical community data
if grep -rq "poisson1957\|Sarina Benatar" "${BACKUP_DIR}/" 2>/dev/null; then
  echo "✓ Community contribution data verified"
else
  echo "⚠ No community contribution data found (may be expected if none exists yet)"
fi

git add "${BACKUP_DIR}/"
git commit -m "backup: data snapshot ${TIMESTAMP}"
echo "✓ Committed as $(git rev-parse --short HEAD)"
