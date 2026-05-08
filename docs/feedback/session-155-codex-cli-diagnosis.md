# Codex CLI Hang Diagnosis (Session 155 Track 5)

**Date**: 2026-04-29
**Codex version**: codex-cli 0.125.0
**Platform**: Darwin 23.6.0 (macOS), zsh
**Worktree**: `.claude/worktrees/agent-a17e2c9fa94a16933` (branch `worktree-agent-a17e2c9fa94a16933`)

**Config** (`~/.codex/config.toml`):
```toml
model = "gpt-5.5"
model_reasoning_effort = "xhigh"
```

## Test results

All Codex calls were issued from a non-TTY shell (the Claude Code Bash tool).
Latency is wall-clock from start of invocation to exit. "Stdin redirect" is
the file descriptor attached to Codex's stdin during the test.

| # | Form                                                                 | Stdin redirect | Result | Latency  | Notes |
|---|----------------------------------------------------------------------|----------------|--------|----------|-------|
| 1 | `codex --version`                                                    | inherited      | PASS   | 2 s      | Reports `codex-cli 0.125.0`. |
| 2 | `codex exec --help` / `codex --help`                                 | inherited      | PASS   | <1 s     | Confirms `[PROMPT]` arg semantics: "If stdin is piped and a prompt is also provided, stdin is appended as a `<stdin>` block". This is the root cause of the hang when stdin is connected but never closes. |
| 3 | `codex exec "<prompt>" </dev/null`                                   | `/dev/null`    | PASS   | 27 s     | Positional prompt, stdin closed. Returned full audit-style answer. One non-fatal `failed to record rollout items: thread ... not found` warning printed to stderr, response was complete. |
| 4 | `codex exec <<< "<prompt>"` (heredoc-string)                         | the herestring | PASS   | 22 s     | Heredoc closes stdin after the string is delivered. Same warning, same complete response. |
| 5 | `echo "<prompt>" \| codex exec -`                                    | pipe (closed)  | PASS   | 23 s     | Explicit `-` placeholder. Pipe closes when `echo` exits. Same warning, complete response. |
| 6 | `codex exec --full-auto "echo hello" </dev/null` *(control)*         | `/dev/null`    | HANG   | ~19 min  | **Bug reproduced**. Stderr printed `Reading additional input from stdin...` even though stdin was `/dev/null`. The model eventually produced output (`hello`) and exited, but not within any reasonable session-timeout. With stdin truly idle (TTY-less, no EOF), the hang is unbounded. |

## Working invocation pattern

**For one-shot audits, use any of these forms with stdin closed:**

```bash
# Form A — positional prompt, explicit stdin redirect (recommended)
codex exec "<your audit prompt>" </dev/null

# Form B — heredoc-string (also fine; closes stdin automatically)
codex exec <<< "<your audit prompt>"

# Form C — pipe with explicit `-` placeholder
echo "<your audit prompt>" | codex exec -
```

All three completed in ~22–27 seconds for a ~13K-token audit-summary prompt at
`model = gpt-5.5, reasoning_effort = xhigh`.

**Do NOT use `--full-auto`**: it forces Codex into an interactive sandbox loop
that re-reads stdin even when a positional prompt is supplied. The "Reading
additional input from stdin..." banner is the diagnostic. This bug has now
blocked the harness's Codex audit step in Sessions 152, 153, 153b, 154 — and
test 6 above confirms it is still present in 0.125.0.

## Recommended `.claude/rules/ai-tool-audit.md` update

The current rule already says "DO NOT use `--full-auto` — stdin hangs in
Sessions 152, 153, 153b" and lists `codex exec "<prompt>"` and
`codex exec <<< "<prompt>"`. The diagnosis confirms both forms work. Suggested
small edits (NOT applied here — this is a read-only track):

1. In the "Invocation" line, add a note that **stdin must be closed** in
   non-TTY contexts (Claude Code Bash tool, CI):

   > **Invocation**: `codex exec "<prompt>" </dev/null` or
   > `codex exec <<< "<prompt>"` or `echo "<prompt>" | codex exec -`. The
   > stdin redirect / herestring / pipe is required when the parent shell is
   > non-TTY (e.g., the Claude Code Bash tool, CI runners) — otherwise Codex
   > may append stdin to the prompt and block. **DO NOT use `--full-auto`** —
   > stdin handling is broken (verified again in 0.125.0, Session 155 Track 5).
   > If all forms hang, fall back to a Claude general-purpose subagent.

2. Add Session 155 to the affected-sessions list: "stdin hangs in Sessions
   152, 153, 153b, 154" → "152, 153, 153b, 154, 155 (--full-auto only;
   non-`--full-auto` forms work in 0.125.0)".

## Side note: rollout-recording warning

Every successful run printed:

```
ERROR codex_core::session: failed to record rollout items: thread <uuid> not found
```

Despite the `ERROR` log level, the model response and exit code were correct.
This appears to be a benign telemetry/recording bug, not a stdin issue.
Worth filing upstream but does not affect audit usability.

## Escalation note

The `--full-auto` stdin bug is the only remaining hang. Non-`--full-auto`
forms work. No upstream escalation needed beyond what the existing rule
documents — Codex maintainers should be told the bug is still reproducible
in 0.125.0 with the exact invocation `codex exec --full-auto "echo hello"`
when stdin is `/dev/null`.

- **Bug class**: stdin handling under `--full-auto` (non-TTY parent shell)
- **Sessions affected**: 152, 153, 153b, 154, 155 (all with `--full-auto`)
- **Sessions safe**: any session that uses Form A/B/C above
- **Reproduction (60-second confirmation)**:
  ```bash
  codex exec --full-auto "echo hello" </dev/null
  # Will print "Reading additional input from stdin..." and hang.
  ```
- **Workaround**: drop `--full-auto`; use Form A/B/C. Fall back to Claude
  general-purpose subagents per `session-defaults.md` if even non-`--full-auto`
  forms regress in a future release.
