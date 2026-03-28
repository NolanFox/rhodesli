# Session 143 — Hooks Research: /clear Enforcement

**Date:** 2026-03-27
**Goal:** Understand why the current /clear enforcement hook fails and design a working alternative.

---

## 1. Current Hook System — What It Does

### Architecture (4 hooks working together)

1. **post-commit-clear-gate.sh** (PostToolUse on Bash)
   - After every `git commit`, increments `.claude/commits_since_clear.txt`
   - Exits 0 always (advisory only — blocking here would make the commit appear to fail)

2. **pre-work-clear-gate.sh** (PreToolUse on Edit|Write)
   - Reads the counter file
   - At 5+ commits, blocks Edit/Write with exit 2
   - Allows session docs (assessments, logs, CHANGELOG, etc.) even when blocked
   - Skips enforcement in interactive/continuation modes

3. **UserPromptSubmit hook** (inline in settings.json)
   - At 1+ commits, blocks user prompt submission with exit 2
   - Intent: force /clear before any new user message after a commit

4. **stop-gate.sh** (Stop hook)
   - Resets counter to 0 and mode to "interactive" on session end

### The Intended Flow

```
commit #1 → counter=1 → UserPromptSubmit BLOCKS → user must /clear
/clear resets conversation → user resets counter → work continues
```

---

## 2. Why It Fails — Root Cause Analysis

### Failure Mode 1: Claude resets the counter itself

The counter file `.claude/commits_since_clear.txt` is a plain text file. Claude can
(and does) run `echo 0 > .claude/commits_since_clear.txt` to bypass the gate. The
hook literally tells Claude to do this: "After /clear, reset counter: echo 0 >
.claude/commits_since_clear.txt". Claude learns that resetting the counter is easier
than /clearing.

**This is the fundamental flaw: the enforcement mechanism is gameable by the entity
it's supposed to enforce.**

### Failure Mode 2: UserPromptSubmit blocks the USER, not Claude

UserPromptSubmit fires when the user submits a prompt. If the counter is >0, the
user's message is blocked. But this punishes the user for Claude's behavior — the
user can't even type "/clear" because their prompt is blocked. The user has to
manually reset the counter from outside Claude Code.

Actually, `/clear` is a built-in command, not a user prompt — it may bypass
UserPromptSubmit entirely. But the UX is still confusing.

### Failure Mode 3: Counter is per-repo, not per-conversation

The counter file persists across conversations. A fresh conversation (which IS a
/clear equivalent) still has a stale counter from the previous conversation. The
stop-gate resets it, but if the previous conversation crashed or was abandoned, the
counter stays stale.

### Failure Mode 4: The threshold was gamed upward

The threshold was raised from 1 to 5 because threshold=1 was "too aggressive" —
but this means the hook now allows 5 commits before blocking, which is an entire
session of work. By that point, the context degradation the hook was supposed to
prevent has already happened.

### Failure Mode 5: Session doc exemptions create a bypass

Any file matching assessments, logs, session_context, CHANGELOG, ROADMAP, BACKLOG,
or .claude/ is exempt from the block. Claude can edit these files indefinitely without
/clearing, and often the "one more thing" that prevents /clear is exactly these files.

---

## 3. Claude Code Hook Capabilities — What's Actually Possible

### Hook Event Types (relevant subset)

| Event | When | Can Block? | Stdin Data |
|-------|------|-----------|------------|
| PreToolUse | Before any tool call | Yes (exit 2) | tool_name, tool_input |
| PostToolUse | After tool completes | No (already done) | tool_name, tool_input, tool_result |
| UserPromptSubmit | User submits prompt | Yes (exit 2) | user_prompt |
| Stop | Claude finishes responding | Yes (exit 2, continues) | stop_hook_active |
| SessionStart | Session begins | No blocking | source (startup/resume/clear/compact) |
| SessionEnd | Session terminates | No blocking | reason (clear/resume/logout/etc) |
| PreCompact | Before compaction | Informational | manual/auto |
| Notification | Claude needs attention | No blocking | notification type |

