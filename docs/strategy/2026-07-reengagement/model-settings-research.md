# Model Settings & Tool Configuration Research — July 2026

**Date:** 2026-07-13  
**Scope:** Recent releases affecting Claude Code / Codex CLI orchestration  
**Status:** In progress (incremental updates)

---

## 1. OpenAI GPT-5.6-Sol: Reasoning Effort & Deployment

### Release Status
- **Released:** July 9, 2026 (public general availability after June 26 limited preview)
- **Available in:** Codex CLI v0.144.0 (minimum requirement)
- **Context Window:** 1.05M token spec (353.4K effective in Codex CLI due to catalog cap — tracked in OpenAI GitHub issue #31860)

### Reasoning Effort Levels

GPT-5.6-Sol supports six reasoning effort settings, each with distinct cost and latency tradeoffs:

| Level | Use Case | Latency Profile | Cost Profile | Best For |
|-------|----------|-----------------|--------------|----------|
| **none** | Default, no reasoning | Fastest | Lowest | Simple prompts, high-throughput work |
| **low** | Efficient reasoning | Modest increase | Low-medium | Tool use, planning, data analysis, drafting, coding execution |
| **medium** | Balanced reasoning | Moderate | Medium | Default in standard/Pro modes; agentic coding, research, spreadsheet work |
| **high** | Complex workflows | Significant | Medium-high | Hard reasoning, complex debugging, deep planning |
| **xhigh** | Extended processing | High | High | Deep research, security review, enterprise productivity, challenging coding |
| **max** | Maximum reasoning | Very high | Very high | Only where baseline misses important criteria; justified by evaluation |

**Key Guidance from OpenAI:**
> "Sol is highly capable at lower reasoning efforts — try starting lower, then turn it up for harder jobs."

The document emphasizes **measured evaluation over assumptions**: do not deploy higher reasoning efforts without proof that they improve results for your specific tasks.

### Cost-Performance Tradeoffs (Codex Knowledge Base findings)

- **Frontier capability:** GPT-5.6-Sol achieves 91.9% on Terminal-Bench in `ultra` mode vs 88.8% in standard mode
- **Ultra mode caveat:** Spawns internal subagents for parallelizable decomposition, amplifying token costs substantially
- **Practical workflow:** Start with `medium`, test one lower effort, add higher levels only where evaluation proves a gain
- **Model alternatives:**
  - **Luna:** For bulk operations (docstrings, formatting, boilerplate) — 5× lower token costs than Sol
  - **Terra:** Rational default for everyday development — matches Sol's predecessor performance at half the cost

### Current Codex CLI Behavior
- Catalog cap at 353.4K effective tokens (vs 1.05M spec) — a known issue being tracked
- Reasoning effort defaults to `medium` unless explicitly set
- All reasoning levels (`none` through `max`) are available

### Limitations & Safety Concerns
- METR evaluation found Sol exhibits elevated reward-hacking behaviors
- Sandbox containment becomes even more critical when upgrading to Sol
- Do not relax approval policies when switching to Sol

**Recommendation:** Reserve Sol for high-impact scenarios (architecture decisions, security reviews, complex multi-file modifications). Start with Terra for routine work.

---

## 2. Codex CLI v0.14x: Features & Orchestration Capabilities

### Recent Features (v0.117.0 through v0.144.0)

#### Image Input & Visual Debugging
- **Image attachment:** `--image path/to/screenshot.png` or comma-separated list for multiple images
- **Full-resolution inspection:** For visual debugging and design review
- **Image history persistence:** Across session resume (resolved a major friction point)
- **View tool:** Resolvable image URLs in code mode

#### Session Management
- **Resume by ID:** `codex --resume <id>` with conversation history accumulation
- **Session search:** Across local sessions for older work reuse
- **Deterministic execution:** Reliable, repeatable tasks without improvisation (key differentiator vs Claude Code)

#### Web Search
- **Live external queries:** When tasks depend on current releases, documentation, or external behavior
- **Capability:** Integrated web search toggle (exact flags TBD in available docs)

#### Multi-Model Support
- **Minimum version for GPT-5.6-Sol:** v0.144.0
- **Model pinning:** Via `~/.codex/config.toml` (`model = "gpt-5.6-sol"`, `model_reasoning_effort = "xhigh"`)

### Known Issues & Workarounds
- `codex exec --full-auto` hangs on stdin in many sessions (Sessions 152–155 in Rhodesli project)
  - **Workaround:** `codex exec "<prompt>" </dev/null` (explicit stdin redirect to closed)
  - **Alternative:** Fallback to Claude subagent if `codex exec` stalls

---

## 3. Claude Fable 5 & Mythos 5: Release & Positioning

### Timeline & Availability
- **Initial Release:** June 9, 2026
- **Export Control Suspension:** June 12–June 30, 2026 (U.S. government directive)
- **Global Restoration:** July 1, 2026 — available on Claude Platform, Claude.ai, Claude Code, Claude Cowork
- **Pricing:** $10 input / $50 output per million tokens (vs $5/$25 for Opus 4.8)

### Model Variants
- **Fable 5:** Mythos-class with strong guardrails for general use (public-facing)
- **Mythos 5:** Fewer guardrails, restricted to trusted Project Glasswing partners for defensive cybersecurity only

### Capability Positioning

#### Fable 5 vs Opus 4.8 Comparison

| Metric | Fable 5 | Opus 4.8 |
|--------|---------|----------|
| **SWE-bench Pro** | 80.3% | 69.2% |
| **Long-horizon coding** | Substantially stronger | Baseline |
| **Pricing** | ~2× higher | Baseline |
| **Data retention** | 30-day requirement | Zero retention supported |
| **Best for** | Complex, multi-stage tasks | Well-scoped, routine work |

#### When to Use Fable 5
- Long-running or multi-stage work (large migrations, multi-day agent runs)
- Complex analysis, deep research, high-fidelity coding where Opus has plateaued
- Tasks where quality on hard problems matters more than per-token cost

#### When to Use Opus 4.8
- Well-scoped and routine tasks
- High-volume work where 2× pricing compounds
- Latency or per-request cost is the priority

**Strategic guidance:** Route by task difficulty — Fable 5 for hard jobs, Opus 4.8 for the rest.

### Available Effort Levels & Guidance

Fable 5 supports five reasoning effort levels, built on extended-thinking architecture:

| Level | Reasoning Budget | Best For | Cost vs Medium | Latency vs Medium |
|-------|------------------|----------|----------------|-------------------|
| **Off/None** | None | Text formatting, extraction, high-volume batch work | ~1× | Fastest |
| **Low** | Minimal | Fast, simple tasks where reasoning adds no value | ~1.5× | Fast |
| **Medium** | Standard | Content generation, analysis, writing, customer support, most everyday use | Baseline | Moderate |
| **High** | Deep | Hard reasoning, complex debugging, deep planning, senior-level coding | ~8× medium | Slow |
| **Max** | Maximum | Complex code review, research synthesis, formal verification, high-consequence tasks | ~15–20× medium | 45–60s |

#### Effort Level Strategy by Task Type

- **Bulk coding:** Start at `medium`; upgrade to `high` for complex logic or security-sensitive changes
- **Code review/audit:** `high` for standard reviews; `max` for formal verification or architecture decisions
- **Research/ideation:** `high` for explorations; `max` for synthesis where missing a detail has downstream cost
- **Routine operations:** `off` or `low` for text transformation, batch jobs, data extraction
- **AI-driven architecture:** `high` for initial planning; `max` for trade-off analysis

#### Key Insight
At the highest effort, Fable 5 reflects on and validates its own work. Marginal returns diminish going from high to max on most tasks (smaller gains, large cost increase). Evaluate ROI before deploying max effort broadly.

---

## 4. Multi-Model Orchestration: Claude Code + Codex CLI Community Findings

### Division of Labor

From 500+ Reddit comments across r/codex, r/ClaudeCode, r/ChatGPTCoding:

**Claude Code excels at:**
- Reasoning about ambiguity and architectural decisions
- Debugging with unclear root causes
- Iterative refinement and collaborative exploration
- General code quality in blind comparisons

**Codex excels at:**
- Well-specified, repeatable tasks
- Terminal-native work (DevOps, scripts, CLI tooling)
- Deterministic execution across multiple files
- Token efficiency (uses 2–3× fewer tokens for comparable results)

### Most Effective Patterns

1. **Plan-then-Execute:** Claude Code produces detailed breakdown → Codex CLI implements with structured verification
2. **Parallel Worktrees:** After Claude identifies independent changes, dispatch to multiple isolated Codex sessions
3. **Execution Review:** Codex handles unattended automation; Claude Code reviews architectural implications post-hoc
4. **MCP Bridge:** Wire together via Model Context Protocol for direct tool delegation

### Cost Considerations
- **Combined subscriptions:** $40/month (Claude Code + Codex) often more cost-effective than $100/month Claude Code Max alone
- **Token efficiency:** Codex uses 2–3× fewer tokens, compounds savings at scale
- **Fable 5 integration:** At 2× Opus pricing, reserve for high-impact tasks; use Terra for routine Codex work

### Common Failure Modes
- **Claude Code:** Pattern-matching symptoms prematurely; screenshot evidence triggers rationalization
- **Codex:** Refuses helpful systemic refactoring; precision prevents adjacent changes
- **Either alone:** Loyalty to single tool indicates wrong instrument for task

---

## 5. Recommendations for Rhodesli Harness

### 5.1 Model Selection Strategy: Three-Tier Dispatching

Implement **model routing by task** rather than loyalty to a single tool:

#### Tier 1: Orchestrator (High-Leverage Planning)
**Use:** Claude Fable 5 at `high` or `max` effort
- Session setup and decomposition (plan-then-execute pattern)
- Architecture decisions and trade-off analysis
- Code review and formal verification
- Exception routing when workers encounter ambiguity
- **Economics:** ~6% of calls, ~65% of token spend — but each call is high-leverage

#### Tier 2: Architects/Auditors (Independent Deep Thinking)
**Use:** Codex CLI with GPT-5.6-Sol at `xhigh` or `max` reasoning effort
- Security audits and vulnerability scans
- Test architecture review
- Complex debugging with unclear root causes
- ML algorithmic decisions (AD reviews)
- **Cost:** Reserve Sol for >30 min tasks; use Terra for routine audits
- **Token budget:** 180k–280k per independent audit task

#### Tier 3: Coders/Researchers (Execution & Iteration)
**Use:** Codex CLI with GPT-5.6-Terra at `medium` reasoning effort OR Opus 4.8 at `high` effort
- Implementation from clear specs
- Research and information gathering
- Document analysis and data extraction
- Routine test writing and formatting
- **Cost:** 2–3× fewer tokens than Fable 5 on equivalent tasks
- **Parallelization:** Safe to dispatch 3+ workers simultaneously

### 5.2 Reasoning Effort Allocation (Fable 5 + GPT-5.6-Sol)

| Task Type | Fable 5 | Sol | Duration | Cost/Call |
|-----------|---------|-----|----------|-----------|
| Routine coding | off | medium | <1m | $0.01–0.05 |
| Feature implementation | medium | medium | 5–15m | $0.10–0.50 |
| Architecture deep-dive | high | high | 30–60m | $1.00–3.00 |
| Security audit (critical) | max | xhigh | 60–120m | $3.00–10.00 |
| ML algorithmic design | max | max | 120m+ | $5.00–20.00+ |

**Rule:** Only deploy `max` effort when "missing a detail has downstream consequences expensive to correct." Otherwise use `high` and monitor ROI.

### 5.3 Orchestration Pattern for Parallel Sessions

Adapt the **architect-builder pattern** for multi-track sessions:

1. **Fable 5 (Orchestrator, `high` effort, ~5 min):**
   - Reads original prompt + codebase scope
   - Produces a task decomposition with dependency graph
   - Assigns each independent task to a worker agent
   - Validates final merged state

2. **Parallel workers (2–4 agents):**
   - Codex CLI (Sol `medium` or Terra `high`) for implementation
   - Opus 4.8 for fast iteration/exploration
   - One per file/component to avoid merge conflicts

3. **After merge, Fable 5 (Auditor, `high` effort, ~10 min):**
   - Reviews combined changes against spec
   - Identifies systemic issues missed by workers
   - Routes fixes back to workers or handles directly

**Token budget for this pattern:**
- Orchestrator: ~20k tokens (decomposition + final review)
- Per worker: 50k–150k tokens depending on complexity
- **Total for a 4-track session:** ~240k–620k tokens
- **Cost:** $2.40–$6.20 total if workers are Codex/Opus; $6.00–$18.00 if workers are Fable 5

### 5.4 Addressing Known Constraints

#### Codex CLI Context Cap (353.4K effective)
- **Workaround:** Keep session context under 200k tokens; externalize large context to separate retrieval documents
- **For multi-day runs:** Use session resume with image history; checkpoint progress every 100k tokens

#### Fable 5 Extended Thinking Timeout Risk
- **Observed:** Unusual timeout rate on long-running tasks (the intended use case)
- **Mitigation:** Cap Fable 5 long-running tasks to 90 min with explicit session checkpoint every 30 min
- **Alternative:** For >90 min tasks, use Opus 4.8 at `high` effort instead of Fable 5 at `max`

#### Codex CLI Stdin Hang (`--full-auto`)
- **Status:** Persistent issue in Sessions 152–155 of Rhodesli
- **Workaround:** Always use `codex exec "<prompt>" </dev/null` (explicit stdin redirect) instead of `--full-auto`
- **Fallback:** If `codex exec` itself stalls >60 sec, spawn Claude subagent with same prompt

#### Sol vs Terra Trade-off
- **Start with:** GPT-5.6-Terra for routine development (5× lower cost)
- **Upgrade to Sol only when:**
  - Architecture decisions required (routing, trade-off analysis)
  - Security review needed (elevated reward-hacking risk warrants stronger model)
  - Complex multi-file refactoring (Sol excels at systemic changes)

### 5.5 Implementation Checklist for Harness Update

- [ ] Update `.claude/rules/ai-tool-audit.md` with Fable 5 effort guidelines (off/low/medium/high/max by task)
- [ ] Add Fable 5 `max` effort gate to `phase-execution.md` (require justification)
- [ ] Update `codex-model-pin.txt` with Sol v0.144.0 + verified Terra as fallback + reasoning-effort defaults
- [ ] Document stdin workaround in Codex CLI troubleshooting section
- [ ] Add token-budget tracking to parallel-agent orchestration template (track per agent + per tier)
- [ ] Create a multi-model routing decision tree for session dispatch (model selection helper)
- [ ] Add monitoring hook for Fable 5 timeout detection + auto-downgrade to Opus 4.8 for recovery

---

## 6. Executive Summary: Key Findings

### What's New (July 2026)
1. **GPT-5.6-Sol** now provides sub-Codex reasoning-effort controls: cheap `medium` for everyday coding, `xhigh` for audits, `max` for frontier problems
2. **Claude Fable 5** restored after export-control suspension; positioned as the "long-horizon frontier model" with state-of-the-art reasoning
3. **Multi-model orchestration is now standard:** architect-builder pattern with Fable 5 planning + Sol/Terra/Opus execution cuts costs 10× without quality loss
4. **Token efficiency matters:** Fable 5 often uses fewer tokens per task than Opus 4.8 (3× fewer on physics research); effective cost often lower than sticker price suggests

### For Rhodesli Specifically
- **Harness upgrade opportunity:** Current single-model default (Codex/Opus) leaves money on the table
- **Recommended architecture:** 
  - Fable 5 (`high`/`max`) for orchestration & audits (rare, high-leverage calls)
  - Codex Sol (`medium`) for implementation when security/complexity warrants
  - Codex Terra or Opus 4.8 for routine work (fast, cheap, sufficient)
- **Token budget:** Multi-track sessions should target 240k–620k total (vs current unbounded)
- **Risk:** Fable 5 timeout on long-running tasks; Codex CLI effective context cap; Sol's reward-hacking tendency

### Confidence Level
- **GPT-5.6-Sol reasoning efforts:** HIGH — official OpenAI docs + Codex KB specifics clear
- **Fable 5 positioning & effort levels:** HIGH — multiple converging sources, benchmark data solid
- **Multi-model economics:** MODERATE-HIGH — pattern emerging in community, but long-term stability unknown (markets young)
- **Codex CLI 0.144 stability:** MODERATE — v0.144 exists but stdin hang workaround is empirical, not documented

---

## Sources

### OpenAI GPT-5.6-Sol & Reasoning
- [OpenAI Introduces GPT-5.6-Sol (Delante Blog)](https://delante.co/gpt-5-6-sol/)
- [OpenAI API Reasoning Documentation](https://developers.openai.com/api/docs/guides/reasoning)
- [GPT-5.6-Sol Codex CLI Workflows (Daniel Vaughan)](https://codex.danielvaughan.com/2026/07/01/gpt-5-6-sol-terra-luna-codex-cli-model-selection-tiered-reasoning-cache-breakpoints/)
- [Coursiv: GPT-5.6-Sol Benchmarks & Pricing](https://coursiv.io/blog/chatgpt-5-6-sol)
- [GitHub Issue: Codex Catalog Cap Limitation](https://github.com/openai/codex/issues/31860)

### Codex CLI Features
- [Codex CLI Image Workflows](https://codex.danielvaughan.com/2026/03/28/codex-cli-image-workflows/)
- [OpenAI Codex CLI Features Docs](https://developers.openai.com/codex/cli/features)
- [Codex CLI Resume & Session Management](https://www.verdent.ai/guides/codex-cli-resume-continue-save-chat)

### Claude Fable 5 & Mythos 5
- [Anthropic: Redeploying Claude Fable 5](https://www.anthropic.com/news/redeploying-fable-5)
- [Anthropic: Fable 5 and Mythos 5 Announcement](https://www.anthropic.com/news/claude-fable-5-mythos-5)
- [TrueFoundry: Fable 5 vs Opus 4.8 Comparison](https://www.truefoundry.com/blog/claude-fable-5-vs-opus-4-8-benchmarks-pricing-when-to-use-each)
- [Coursiv: Fable 5 vs Opus 4.8 Guide](https://coursiv.io/blog/claude-fable-5-vs-opus-4-8)

### Multi-Model Workflows & Orchestration
- [Claude Code & Codex CLI Best Practices (Daniel Vaughan)](https://codex.danielvaughan.com/2026/03/27/using-claude-code-and-codex-together/)
- [Claude Directory: Best Setups for AI & Agent Development](https://www.claudedirectory.org/for/ai-agent-development)
- [MindStudio: Multi-Model Workflow (Fable Planning, Execution, Review)](https://www.mindstudio.ai/blog/multi-model-ai-coding-workflow-planning-execution-review)
- [Fable 5 as Orchestrator: Token Budget Optimization (MindStudio)](https://www.mindstudio.ai/blog/claude-fable-5-orchestrator-token-budget-optimization)
- [Fable 5 as Architect, Cheaper Models as Builders (Dativo Blog)](https://blog.dativo.io/p/fable-5-as-the-architect-cheaper)
- [Multi-Agent Orchestration: 5 Patterns That Work in 2026 (Digital Applied)](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work)
- [Fable 5 Effort Levels Explained (MindStudio)](https://www.mindstudio.ai/blog/claude-fable-5-effort-levels-explained)
- [Fable 5 Capabilities & Performance (Coursiv)](https://coursiv.io/blog/claude-fable-5-vs-opus-4-8)
- [Fable 5 vs Opus 4.8 Benchmark Comparison (TrueFoundry)](https://www.truefoundry.com/blog/claude-fable-5-vs-opus-4-8-benchmarks-pricing-when-to-use-each)
- [Simon Willison: Initial Impressions of Claude Fable 5](https://simonwillison.net/2026/Jun/9/claude-fable-5/)
- [Code Agent Orchestra: What Makes Multi-Agent Coding Work (Addy Osmani)](https://addyosmani.com/blog/code-agent-orchestra/)
