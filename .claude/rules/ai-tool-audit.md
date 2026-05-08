# AI Tool Audit Logging

Triggers: After any use of Codex, Antigravity, or other external AI tools in a session.

## Principle: ALWAYS USE THE BEST AVAILABLE MODEL FOR AUDIT WORK

The harness defaults to the strongest model OpenAI offers in Codex CLI. Audit work
(security review, data-integrity review, prompt design review) is exactly the
case where reasoning quality matters most — never default to a weaker model
"because it's faster." If a faster model is needed for a specific tactical task,
state that explicitly with a one-line justification.

## Current standard (set 2026-04-28, Session 154 prep)

- **Codex CLI**: v0.125.0 or later (run `codex --version` to verify)
- **Codex model**: `gpt-5.5` — current best available for code/audit work (per OpenAI Codex model docs, Apr 2026)
- **Codex reasoning effort**: `xhigh` — for non-latency-sensitive audit work, xhigh is the strongest setting
- **Config location**: `~/.codex/config.toml` (`model = "gpt-5.5"`, `model_reasoning_effort = "xhigh"`)
- **Invocation**: `codex exec "<prompt>" </dev/null` (Track 5 / Session 155 confirmed: explicit stdin redirect is the most reliable form). Alternatives that also work: `codex exec <<< "<prompt>"` (here-string) or `echo "<prompt>" | codex exec -`. **DO NOT use `--full-auto`** — stdin hangs in Sessions 152, 153, 153b, 154, 155. If `codex exec` itself stalls, fall back to a Claude subagent (general-purpose, fresh context) with the same review prompt. See `docs/feedback/session-155-codex-cli-diagnosis.md` for the working/failing matrix.

### Upgrade discipline

When OpenAI ships a model newer than `gpt-5.5` (e.g., gpt-5.6, gpt-6.0):
1. Update `~/.codex/config.toml` to the new model.
2. Update this section's "current standard" to match.
3. Update `.claude/rules/codex-model-pin.txt` (single-line pin file the harness reads).
4. Search for stale references: `grep -rn "gpt-5\.5\|gpt-5\.4\|o4-mini\|o3" .claude/rules/ docs/prompts/ docs/HARNESS_DECISIONS.md` and update inline examples (not historical session records).
5. Do all four in the SAME commit.

### Staying current with model releases (ENFORCED via harness)

The harness pins the current best model in `.claude/rules/codex-model-pin.txt`.
`scripts/harness-check.sh` reads this pin. If the `verified_date` is older than
**14 days**, the script warns at session start with a prompt to refresh.

**To refresh the pin** (run at session start when the warning fires, or any time
you suspect a new release):

1. **Check OpenAI's Codex docs**: https://developers.openai.com/codex/models
2. **Check the OpenAI/Codex changelog**: https://openai.com/index/ (look for "GPT-5.x-Codex" announcements)
3. **Check `codex --version`**: ensure CLI version supports the latest model
4. **If a newer model is available** (e.g., gpt-5.6 or beyond):
   - Update `~/.codex/config.toml`: `model = "<new-model>"`, keep `model_reasoning_effort = "xhigh"` (unless docs say otherwise)
   - Update this rule's "Current standard" section
   - Update `.claude/rules/codex-model-pin.txt` with new model + today's date + source URL
   - Search for and update stale inline references per "Upgrade discipline" above
   - Commit all changes together with message `chore(harness): bump codex model pin to <new-model>`
5. **If no newer model**: update only the `verified_date` in the pin file with today's date and a one-line note `# verified <date> — gpt-5.5 still latest`. Commit with `chore(harness): refresh codex model pin (no change, verified <date>)`.

**Why a 14-day window**: OpenAI typically ships Codex model updates every 2-6
weeks (gpt-5.1 → 5.2 → 5.3 → 5.4 → 5.5 cadence over ~3 months). 14 days catches
new releases within one cycle without being so aggressive that every session
opens with a check.

**This is a HARD rule for audit work**: never run a Codex audit on a stale pin.
If the pin is stale, refresh it BEFORE running the audit — the whole point of
audits is using the strongest reasoning model available, and we don't get that
by drifting to last quarter's model.

### Downgrade discipline

DO NOT downgrade to a model older than the current standard without:
1. A one-line justification appended here naming the specific upstream regression.
2. A BACKLOG entry to revisit when the regression is fixed.
3. A timeline (≤ 30 days) for revisiting.

## Rule

Every session that uses external AI tools (Codex CLI, Antigravity, etc.) MUST log:

### 1. During the Session
- **What tool** was used (Codex CLI, Claude subagent, Antigravity, etc.)
- **What model** powered it (e.g., Codex CLI v0.115 with o4-mini, Claude Opus 4.6, Claude Sonnet 4.6)
- **Agent type**: Independent (fresh context, no prior knowledge) vs Resume (sees prior findings)
- **What task** it was given (audit scope, implementation task, etc.)
- **Raw findings** saved to `docs/session_context/session-NN-{tool}-audit.md`
- **Assessment** of each finding: P0/P1/P2/P3, acted on vs deferred
- **What we actually used** vs what we didn't (with reasons)

### 2. In the Session Assessment (MANDATORY)
Include an **AI Tools** section. This is NOT optional — every session assessment MUST have this section even if "No AI tools used."
```markdown
## AI Tool Usage
- **Tool**: Codex CLI v0.125 (gpt-5.5, xhigh)
- **Agent type**: Independent (fresh context)
- **Task**: Security audit of data repair scripts
- **Findings**: 8 total (2 P1, 3 P2, 3 P3)
- **Acted on**: 2 P1s fixed immediately
- **Deferred**: 3 P2s to BACKLOG
- **Discarded**: 3 P3s (false positives / not applicable)
- **Value assessment**: STRONG — caught SQL injection risk we would have missed
- **Would we have found this ourselves?** The SQL injection: unlikely. The style issues: yes, eventually.
- **Comparison note**: [If multiple tools audited same scope, compare findings here]
```

### 2b. Provenance Tracking (MANDATORY)
Every audit artifact MUST include at the top:
```markdown
**Auditor**: Codex CLI v0.125 (gpt-5.5, xhigh) | Claude Opus 4.6 subagent | etc.
**Agent type**: Independent (no prior context) | Resume (sees prior findings)
**Scope**: [what was reviewed]
**Date**: [ISO date]
```
This enables fair comparison across agents, models, and approaches over time.

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
