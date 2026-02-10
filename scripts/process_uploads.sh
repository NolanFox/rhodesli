#!/bin/bash
# Full upload processing pipeline.
#
# Downloads staged photos from production, runs face detection and clustering,
# then optionally uploads to R2 and syncs data back to production.
#
# Usage:
#   ./scripts/process_uploads.sh              # Full pipeline (interactive)
#   ./scripts/process_uploads.sh --dry-run    # Steps 1-3 only, preview mode
#
# Steps:
#   1. Download staged photos from production
#   2. Run face detection + embedding generation (ingest_inbox)
#   3. Run clustering to find matches (cluster_new_faces)
#   4. Upload processed photos + crops to R2
#   5. Sync updated data to production (redeploy)
#   6. Clear staging on production
#
# Requires:
#   - RHODESLI_SYNC_TOKEN (for API access)
#   - R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME (for R2 upload)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PENDING_DIR="$PROJECT_ROOT/raw_photos/pending"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

echo "=== Rhodesli Upload Processing Pipeline ==="
echo ""

# --- Pre-flight checks ---
if [[ -z "${RHODESLI_SYNC_TOKEN:-}" ]]; then
    # Try loading from .env
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep RHODESLI_SYNC_TOKEN | xargs 2>/dev/null) || true
    fi
    if [[ -z "${RHODESLI_SYNC_TOKEN:-}" ]]; then
        echo "ERROR: RHODESLI_SYNC_TOKEN not set. Set it in .env or export it."
        exit 1
    fi
fi

if [[ "$DRY_RUN" == "false" ]]; then
    # Check R2 credentials for non-dry-run
    for var in R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME; do
        if [[ -z "${!var:-}" ]]; then
            # Try loading from .env
            if [[ -f "$PROJECT_ROOT/.env" ]]; then
                export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep "$var" | xargs 2>/dev/null) || true
            fi
            if [[ -z "${!var:-}" ]]; then
                echo "WARNING: $var not set. R2 upload will fail."
            fi
        fi
    done
fi

# --- Step 1: Download staged photos ---
echo "Step 1: Downloading staged photos from production..."
echo ""

python3 "$SCRIPT_DIR/download_staged.py" --dest "$PENDING_DIR"

# Check if anything was downloaded
if [[ ! -d "$PENDING_DIR" ]] || [[ -z "$(ls -A "$PENDING_DIR" 2>/dev/null | grep -v _metadata)" ]]; then
    echo ""
    echo "No photos to process. Done."
    exit 0
fi

PHOTO_COUNT=$(ls -1 "$PENDING_DIR" 2>/dev/null | grep -v "^_" | grep -v ".json$" | wc -l | tr -d ' ')
echo ""
echo "Found $PHOTO_COUNT photo(s) in $PENDING_DIR"
echo ""

# --- Step 2: Face detection + embedding generation ---
echo "Step 2: Running face detection and embedding generation..."
echo ""

JOB_ID="staged-$(date +%Y%m%d-%H%M%S)"

# Collect source from metadata if available
SOURCE=""
METADATA_FILE=$(ls "$PENDING_DIR"/_metadata.json 2>/dev/null | head -1)
if [[ -n "$METADATA_FILE" ]]; then
    SOURCE=$(python3 -c "import json; print(json.load(open('$METADATA_FILE')).get('source', ''))" 2>/dev/null || echo "")
fi

SOURCE_ARG=""
if [[ -n "$SOURCE" ]]; then
    SOURCE_ARG="--source \"$SOURCE\""
fi

python3 -m core.ingest_inbox --directory "$PENDING_DIR" --job-id "$JOB_ID" $SOURCE_ARG
echo ""

# --- Step 3: Clustering ---
echo "Step 3: Running face clustering (dry-run)..."
echo ""

python3 "$SCRIPT_DIR/cluster_new_faces.py" --dry-run
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo "=== DRY RUN COMPLETE ==="
    echo ""
    echo "Review the clustering output above."
    echo "To continue with full pipeline:"
    echo "  ./scripts/process_uploads.sh"
    echo ""
    echo "Or run remaining steps manually:"
    echo "  python scripts/cluster_new_faces.py --execute"
    echo "  python scripts/upload_to_r2.py --execute"
    echo "  git add data/ && git commit -m 'data: process staged uploads'"
    echo "  git push  # triggers Railway redeploy"
    echo "  python scripts/download_staged.py --clear-after"
    exit 0
fi

# --- Step 4: Upload to R2 ---
echo "Step 4: Uploading photos and crops to R2..."
echo ""

python3 "$SCRIPT_DIR/upload_to_r2.py" --execute
echo ""

# --- Step 5: Deploy updated data ---
echo "Step 5: Syncing data to production..."
echo ""
echo "  Updated data files need to reach the Railway volume."
echo "  Committing and pushing to trigger redeploy..."
echo ""

git -C "$PROJECT_ROOT" add data/identities.json data/photo_index.json data/embeddings.npy 2>/dev/null || true
if git -C "$PROJECT_ROOT" diff --cached --quiet; then
    echo "  No data file changes to commit."
else
    git -C "$PROJECT_ROOT" commit -m "data: process staged uploads ($JOB_ID)"
    echo "  Committed data changes."
    echo ""
    echo "  Push to deploy: git push"
    echo "  (Not pushing automatically — review the commit first)"
fi
echo ""

# --- Step 6: Clear staging ---
echo "Step 6: Clearing processed files from production staging..."
echo ""

python3 "$SCRIPT_DIR/download_staged.py" --clear-after --dest "$PENDING_DIR"
echo ""

echo "=== Pipeline Complete ==="
echo ""
echo "Summary:"
echo "  - Processed $PHOTO_COUNT photo(s) from staging"
echo "  - Job ID: $JOB_ID"
echo "  - Photos uploaded to R2"
echo ""
echo "Remaining:"
echo "  - Review cluster matches: python scripts/cluster_new_faces.py --execute"
echo "  - Push to deploy: git push"
echo "  - Verify on live site: $RHODESLI_SITE_URL"
