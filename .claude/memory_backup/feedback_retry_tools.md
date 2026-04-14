---
name: Never give up on tools after first failure
description: When a tool (Chrome, MCP, etc.) fails, retry with fresh connection — never fall back to "just tell me what you see"
type: feedback
---

When Chrome extension or any MCP tool disconnects or fails, RETRY by re-fetching tabs_context_mcp and reconnecting. Do NOT give up after one failure and fall back to asking the user for manual input.

**Why:** User explicitly corrected this behavior — "Unacceptable. You can get Claude Chrome to work. You've done so in the past." The user expects persistence, not surrender after first error.

**How to apply:** On any tool connection failure: (1) retry tabs_context_mcp with createIfEmpty, (2) if that fails, wait 5s and retry, (3) only after 3+ failures escalate to user with specific error. Never preemptively give up.
