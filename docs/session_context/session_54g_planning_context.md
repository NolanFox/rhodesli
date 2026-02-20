# Session 54G Planning Context

**Purpose:** Final cleanup session before Session 49B interactive. Captures research, feedback reconciliation, and architectural decisions from the 54F review cycle.
**Breadcrumbs:** Session 54F results → AD-119 (buffalo_sc fix) → HARNESS_DECISIONS.md → OPS_DECISIONS.md → BACKLOG.md

---

## 1. Session 54F Results Summary

**The Win:** Compare pipeline latency reduced from 51.2s → 10.5s (2-face photo) on Railway shared CPU.
- 28.5s for 14-face group photo (borderline unusable but functional)
- Root cause: buffalo_sc wasn't in Docker image; hybrid detection silently fell back to full buffalo_l (all 5 models)
- Singleton model loading was already working — it was loading the *wrong* (heavier) model
- This is a Railway shared CPU floor — GPU inference would bring it under 1 second

**What 54F Fixed:**
- Correct model packaging in Dockerfile (buffalo_sc now included)
- Instrumentation caught the real cause (Phase 1 logging)
- 11/11 smoke tests passing against production endpoints

**What 54F Did NOT Do:**
- Did not run Playwright browser tests (only curl/API smoke tests) — LOGGED AS FAIL
- Did not verify Railway CLI was actually being used for log diagnosis
- Loading indicator still missing in production UX
- Photos still don't display in compare results
- Uploaded images don't persist to archive

---

## 2. Nolan's Feedback (7 Items — All Must Be Addressed)

### 2A. Interactive Upload UX Vision (NEW FEATURE — BACKLOG + AD)

Nolan's full UX specification for compare/estimate uploads:

1. **Photo preview appears immediately** after upload
2. **Progress bar** with text summarizing current step, face count, and pipeline stage
3. **Faces populate below one-by-one** as detection completes (same pattern as elsewhere in UX)
4. **Face overlays on the photo change colors** through pipeline stages (detection → embedding → comparison)
5. **Fully interactive** when complete (like other photo views)
6. **Transition between compare and estimate** views with same photo
7. **Every uploaded photo saved** as if submitted through main upload flow (gatekeeper pattern)
8. **Support 2-3 concurrent uploads** via server-side queue (prevent Railway timeout)
9. **Multi-photo upload required** for compare; TBD for estimate — needs design thinking
10. **Progress explanation:** "distilled for non-technical person that a technical person could still use to figure out what part of the ML pipeline it was at"

**Technical approach (from research):**
- **SSE (Server-Sent Events)** is the right pattern for this. FastHTML + HTMX can handle SSE natively.
- Pattern: POST upload → return job_id immediately (202) → SSE stream for progress → faces populate via HTMX swap as each completes
- Reference: Medium article "Server-Sent Events: The Streaming Protocol" (Jan 2026) describes this exact pattern for long-running AI tasks
- FastHTML SSE example exists on GitHub (fabge/fasthtml-sse) — chatbot pattern, adaptable
- Queue needed: Python `asyncio.Queue` or Redis-backed queue for Railway. Given single-worker constraint, `asyncio.Queue` is simplest
- Face-by-face progressive rendering: each detected face triggers an SSE event with face crop + overlay coordinates

**Decision:** Create AD entry for this architecture. Add to BACKLOG as multi-session epic. Do NOT build in 54G — this is a design + implementation effort spanning 2-3 sessions minimum.

### 2B. Root Cause Learning — Silent Fallback Principle

The buffalo_sc fallback revealed a systemic issue: **ML model fallbacks that degrade silently are bugs, not features.**

**Check:** Does AD-119 capture the general principle or just the specific fix?
- If just the fix: Add a HARNESS lesson or new HD entry
- Required principle: "Every ML model loading must log which model was actually loaded and whether any fallback occurred. Silent fallbacks are bugs."
- This applies to: CORAL training, similarity calibration, any future model work, the LoRA pipeline

**Action for Claude Code:** Read AD-119. If it only documents the buffalo_sc Docker fix, add a new section or companion entry (AD-120) that captures the generalizable principle. Cross-reference to HARNESS_DECISIONS.md.

### 2C. Railway CLI Enforcement

**Status from past conversations:** Railway CLI IS installed and linked to the project.
**Problem:** Claude Code still doesn't use `railway logs` even when rules say to.

**Research findings — 3 approaches, ranked:**