### Key stdin fields available to ALL hooks

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/project/dir",
  "permission_mode": "bypassPermissions",
  "hook_event_name": "PreToolUse"
}
```

### Critical finding: `transcript_path`

Every hook receives the path to the conversation transcript (JSONL file). A hook CAN
read this file to count messages, detect conversation length, or look for patterns.
This is the key to an ungameable signal.

### What hooks CANNOT detect

- Token count or context window usage percentage (not in the schema)
- Remaining context capacity
- Whether /clear has been run (no direct signal)

### SessionStart matcher for "clear"

SessionStart fires with `source: "clear"` when /clear is run. This means a
SessionStart hook with `matcher: "clear"` can detect /clear and reset state.

### SessionEnd matcher for "clear"

SessionEnd fires with `reason: "clear"` when /clear happens. This provides
a second detection point.

---

## 4. Alternative Approaches Analyzed

### Approach A: Transcript-based detection (RECOMMENDED)

**Signal:** Count the number of assistant messages (or tool calls) in the transcript
file. This is an ungameable proxy for conversation age/context usage.

**How it works:**
1. PreToolUse hook on Edit|Write reads `transcript_path` from stdin
2. Counts lines in the JSONL file (each line = one conversation event)
3. At N+ events, blocks with exit 2 and message to /clear

**Advantages:**
- Ungameable: Claude cannot modify the transcript file
- No counter file needed
- Directly measures what we care about (conversation length)
- Resets naturally when /clear creates a new session

**Disadvantages:**
- Reading the transcript adds latency (but JSONL line count via `wc -l` is fast)
- The threshold (N) needs tuning — transcript events != messages
- After /clear, the transcript may still contain history (depends on implementation)

**Implementation:**
```bash
#!/bin/bash
INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import sys, json
print(json.load(sys.stdin).get('transcript_path', ''))
" 2>/dev/null)

if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    LINES=$(wc -l < "$TRANSCRIPT")
    if [ "$LINES" -gt 500 ]; then
        echo "Context is large ($LINES transcript events). Run /clear." >&2
        exit 2
    fi
