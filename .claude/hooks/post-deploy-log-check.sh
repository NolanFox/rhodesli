#!/bin/bash
# After git push to main, capture Railway deploy logs
# Belt-and-suspenders backup to Railway MCP Server
echo "=== Railway Deploy Log Check ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 10
railway logs --latest 2>&1 | head -50
echo "=== End Deploy Log Check ==="