1. **Railway MCP Server (BEST):** `claude mcp add railway-mcp-server -- npx -y @railway/mcp-server` — This gives Claude Code *native API access* to Railway for deployments, logs, and project management. It's not a CLAUDE.md rule (which can be ignored); it's an actual tool in the MCP toolbelt. Railway's own documentation recommends this for Claude Code integration.

2. **Claude Code Hooks (GOOD):** A `PostToolUse` hook that runs after `git push` could automatically call `railway logs` and pipe output to a file. This enforces the behavior mechanically rather than via instruction.

3. **Railway Skills (ALTERNATIVE):** Open-source Claude Code skills for Railway exist (mshumer/claude-skill-railway, mokarram-PU/claude-skill-railway) — these package status checks, health verification, and project switching as slash commands.

**Decision:** Install Railway MCP Server as primary solution. Add a PostToolUse hook as belt-and-suspenders. Update CLAUDE.md to reference the MCP server. Create AD/HD entry documenting this decision.

**Action for Claude Code:** 
- Verify Railway CLI installed: `which railway`
- Install Railway MCP Server: `claude mcp add railway-mcp-server -- npx -y @railway/mcp-server`  
- Verify: `claude mcp list`
- If MCP install fails, fall back to PostToolUse hook approach
- Create `.claude/hooks/post-deploy-check.sh` that runs `railway logs --latest` after any git push
- Keep trying until confirmed working. Test by pushing a trivial commit and verifying logs are captured.

### 2D. AD-119 Deeper Lesson (Silent Fallback Principle)

See 2B above. Claude Code must:
1. Read AD-119 
2. Assess if it captures the generalizable principle
3. If not, create AD-120: "ML Model Loading Observability — Silent Fallbacks Are Bugs"
4. Cross-reference in HARNESS_DECISIONS.md and CLAUDE.md
5. Report back what it did

### 2E. Production Browser Testing Verification

**Question:** Did 54F actually run Playwright browser tests, or only curl smoke tests?
**Likely answer:** Only curl. The transcript references show "11/11 smoke tests passing" which hit API endpoints, not browser rendering.

**Action for Claude Code:**
1. Check session 54F logs/transcript for any Playwright execution
2. If no browser tests were run, log this as a FAIL in the session log
3. Create/update a CLAUDE.md rule: "After any deploy that touches UI, run Playwright browser smoke test (not just curl). Log PASS/FAIL explicitly."
4. Verify Playwright is installed and the test suite from 54E exists
5. Run the Playwright browser test now against production to verify compare renders correctly

### 2F. Pre-49B Verification Tasks

All of these Claude Code should execute directly:

1. **Health check:** `curl -s https://rhodesli.nolanandrewfox.com/health` — verify app is up
2. **Compare upload test:** Use Playwright to upload a test photo and verify:
   - Does a loading indicator appear?
   - Do results display with photos?
   - How long does it feel?
3. **AD-119 check:** See 2D above
4. **Railway CLI check:** See 2C above
5. **Document all findings** in session log

### 2G. Performance Journey Documentation

The 51.2s → 10.5s optimization story needs a permanent home that won't rot.

**Research findings on ADR/documentation best practices:**
- AWS ADR guidance: "ADR serves as an append-only log extending beyond initial design"
- Microsoft Well-Architected Framework: "Start the ADR at onset and maintain throughout lifespan"
- Key principle from research: ADRs are immutable snapshots with superseding records, not edited-in-place documents

**Proposed: PERFORMANCE_CHRONICLE.md**

A new document type for Rhodesli — not an AD (single decision) but a chronicle of an optimization journey. Structure:

```
# Performance Chronicle: Compare Pipeline Latency

## Timeline
| Date | Session | Metric | Value | Change |
|------|---------|--------|-------|--------|
| 2026-02-19 | 54A | Compare (2-face) | 51.2s | Baseline |
| 2026-02-20 | 54F | Compare (2-face) | 10.5s | -79.5% |
| 2026-02-20 | 54F | Compare (14-face) | 28.5s | First measurement |

## Root Causes Discovered
- Session 54F: buffalo_sc not in Docker → silent fallback to buffalo_l
- Singleton model loading was working; wrong model was loaded

## Architecture Constraints
- Railway shared CPU ($5/mo Hobby plan)
- GPU inference would bring under 1 second
- Current floor for shared CPU without architecture change

## Breadcrumbs
- AD-119: buffalo_sc Docker fix
- AD-120: Silent fallback observability principle  
- Session 54A-54F: Full session logs
- CHANGELOG: v0.XX entries
```

**Decision:** Create PERFORMANCE_CHRONICLE.md in docs/. Add breadcrumbs to relevant ADs and session logs. Add CLAUDE.md rule: "When any performance optimization is completed, update PERFORMANCE_CHRONICLE.md with before/after metrics, root cause, and breadcrumbs."

