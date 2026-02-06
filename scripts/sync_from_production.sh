#!/bin/bash
# Downloads current production data to local repo.
#
# Prerequisites:
#   You must be logged in as admin. Use a browser to sign in at the SITE_URL,
#   then export your session cookie to cookies.txt (e.g., via a browser extension
#   or by copying the cookie header manually).
#
# Usage:
#   ./scripts/sync_from_production.sh
#   SITE_URL=https://custom.domain.com ./scripts/sync_from_production.sh

set -euo pipefail

SITE_URL="${SITE_URL:-https://rhodesli.nolanandrewfox.com}"

echo "Syncing from $SITE_URL ..."

echo "Syncing identities.json..."
curl -s -b cookies.txt "$SITE_URL/admin/export/identities" -o data/identities.json

echo "Syncing photo_index.json..."
curl -s -b cookies.txt "$SITE_URL/admin/export/photo-index" -o data/photo_index.json

echo "Done. Run 'git diff data/' to see changes."
