---
name: agent_comparison
description: Performance comparison of Claude Code vs Codex CLI vs Antigravity for Rhodesli development — strengths, weaknesses, and optimal usage patterns
type: project
---

## Multi-Agent Development Patterns (Sessions 97-100, March 2026)

**Codex CLI (GPT-5.4 xhigh):**
- 100+ commits across sessions 97-100 (tagged `[codex]`)
- **Strengths:** High throughput, excellent commit discipline (atomic + well-labeled), strong assessment/documentation culture, good at breadth (many small fixes fast), PR-based workflow with verification
- **Weaknesses:** Degrades over long sessions (12h Session 100 showed diminishing returns after ~6h), shipped a production perf regression in Session 98 (GEDCOM full-scan in request path, fixed in 98B hotfix), left incomplete work when rate-limited (half-finished timeline nav_prefix), did NOT update ROADMAP/CHANGELOG/current_session.txt (harness violations), created 12 orphaned worktrees without cleanup, merge chain regressions in identities.json went undetected

**Why:** Codex excels at surface-level correctness (tests pass, commits clean) but misses deeper data integrity issues. Best for focused <4h implementation sessions, not marathon debugging.

**How to apply:** Cap Codex sessions at 4h max. Always follow with Claude Code data integrity audit. Use for implementation, not data migration.

**Antigravity (Gemini 3.1 Pro):**
- ~20 commits in Session 99 (UI implementation) + design review artifacts for Session 100
- **Strengths:** Good visual design direction, useful critical review of PRDs, actionable mockup packs, identified adoption/discoverability risks
- **Weaknesses:** Only one session of actual code, used `variant="session99"` approach (code duplication), commits tagged `[gemini]` for planning/docs work, no evidence of running tests independently

**Why:** Antigravity works best as design critic and reviewer, not primary implementer. The variant-based approach is cautious but creates maintenance burden.

**How to apply:** Use for design review, UX critique, and planning documents. Pair with Codex for implementation.

**Claude Code (Opus 4.6):**
- All sessions prior to 97 (through 96e-cont9)
- **Strengths:** Thorough data integrity work (merge chain repairs, orphan detection), better ROADMAP/CHANGELOG discipline, context management (/clear protocol), Supabase dual-write architecture, strong at depth (debugging complex data issues)
- **Weaknesses:** Slower throughput per session, can get stuck in debugging loops, context degradation over long sessions

**Why:** Claude Code is best for data-sensitive work, architectural decisions, and audit/verification.

**How to apply:** Use for data integrity, architectural work, and post-Codex verification. The audit pattern (Codex implements → Claude Code verifies) is the strongest workflow discovered.

**Optimal Multi-Agent Pattern:**
1. Claude Code: Architecture, data integrity, planning, verification
2. Codex: Implementation sprints (<4h), test writing, bug fixes
3. Antigravity: Design review, UX critique, PRD analysis
4. Always: Claude Code audit after any Codex data-touching session
