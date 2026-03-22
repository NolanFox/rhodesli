# AI Tool Audit Logging

Triggers: After any use of Codex, Antigravity, or other external AI tools in a session.

## Rule

Every session that uses external AI tools (Codex CLI, Antigravity, etc.) MUST log:

### 1. During the Session
- **What tool** was used (Codex CLI, Antigravity, etc.)
- **What task** it was given (audit scope, implementation task, etc.)
- **Raw findings** saved to `docs/session_context/session-NN-{tool}-audit.md`
- **Assessment** of each finding: P0/P1/P2/P3, acted on vs deferred
- **What we actually used** vs what we didn't (with reasons)

### 2. In the Session Assessment
Include an **AI Tools** section:
```markdown
## AI Tool Usage
- **Tool**: Codex CLI
- **Task**: Security audit of data repair scripts
- **Findings**: 8 total (2 P1, 3 P2, 3 P3)
- **Acted on**: 2 P1s fixed immediately
- **Deferred**: 3 P2s to BACKLOG
- **Discarded**: 3 P3s (false positives / not applicable)
- **Value assessment**: STRONG — caught SQL injection risk we would have missed
- **Would we have found this ourselves?** The SQL injection: unlikely. The style issues: yes, eventually.
```

### 3. Building the Corpus
Over time, this creates a record of:
- What AI tools work well for (security audits, style review, test coverage)
- What they don't (data integrity reasoning, domain-specific logic)
- When to invest time in AI audits vs skip them
- Which tools are strongest for which tasks

### Value Assessment Scale
- **STRONG**: Found issues we likely wouldn't have caught. Worth the time investment.
- **MODERATE**: Found issues we'd have caught eventually, but saved time.
- **WEAK**: Mostly false positives or obvious issues. Low ROI.
- **COUNTERPRODUCTIVE**: Wasted time on irrelevant findings or introduced confusion.

## Why This Exists
Sessions 124-132 used Codex extensively but didn't consistently log what was useful
vs what wasn't. Without this data, we can't optimize when to use AI tools and when
to skip them. The corpus enables data-driven decisions about tool usage.
