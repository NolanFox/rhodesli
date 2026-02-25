# Session 68 Context: Harden Hooks, Regression Tests, ML Progress

## Source
- **Date:** 2026-02-25
- **Origin:** Sessions 66-67 review — hooks shipped but have gaps, parallelization regressed
- **Predecessor:** Session 67 (v0.73.0 — hook enforcement system)

---

## PART 1: RESEARCH FINDINGS — WHAT MUST CHANGE

### 1A: PreCompact CANNOT Block /compact
Multiple sources confirm: "Exit Code 2 Behavior for PreCompact: N/A — shows stderr to user only, no blocking capability." One authoritative source states: "PreToolUse is the only hook that can block actions."

**Implication:** The `exit 2` approach in our PreCompact manual hook does NOT prevent compaction. /compact will still execute.

**Fix:** Since we can't block /compact, we must make it non-destructive:
1. **PreCompact (manual):** Save a full transcript backup BEFORE compaction, plus output a loud warning
2. **SessionStart (compact matcher):** When Claude resumes AFTER compaction, re-inject ALL critical context from disk. This already partially exists (recovery-instructions.sh) but needs to be comprehensive — read CLAUDE.md, current session context, SESSION_LOG.md, current_session.txt, and inject all of it
3. **CLAUDE.md rule:** Keep the ban on /compact. Even though we can't mechanically block it, the Stop hook's session-evaluator WILL flag it as a RED FLAG in the assessment

### 1B: Command Stop Hook vs Agent Stop Hook
Session 67 used command type (bash script with grep) instead of agent type (spawns subagent with file access). The grep approach immediately produced a false positive ("FAIL" matched in test descriptions).

**Trade-off analysis:**
- Agent hook: Fires per-turn when `stop_hook_active=true`, costs tokens each time, but can read files intelligently
- Command hook: Free, deterministic, but grep-based file parsing is brittle

**Fix:** Replace the bash grep patterns with a Python script that does structural parsing of SESSION_LOG.md. Python can properly parse markdown sections, check for phase verdict patterns with context awareness, and avoid false positives from text content. Still command type (no token cost) but much more robust than grep.

### 1C: UX Review Gate — How to Enforce
Session 67 merged the UX review check into the Stop hook bash script. The issue: checking for "ux-reviewer" text in SESSION_LOG.md is too simplistic — sessions without UI work shouldn't require UX review.

**Fix:** The Stop hook Python script should:
1. Check if the session prompt mentions Chrome, screenshots, or UI work
2. If yes: check if SESSION_LOG.md mentions ux-reviewer invocation
3. If screenshots exist in `docs/screenshots/session-{N}/` but no UX review: block
4. If no UI work indicated: skip the UX check

### 1D: /clear Confirmed Interactive-Only
Session 67 confirmed: `/clear` does not work in `-p` (pipe) mode. A `scripts/run_session.sh` was created that splits prompts at `## PHASE` markers and runs each as a separate `claude -p` invocation with checkpoint files.

**Status:** Script exists but has NEVER been tested. Session 68 must test it.

### 1E: Parallelization Regression
Session 66 successfully used worktree parallelization (3 subagents, merged cleanly, ~30 min savings). Sessions 66b and 67 did NOT use parallelization. The UserPromptSubmit hook injects a reminder, but there's no enforcement.

**Fix:** The parallelization reminder from UserPromptSubmit is sufficient for now — it's a nudge, not a gate. The real fix is including explicit parallelization plans in each session prompt (which we're doing in this prompt).

---

## PART 2: HARNESS REGRESSION CHECKLIST

These are features we've built across sessions 65-67 that must all still work. Phase 1 of Session 68 runs through this checklist.

