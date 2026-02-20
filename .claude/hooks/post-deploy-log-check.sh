#!/bin/bash
# After git push to main, capture Railway deploy logs + remind about Playwright
# Belt-and-suspenders backup to Railway MCP Server
# See HD-014: Every deploy MUST be followed by production Playwright verification

echo "=== Railway Deploy Log Check ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 10
railway logs --latest 2>&1 | head -50
echo "=== End Deploy Log Check ==="
echo ""
echo "REMINDER: Run Playwright against production after deploy completes:"
echo "  Use MCP Playwright browser tools to verify key pages on production"
echo "  Or: pytest tests/e2e/ -v (against local server)"
echo "  See HD-014: Every deploy MUST be followed by production verification."
