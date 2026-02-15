#!/bin/bash
# Push to production and verify features are live.
# Usage: ./scripts/deploy_and_verify.sh
set -e

echo "=== Deploy & Verify ==="
echo ""

# Step 1: Push
echo "Pushing to origin/main..."
git push

# Step 2: Wait for Railway deploy
echo ""
echo "Waiting 90 seconds for Railway deploy..."
sleep 90

# Step 3: Smoke tests
echo ""
echo "Running production smoke tests..."
python tests/smoke/test_production.py

echo ""
echo "Deploy verified!"