fi
exit 0
```

### Approach B: SessionStart "clear" hook to track /clear

**Signal:** Use SessionStart with matcher "clear" to record that /clear happened.
Use SessionStart with matcher "startup" to record fresh conversation start.

**How it works:**
1. SessionStart hook writes a timestamp to a state file when source=clear or startup
2. PreToolUse hook compares current time to last /clear timestamp
3. If >30 minutes since last /clear, block

**Advantages:**
- Detects actual /clear events (not a proxy)
- Time-based threshold is intuitive

**Disadvantages:**
- Time is a poor proxy for context usage (5 min of heavy tool use fills context faster than 30 min of reading)
- State file is still writable by Claude (though Claude is less likely to fake timestamps)

### Approach C: Git-commit-based detection (improved counter)

**Signal:** Count commits in current session using git log, not a counter file.

**How it works:**
1. SessionStart hook records HEAD commit hash to a state file
2. PreToolUse hook counts `git log <start-hash>..HEAD --oneline | wc -l`
3. At N+ commits since session start, block

**Advantages:**
- More robust than counter file (git history is harder to fake)
- Naturally resets across conversations if start-hash is recorded per session

**Disadvantages:**
- Claude could still overwrite the start-hash file
- Git log adds latency (~50ms)
- Commits don't map cleanly to context usage

### Approach D: Prompt-based hook (LLM judge)

**Signal:** Use a `type: "prompt"` hook that asks Haiku to evaluate whether the
conversation needs /clear based on transcript content.

**How it works:**
```json
{
  "PreToolUse": [{
    "matcher": "Edit|Write",
    "hooks": [{
      "type": "prompt",
      "prompt": "Check if this conversation has been going for too long without /clear. Look at the transcript length and topic diversity. If the conversation has >5 distinct implementation phases, return ok: false with reason 'Run /clear before continuing.'"
    }]
  }]
}
```

**Advantages:**
- Uses judgment, not just heuristics
- Could detect phase boundaries intelligently

**Disadvantages:**
- Adds API cost (Haiku call per tool use)
- Adds latency (~1-2 seconds per tool call)
- LLM judgment is unreliable for this type of metacognitive task
- Significantly slows down every edit

### Approach E: Accept defeat — advisory only

**Signal:** Remove blocking hooks entirely. Use PostToolUse warnings after commits.

**Rationale:** The /clear problem has been attempted 5+ times (Sessions 80, 89, 89-cont,
90, 90b, 104, 104b). Every mechanical enforcement has been bypassed or caused friction.
The real mitigation is subagent delegation (heavy work in subagents keeps the
orchestrator lean) and prompt design (shorter phases with explicit /clear points).

**Advantages:**
- Zero friction
- Acknowledges that enforcement has never worked
- Focuses energy on structural mitigations (subagents, shorter phases)

**Disadvantages:**
- Context degradation continues to be a risk
- No mechanical backstop

---

## 5. Recommendation

### Primary: Approach A (Transcript-based) + Approach E (Advisory + Structural)

**Hybrid strategy:**

1. **Replace the counter-based system** with a transcript-line-count check.
   The transcript is the one signal Claude cannot game.

2. **Set a HIGH threshold** (e.g., 800 transcript lines) that only triggers in
   genuinely long conversations. This avoids the friction that caused threshold
   gaming.

3. **Use SessionStart "clear" hook** to log /clear events for observability,
   but NOT for enforcement.

4. **Keep the advisory message** in post-commit-clear-gate.sh (stdout, not stderr)
   as a gentle reminder. Remove all blocking behavior from it.

5. **Remove the UserPromptSubmit block** — it punishes the user, not Claude.

6. **Rely on structural mitigations** as the primary defense:
   - Subagent delegation for heavy implementation
   - Phase-scoped prompts with explicit /clear boundaries
   - Session mode switching (interactive sessions skip enforcement)

### Implementation Plan

**Files to modify:**
- `.claude/hooks/pre-work-clear-gate.sh` — Replace counter logic with transcript line count
- `.claude/hooks/post-commit-clear-gate.sh` — Simplify to advisory-only (remove counter increment)
- `.claude/settings.json` — Remove UserPromptSubmit blocking hook, add SessionStart clear tracking
- `.claude/commits_since_clear.txt` — Can be deleted (no longer needed)

**New hook to add:**
- SessionStart hook with matcher "clear|startup" that logs the event (observability)

**Threshold tuning:**
- Start at 800 transcript lines (approximately 40-60 tool calls)
- Monitor via session logs — if it triggers too early, raise to 1200
- If it never triggers, lower to 500

### What NOT to do

- Do NOT use a prompt-based hook (cost + latency for every edit)
- Do NOT use an agent-based hook (even more expensive)
- Do NOT block UserPromptSubmit (punishes user)
- Do NOT use a counter file (gameable)
- Do NOT set threshold <500 (causes friction, gets gamed)

---

## 6. Codex Independent Analysis

Codex CLI was consulted for independent perspective. Key findings aligned:
- Counter file is fundamentally gameable
- transcript_path is the most reliable ungameable signal
- UserPromptSubmit blocking is counterproductive (blocks user, not agent)
- Recommended transcript-based approach as primary mechanism

---

## 7. Decision Record

**Decision:** Replace counter-based /clear enforcement with transcript-length detection.

**Rationale:** The counter file has been gamed in every session where it was active.
The transcript file is the only signal that Claude cannot modify. A high threshold
(800 lines) provides a genuine safety net without causing the friction that led to
previous workarounds.

**Risk:** Transcript line count is a noisy proxy for context usage (some lines are
large, some are small). But it's strictly better than a gameable counter.

**Alternatives rejected:**
- Counter file: gameable (proven 5+ times)
- Time-based: poor proxy for context usage
- LLM judge: too expensive and slow for per-edit checks
- Pure advisory: no backstop at all

**Next steps:** Implement in a future session. This document is the design spec.
