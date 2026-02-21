# Browser Automation Research — Session 49B Interactive + UX Audit

## Decision: Dual-Path Browser Strategy (AD-XXX)

### Options Evaluated

#### 1. Claude in Chrome Extension (PRIMARY — try first)
- **What**: Anthropic's own Chrome extension, integrates with Claude Code via MCP
- **Strengths**: Uses your real logged-in Chrome session (solves OAuth admin 
  auth), reads console errors + DOM state, can click/navigate/screenshot
- **Weaknesses**: 2.7-star rating, frequent "Browser extension not connected" 
  errors (6+ open GitHub issues as of Feb 2026). Beta quality. Connection 
  relies on native messaging host config that can break across updates.
- **Setup**: `claude mcp add chrome` or install extension + run `claude --chrome`
- **Token cost**: Screenshots stream into context (~high, varies)
- **Auth**: Automatic — uses your logged-in Chrome session

#### 2. Playwright MCP (FALLBACK — if Chrome fails)
- **What**: Microsoft's official MCP server for browser automation
- **Strengths**: Mature, well-documented, cross-browser, reliable
- **Weaknesses**: Opens fresh browser (no cookies), 26 tools cause 
  "decision paralysis" in agents (Speakeasy research), higher token cost
- **Setup**: `claude mcp add playwright npx @playwright/mcp@latest`
- **Token cost**: ~114k tokens per typical task via MCP
- **Auth**: Must manually log in each session (OAuth redirect in browser)

#### 3. Playwright CLI (BEST for token efficiency)
- **What**: Microsoft's CLI companion to Playwright MCP (Feb 2026)
- **Strengths**: ~27k tokens per task (4x cheaper than MCP), saves 
  snapshots/screenshots to disk files not context window
- **Weaknesses**: Newest option, less community validation. Requires 
  agent to read files from disk for visual info.
- **Setup**: `npm install -g @playwright/cli`
- **Token cost**: ~27k tokens per typical task
- **Auth**: Same as Playwright MCP (manual login needed)

#### 4. Chrome DevTools MCP (SPECIALIZED)
- **What**: Deep browser debugging — performance, network, console
- **Strengths**: Network request inspection, performance profiling
- **Weaknesses**: Overkill for UX audit, more complex setup
- **Decision**: DEFER — not needed for current walkthrough

### Decision
Try Claude in Chrome first (5-minute connection test). If it connects, 
use it for the full audit (best auth story). If it fails, fall back to 
Playwright MCP with manual OAuth login. Log which path was taken.

### Known Failure Modes (Claude in Chrome)
1. "Browser extension is not connected" — most common. Fix: restart 
   Chrome fully (Cmd+Q), then restart Claude Code
2. Native messaging host missing — check file exists at:
   ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/
   com.anthropic.claude_code_browser_extension.json
3. Account mismatch — ensure same Anthropic account in Claude Code 
   and chrome.claude.ai
4. Version mismatch — run `claude --version` and check extension 
   version in chrome://extensions match recent versions

### Known Failure Modes (Playwright MCP)
1. Tool proliferation — 26 tools cause agent indecision. Mitigation: 
   prompt should explicitly say which tools to use (browser_navigate, 
   browser_snapshot, browser_click, browser_take_screenshot)
2. Excessive screenshots — agent takes screenshot after every action. 
   Mitigation: prompt should say "use browser_snapshot for navigation, 
   browser_take_screenshot only for evidence"
3. Fresh browser = no auth. Mitigation: prompt tells agent to navigate 
   to login, then pause for human to authenticate

### Token Budget Estimates
- Per-page audit (navigate + snapshot + screenshot): ~5-15k tokens
- Full app audit (~15 routes): ~75-225k tokens
- With /clear between groups of 5 routes: manageable in 3 batches
- Playwright CLI would cut these numbers by ~4x

### Harness Integration
- Screenshots saved to: docs/browser_audit/screenshots/
- Audit findings saved to: docs/browser_audit/session_49b_ux_audit.md
- Each finding breadcrumbed to: ISSUES_LOG.md and BACKLOG.md
- Decisions breadcrumbed to: ALGORITHMIC_DECISIONS.md

### Sources
- Anthropic docs: code.claude.com/docs/en/chrome
- Simon Willison: til.simonwillison.net/claude-code/playwright-mcp-claude-code
- Speakeasy (tool proliferation): speakeasy.com/blog/playwright-tool-proliferation
- TestCollab (CLI vs MCP): testcollab.com/blog/playwright-cli
- Bug0 (MCP server comparison): bug0.com/blog/playwright-mcp-servers-ai-testing
- GitHub issues: #26305, #26217, #24593, #23104, #21371, #21890
