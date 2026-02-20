# Session 54E Prompt: Verification Sweep — Close Every Gap

Saved from user prompt. This session is VERIFICATION ONLY — no new features.

## Phases
1. **Deliverable Existence Audit** — Verify every deliverable from sessions 54, 54B, 54c, 54D exists. Create anything missing.
2. **Playwright MCP Setup + Browser Testing** — Confirm Playwright works, run browser tests.
3. **CLAUDE.md Session Operations Checklist** — Add frequently-forgotten operational rules.
4. **Final Verification + Push** — Tests, doc sizes, git push.

## Absolute Rules
1. All tests must pass: `pytest tests/ -x -q`
2. Deploy via `git push origin main`. NOT Railway dashboard.
3. When trimming any doc, verify destination has content FIRST (HD-011).
4. No doc file > 300 lines.
5. Every new decision → ALGORITHMIC_DECISIONS.md or HARNESS_DECISIONS.md.
