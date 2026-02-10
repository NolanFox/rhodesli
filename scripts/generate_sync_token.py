#!/usr/bin/env python3
"""Generate a secure sync token for the Rhodesli sync API.

Usage:
    python scripts/generate_sync_token.py
"""

import secrets

token = secrets.token_urlsafe(32)

print(f"Generated sync token: {token}")
print()
print("Set it on Railway:")
print(f"  railway variables set RHODESLI_SYNC_TOKEN={token}")
print()
print("Set it locally (add to .env):")
print(f"  echo 'RHODESLI_SYNC_TOKEN={token}' >> .env")
print()
print("Or export directly for this shell session:")
print(f"  export RHODESLI_SYNC_TOKEN={token}")
print()
print("After setting on Railway, redeploy (push to main or trigger manual deploy).")
print("Then test with:")
print("  python scripts/sync_from_production.py --dry-run")