| # | Feature | Introduced | How to Verify |
|---|---------|-----------|--------------|
| 1 | Stop hook blocks when assessment missing | 67 | `echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR=. bash .claude/hooks/session-stop-gate.sh` with no assessment file |
| 2 | Stop hook approves when assessment exists | 67 | Same command with assessment file present |
| 3 | PreCompact manual warning | 67 | `echo '{"trigger":"manual"}' | bash .claude/hooks/[precompact-script]` — verify exit code and stderr |
| 4 | PreCompact auto recovery injection | 67 | `echo '{"trigger":"auto"}' | bash .claude/hooks/recovery-instructions.sh` — verify context output |
| 5 | UserPromptSubmit parallelization reminder | 67 | Check that the echo command injects text |
| 6 | PreToolUse test-before-commit | 65d | Attempt a git commit — pytest should run first |
| 7 | PostToolUse AD reminder | 65d | Edit an ML file — should see AD update reminder |
| 8 | Upload pipeline works end-to-end | 66b | Upload a real photo, verify face count increases |
| 9 | Session log archival + INDEX.md | 66 | `ls docs/session_logs/` should have indexed logs |
| 10 | ux-reviewer subagent exists | 66 | `cat .claude/agents/ux-reviewer.md` |
| 11 | session-evaluator subagent exists | 66 | `cat .claude/agents/session-evaluator.md` |
| 12 | fix-prompt-writer subagent exists | 66 | `cat .claude/agents/fix-prompt-writer.md` |
| 13 | run_session.sh exists | 67 | `ls scripts/run_session.sh` |
| 14 | GEDCOM admin UI accessible | 66 | Navigate to /admin/gedcom |
| 15 | 3588+ tests pass | 67 | `pytest tests/ -x -q` count |

---

## PART 3: STOP HOOK UPGRADE PLAN

Replace `.claude/hooks/session-stop-gate.sh` (bash + grep) with `.claude/hooks/session-stop-gate.py` (Python, structural parsing).

```python
#!/usr/bin/env python3
"""Session stop gate - blocks Claude from stopping until session requirements met."""
import sys, json, os, re

def main():
    input_data = json.load(sys.stdin)
    
    # Don't block on second try (prevent infinite loops)
    if input_data.get("stop_hook_active"):
        print(json.dumps({"decision": "approve", "reason": "Approving on retry"}))
        return
    
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    session_file = os.path.join(project_dir, ".claude", "current_session.txt")
    
    if not os.path.exists(session_file):
        # No session tracking — approve (non-session work)
        print(json.dumps({"decision": "approve", "reason": "No session tracking active"}))
        return
    
    session_id = open(session_file).read().strip()
    missing = []
    
    # Check 1: Assessment file exists
    assessment = os.path.join(project_dir, "docs", "assessments", f"session-{session_id}-assessment.md")
    if not os.path.exists(assessment):
        missing.append(f"Assessment file missing: docs/assessments/session-{session_id}-assessment.md")
    
    # Check 2: SESSION_LOG.md has phase verdicts
    session_log = os.path.join(project_dir, "SESSION_LOG.md")
    if os.path.exists(session_log):
        log_content = open(session_log).read()
        # Check for phase completion markers (flexible patterns)
        phase_pattern = re.compile(r'###?\s+Phase\s+\d', re.IGNORECASE)
        complete_pattern = re.compile(r'(COMPLETE|PASS|DONE)', re.IGNORECASE)
        phases = phase_pattern.findall(log_content)
        if phases and not complete_pattern.search(log_content):
            missing.append("SESSION_LOG has phases but none marked COMPLETE/PASS/DONE")
        
        # Check 3: If any phase has FAIL verdict, need b-path prompt
        fail_pattern = re.compile(r'Phase\s+\d.*?(?:FAIL|FAILED)', re.IGNORECASE)
        if fail_pattern.search(log_content):
            bpath = os.path.join(project_dir, "docs", "prompts", f"session-{session_id}b-prompt.md")
            if not os.path.exists(bpath):
                missing.append(f"Phase has FAIL but no b-path prompt: docs/prompts/session-{session_id}b-prompt.md")
    
    # Check 4: If screenshots exist, was ux-reviewer invoked?
    screenshot_dir = os.path.join(project_dir, "docs", "screenshots", f"session-{session_id}")
    if os.path.exists(screenshot_dir) and os.listdir(screenshot_dir):
        if os.path.exists(session_log):
            log_content = open(session_log).read()
            if "ux-reviewer" not in log_content.lower() and "ux review" not in log_content.lower():
                missing.append("Screenshots exist but ux-reviewer was not invoked")
    
    if missing:
        reasons = " | ".join(missing)
        print(json.dumps({"decision": "block", "reason": f"Missing: {reasons}. Complete these before stopping."}))
    else:
        print(json.dumps({"decision": "approve", "reason": f"Session {session_id} outputs verified."}))

if __name__ == "__main__":
    main()
```