---

## 3. Research Summary

### SSE for Progressive Upload UX
- SSE is the right pattern for server→client progress streaming
- FastHTML supports SSE (reference: fabge/fasthtml-sse on GitHub)
- Pattern: immediate 202 + job_id → SSE progress stream → HTMX partial swaps
- Queue needed for concurrent uploads on Railway single-worker

### Railway MCP Server
- Official Railway integration for Claude Code
- Gives native API access (not just CLI wrapping)
- Install: `claude mcp add railway-mcp-server -- npx -y @railway/mcp-server`
- Solves the "rules say use railway logs but Claude Code doesn't" problem mechanically

### MCP Token Overhead — Mostly Solved (Jan 2026)
- **Historical problem:** MCP servers loaded ALL tool definitions at startup. Users reported 50-80k tokens consumed before typing anything.
- **Fix (Jan 2026):** Claude Code shipped **Tool Search** as default behavior. When tool definitions exceed 10% of context, tools are deferred and loaded on-demand only when needed.
- **Impact:** Up to 95% reduction in startup token cost. Railway MCP's modest tool count (~5-8 tools) should add minimal idle overhead with Tool Search active.
- **Verification:** After install, run `/context` to confirm Railway tools are deferred, not eagerly loaded. Session 54G: MCP not yet loaded (requires restart). npm cache permission issue observed.
- **Fallback:** If token overhead is concerning for long overnight sessions, the PostToolUse hook approach has ZERO token overhead since it's just a shell script. The hook-only approach is acceptable if MCP proves too expensive.
- **Source:** Anthropic engineering blog "Introducing advanced tool use" + Claude Code docs on cost management
- **Key insight from Anthropic's own docs:** "Prefer CLI tools when available — tools like `gh`, `aws`, `gcloud`, and `railway` are more context-efficient than MCP servers because they don't add persistent tool definitions." The MCP advantage is discoverability (Claude Code knows it exists as a tool), not efficiency.

### Performance Documentation Best Practices
- ADRs are single-decision, immutable records (AWS, Microsoft guidance)
- A "chronicle" or "journey" document is a different artifact — an append-only timeline
- Cross-reference via breadcrumbs to ADs, sessions, changelog
- Key: must be machine-discoverable (CLAUDE.md reference) so future sessions find it

### Claude Code Hook Enforcement
- PostToolUse hooks run automatically after tool execution
- Can enforce `railway logs` after `git push` without relying on instructions
- Belt-and-suspenders with MCP Server approach

---

## 4. Decisions Made in This Planning Session

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| 1 | SSE for upload progress | Only viable pattern for long-running server→client streaming; FastHTML compatible | ACCEPTED — add to BACKLOG as epic |
| 2 | Queue for concurrent uploads | Railway single-worker would timeout without it; asyncio.Queue simplest | ACCEPTED — add to AD |
| 3 | Railway MCP Server | Mechanical enforcement > instructional rules; official integration | ACCEPTED — install in 54G |
| 4 | PostToolUse hook for deploy logs | Belt-and-suspenders backup | ACCEPTED — create in 54G |
| 5 | PERFORMANCE_CHRONICLE.md | ADRs are single-decision; optimization journeys need their own format | ACCEPTED — create in 54G |
| 6 | AD-120 for silent fallback principle | AD-119 may only have the specific fix, not the generalizable lesson | ACCEPTED — create if needed |
| 7 | Playwright enforcement rule | Curl ≠ browser testing; must be explicit in harness | ACCEPTED — add to CLAUDE.md |

---

## 5. What 54G Does NOT Do

- Does NOT build the SSE upload progress UX (that's a multi-session epic)
- Does NOT change ML models or pipeline architecture  
- Does NOT do the 49B interactive work (GEDCOM, birth year review, visual walkthrough)
- Does NOT modify identity/photo/ML data files
- Does NOT redesign compare/estimate flow (only documents the vision)

---

## 6. Files Claude Code Should Reference

- `CLAUDE.md` — update with new rules
- `ALGORITHMIC_DECISIONS.md` — check AD-119, potentially create AD-120
- `HARNESS_DECISIONS.md` — add entries for Railway MCP, Playwright enforcement
- `OPS_DECISIONS.md` — add Railway MCP Server entry  
- `BACKLOG.md` — add SSE upload progress epic, performance chronicle maintenance
- `ROADMAP.md` — slot SSE epic appropriately (after current sprint)
- `docs/session_logs/` — session 54G log
- `docs/session_context/` — copy this file there
