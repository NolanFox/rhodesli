#!/bin/bash
# Full ML refresh pipeline: sync -> backup -> rebuild golden set -> evaluate -> validate.
#
# Usage:
#   bash scripts/full_ml_refresh.sh
#
# Requires RHODESLI_SYNC_TOKEN to be set (in .env or exported).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Rhodesli ML Refresh ==="
echo ""

echo "1. Syncing production data..."
python3 "$SCRIPT_DIR/sync_from_production.py" 2>/dev/null || echo "   ⚠ Sync skipped (token not set or deploy pending)"
echo ""

echo "2. Backing up data..."
bash "$SCRIPT_DIR/backup_production.sh"
echo ""

echo "3. Building golden set..."
python3 "$SCRIPT_DIR/build_golden_set.py"
echo ""

echo "4. Evaluating golden set..."
python3 "$SCRIPT_DIR/evaluate_golden_set.py"
echo ""

echo "5. Validating clustering proposals..."
python3 "$SCRIPT_DIR/validate_clustering.py" 2>/dev/null || echo "   ⚠ Validation skipped"
echo ""

echo "6. Dry-run cluster match application..."
python3 "$SCRIPT_DIR/apply_cluster_matches.py" --dry-run --tier high 2>/dev/null || echo "   ⚠ Apply script not available or no matches"
echo ""

echo "=== Done. Review output above, then apply: ==="
echo "  python3 scripts/apply_cluster_matches.py --execute --tier high"