**Why Python over bash grep:**
- Regex with context awareness (FAIL in a phase verdict vs FAIL in test description)
- Proper JSON output (no string escaping issues)
- Easy to extend (add more checks without fragile grep chains)
- Still command type (no LLM cost)

---

## PART 4: PRECOMPACT RECOVERY FIX

Since PreCompact can't block, change strategy:

**PreCompact (manual):** Keep the loud warning + transcript backup. Change from `exit 2` (which doesn't block) to `exit 0` with loud stderr warning.

**SessionStart (compact matcher):** Create `.claude/hooks/post-compact-recovery.sh`:
```bash
#!/bin/bash
# Fires when session resumes after compaction
# Re-inject ALL critical context from disk

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

echo "⚠️ COMPACTION OCCURRED — RE-READING ALL CONTEXT FROM DISK ⚠️"
echo ""
echo "=== CLAUDE.md ==="
cat "$PROJECT_DIR/CLAUDE.md" 2>/dev/null
echo ""
echo "=== Current Session ==="
cat "$PROJECT_DIR/.claude/current_session.txt" 2>/dev/null
echo ""
echo "=== SESSION_LOG.md ==="
cat "$PROJECT_DIR/SESSION_LOG.md" 2>/dev/null
echo ""
echo "REMINDER: /compact is BANNED. Use /clear instead. This compaction was logged as a RED FLAG."
```

Register in settings.json:
```json
"SessionStart": [
  {
    "matcher": "compact",
    "hooks": [
      { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/post-compact-recovery.sh\"" }
    ]
  }
]
```

---

## PART 5: DEFERRED ITEMS

### From Session 67
1. **UX-103 (P1):** Full-bleed photo view dead end — no CTAs, overlays, metadata
2. **144 rate-limited photos:** Retry command ready, $1.50-4.50 API cost (AUTHORIZED by Nolan)
3. **run_session.sh testing:** Never tested, must validate
4. **LoRA training data audit:** Next ML milestone, keeps getting deferred

### From Session 66b
5. **Photo count discrepancy:** 274 production vs 271 local (3-photo delta)
6. **GEDCOM upload end-to-end:** Still never tested through web UI with real file

---

## PART 6: PARALLELIZATION PLAN FOR SESSION 68

After Phase 0 (orient) and Phase 1 (regression checks + hook upgrades):

**Parallel workstream A:** UX-103 P1 fix + UX review (touches app/main.py, templates)
**Parallel workstream B:** 144 photo retry (touches scripts/, Gemini API, no app code)
**Parallel workstream C:** LoRA training data audit (touches docs/, ML analysis, no app code)

These three are completely independent. A touches app code, B touches scripts + API, C touches docs/ML.

After parallel merge:
**Sequential:** run_session.sh test → evaluation

---

## PART 7: SESSION PRIORITY ORDER

1. **REGRESSION CHECKS (Phase 1):** Verify all harness features still work
2. **HOOK UPGRADES (Phase 2):** Python stop gate, PreCompact recovery, settings.json update
3. **PARALLEL WORK (Phase 3):** UX-103 fix + photo retry + LoRA audit
4. **MERGE + TEST (Phase 4):** Merge parallel branches, full test suite
5. **run_session.sh VALIDATION (Phase 5):** First real test of phase-splitting runner
6. **EVALUATION (Phase 6):** Stop hook should enforce this
