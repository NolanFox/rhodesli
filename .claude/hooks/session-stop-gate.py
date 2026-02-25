#!/usr/bin/env python3
"""Session stop gate - blocks Claude from stopping until session requirements met.

Replaces session-stop-gate.sh (bash + grep) with structural markdown parsing
to avoid false positives from FAIL appearing in test descriptions.

AD-167: Python stop gate replaces bash grep.
"""
import sys
import json
import os
import re


def main():
    input_data = json.load(sys.stdin)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    session_file = os.path.join(project_dir, ".claude", "current_session.txt")

    if not os.path.exists(session_file):
        print(json.dumps({"decision": "approve", "reason": "No session tracking active"}))
        return

    session_id = open(session_file).read().strip()
    if not session_id or session_id == "unknown":
        print(json.dumps({"decision": "approve", "reason": "No active session tracking"}))
        return

    assessment = os.path.join(project_dir, "docs", "assessments", f"session-{session_id}-assessment.md")
    session_log = os.path.join(project_dir, "SESSION_LOG.md")

    # If already blocked once (stop_hook_active=true), only check assessment
    stop_active = str(input_data.get("stop_hook_active", "false")).lower()
    if stop_active == "true":
        if os.path.exists(assessment):
            print(json.dumps({"decision": "approve", "reason": "Assessment file now exists. Session complete."}))
        else:
            print(json.dumps({
                "decision": "block",
                "reason": f"Assessment file STILL missing: docs/assessments/session-{session_id}-assessment.md — write it now."
            }))
        return

    missing = []

    # Check 1: Assessment file exists
    if not os.path.exists(assessment):
        missing.append(f"Assessment file (docs/assessments/session-{session_id}-assessment.md)")

    # Check 2: SESSION_LOG.md has phase verdicts
    log_content = ""
    if os.path.exists(session_log):
        log_content = open(session_log).read()
        # Look for phase headers with completion markers
        # Pattern: "### Phase N: ... — COMPLETE/PASS/DONE/SKIP"
        phase_verdicts = re.findall(
            r'^###?\s+Phase\s+\d+.*?(?:COMPLETE|PASS|DONE|SKIP)',
            log_content, re.MULTILINE | re.IGNORECASE
        )
        if not phase_verdicts:
            missing.append("Phase verdicts in SESSION_LOG.md (no phases marked COMPLETE/PASS/DONE)")

    # Check 3: If any phase has FAIL verdict (structural check — only in phase header lines)
    if log_content:
        # Only match FAIL in phase verdict lines, not in arbitrary text
        fail_lines = re.findall(
            r'^###?\s+Phase\s+\d+.*?FAIL',
            log_content, re.MULTILINE | re.IGNORECASE
        )
        if fail_lines:
            bpath = os.path.join(project_dir, "docs", "prompts", f"session-{session_id}b-prompt.md")
            if not os.path.exists(bpath):
                missing.append(f"B-path prompt: Phase has FAIL but no docs/prompts/session-{session_id}b-prompt.md")

    # Check 4: If screenshots exist, was ux-reviewer invoked?
    screenshot_dir = os.path.join(project_dir, "docs", "screenshots", f"session-{session_id}")
    if os.path.exists(screenshot_dir):
        screenshots = [f for f in os.listdir(screenshot_dir) if not f.startswith('.')]
        if screenshots and log_content:
            ux_mentioned = (
                "ux-reviewer" in log_content.lower()
                or "ux review" in log_content.lower()
                or "ux_review" in log_content.lower()
            )
            if not ux_mentioned:
                missing.append(f"UX review: {len(screenshots)} screenshots but no ux-reviewer invocation logged")

    if missing:
        reasons = " | ".join(missing)
        print(json.dumps({"decision": "block", "reason": f"Missing: {reasons}. Complete these before stopping."}))
    else:
        print(json.dumps({"decision": "approve", "reason": f"Session {session_id} outputs verified."}))


if __name__ == "__main__":
    main()
