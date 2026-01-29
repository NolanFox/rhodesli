#!/bin/bash
# ============================================================
# Rhodesli System Reset & Rebuild
# ============================================================
#
# One-command reset for fast iteration during development.
# Wipes identity/photo registries and rebuilds from raw photos.
#
# Usage:
#   ./scripts/reset_system.sh                # Reset registries only
#   ./scripts/reset_system.sh --full         # Also delete embeddings
#   ./scripts/reset_system.sh --yes          # Skip confirmation prompt
#   ./scripts/reset_system.sh --full --yes   # Full reset, no prompt

set -e  # Exit on error

# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Files to delete (always)
IDENTITIES_JSON="$PROJECT_ROOT/data/identities.json"
PHOTO_INDEX_JSON="$PROJECT_ROOT/data/photo_index.json"

# Files to delete (--full only)
EMBEDDINGS_NPY="$PROJECT_ROOT/data/embeddings.npy"

# ============================================================
# ARGUMENT PARSING
# ============================================================

FULL_RESET=false
SKIP_CONFIRM=false

for arg in "$@"; do
    case $arg in
        --full)
            FULL_RESET=true
            ;;
        --yes|-y)
            SKIP_CONFIRM=true
            ;;
        --help|-h)
            echo "Usage: $0 [--full] [--yes]"
            echo ""
            echo "Options:"
            echo "  --full    Also delete embeddings.npy (requires re-ingestion)"
            echo "  --yes     Skip confirmation prompt"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================
# CONFIRMATION
# ============================================================

echo "============================================================"
echo "RHODESLI SYSTEM RESET"
echo "============================================================"
echo ""
echo "This will DELETE:"
echo "  - $IDENTITIES_JSON"
echo "  - $PHOTO_INDEX_JSON"

if [ "$FULL_RESET" = true ]; then
    echo "  - $EMBEDDINGS_NPY (--full mode)"
fi

echo ""

if [ "$SKIP_CONFIRM" = false ]; then
    read -p "This will delete all identities and clusters. Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# ============================================================
# DELETE FILES
# ============================================================

echo ""
echo "Deleting files..."

if [ -f "$IDENTITIES_JSON" ]; then
    rm "$IDENTITIES_JSON"
    echo "  Deleted: identities.json"
else
    echo "  Not found: identities.json (skipped)"
fi

if [ -f "$PHOTO_INDEX_JSON" ]; then
    rm "$PHOTO_INDEX_JSON"
    echo "  Deleted: photo_index.json"
else
    echo "  Not found: photo_index.json (skipped)"
fi

if [ "$FULL_RESET" = true ]; then
    if [ -f "$EMBEDDINGS_NPY" ]; then
        rm "$EMBEDDINGS_NPY"
        echo "  Deleted: embeddings.npy"
    else
        echo "  Not found: embeddings.npy (skipped)"
    fi
fi

# ============================================================
# REBUILD
# ============================================================

echo ""
echo "============================================================"
echo "REBUILDING SYSTEM"
echo "============================================================"

# Step 1: Ingest (compute embeddings)
echo ""
echo "Step 1: Running bulk ingestion..."
echo "------------------------------------------------------------"
python "$PROJECT_ROOT/scripts/ingest_bulk.py"

# Step 2: Seed (cluster embeddings into identities)
echo ""
echo "Step 2: Running seed registry (clustering)..."
echo "------------------------------------------------------------"
python "$PROJECT_ROOT/scripts/seed_registry.py"

# ============================================================
# SUMMARY
# ============================================================

echo ""
echo "============================================================"
echo "RESET COMPLETE - SUMMARY"
echo "============================================================"

# Count photos (from embeddings)
if [ -f "$EMBEDDINGS_NPY" ]; then
    # Use Python to count unique filenames in embeddings
    PHOTO_COUNT=$(python3 -c "
import numpy as np
from pathlib import Path
data = np.load('$EMBEDDINGS_NPY', allow_pickle=True)
filenames = set(f.get('filename', '') for f in data if f.get('filename'))
print(len(filenames))
")
    FACE_COUNT=$(python3 -c "
import numpy as np
data = np.load('$EMBEDDINGS_NPY', allow_pickle=True)
print(len(data))
")
else
    PHOTO_COUNT=0
    FACE_COUNT=0
fi

# Count identities
if [ -f "$IDENTITIES_JSON" ]; then
    IDENTITY_COUNT=$(python3 -c "
import json
from pathlib import Path
with open('$IDENTITIES_JSON') as f:
    data = json.load(f)
    print(len(data.get('identities', {})))
")
else
    IDENTITY_COUNT=0
fi

echo "Photos:      $PHOTO_COUNT"
echo "Faces:       $FACE_COUNT"
echo "Identities:  $IDENTITY_COUNT"
echo "============================================================"
echo ""
echo "System reset complete. Start the server with:"
echo "  python app/main.py"
