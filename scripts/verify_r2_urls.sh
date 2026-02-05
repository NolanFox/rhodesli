#!/bin/bash
# Verify all image URLs point to R2

BASE_URL="${1:-https://rhodesli-production.up.railway.app}"

echo "Verifying R2 URLs on $BASE_URL"
echo "================================"

sections=("" "?section=to_review" "?section=to_review&view=browse" "?section=confirmed" "?section=photos")
all_passed=true

for section in "${sections[@]}"; do
  url="$BASE_URL/$section"
  html_content=$(curl -s "$url")
  r2_count=$(echo "$html_content" | grep -c "r2.dev" 2>/dev/null || echo "0")
  local_count=$(echo "$html_content" | grep -c "/static/crops\|/photos/" 2>/dev/null || echo "0")

  echo "$section:"
  echo "  R2 URLs: $r2_count"
  echo "  Local URLs: $local_count"

  if [ "$local_count" -gt 0 ]; then
    echo "  ❌ FAIL - Found local URLs that should be R2"
    all_passed=false
  elif [ "$r2_count" -gt 0 ]; then
    echo "  ✓ PASS"
  else
    echo "  ⚠ WARNING - No image URLs found"
  fi
  echo ""
done

# Test photo modal
echo "Photo Modal Test:"
PHOTO_ID=$(curl -s "$BASE_URL/?section=photos" | grep -oE 'hx-get="/photo/[^/]+/partial"' | head -1 | sed 's/.*\/photo\/\([^/]*\)\/.*/\1/')
if [ -n "$PHOTO_ID" ]; then
  MODAL=$(curl -s "$BASE_URL/photo/$PHOTO_ID/partial")
  if echo "$MODAL" | grep -q "Could not load photo"; then
    echo "  ❌ FAIL - Photo modal shows error"
    all_passed=false
  else
    r2_in_modal=$(echo "$MODAL" | grep -c "r2.dev" || echo "0")
    if [ "$r2_in_modal" -gt 0 ]; then
      echo "  ✓ PASS - Photo modal has R2 URLs"
    else
      echo "  ⚠ WARNING - Photo modal has no R2 URLs"
    fi
  fi
else
  echo "  ⚠ WARNING - Could not find photo ID for testing"
fi

echo ""
if $all_passed; then
  echo "✓ All checks passed"
  exit 0
else
  echo "❌ Some checks failed"
  exit 1
fi
