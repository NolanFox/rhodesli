"""Tests for the pre-work-clear-gate.sh transcript-based /clear enforcement hook.

Verifies the hook reads transcript_path from stdin JSON, counts lines,
and blocks or warns based on thresholds.
"""

import json
import os
import subprocess
import tempfile

import pytest

HOOK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks", "pre-work-clear-gate.sh"))


def _run_hook(
    transcript_lines=0,
    session_mode="implementation",
    file_path="/some/code.py",
    transcript_path=None,
    omit_transcript=False,
):
    """Run the pre-work-clear-gate.sh hook with simulated input.

    Args:
        transcript_lines: Number of lines to put in the fake transcript file.
        session_mode: Session mode to write to session_mode.txt.
        file_path: The file being edited (checked for exemptions).
        transcript_path: Override transcript path. If None, creates a temp file.
        omit_transcript: If True, don't include transcript_path in the input JSON.

    Returns:
        (returncode, stdout, stderr)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # The hook canonicalizes file paths against `git rev-parse --show-toplevel`
        # to defeat `../` traversal bypasses (Codex P0 fix, commit ba91f949).
        # Without a git repo at cwd, REPO="" and the session-doc allowlist branch
        # is skipped — making it impossible to test exemptions. Initialize a
        # minimal repo in tmpdir so the canonicalization branch fires.
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )

        # Create session mode file
        claude_dir = os.path.join(tmpdir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        with open(os.path.join(claude_dir, "session_mode.txt"), "w") as f:
            f.write(session_mode)

        # Create transcript file with specified number of lines
        if transcript_path is None and not omit_transcript:
            transcript_file = os.path.join(tmpdir, "transcript.jsonl")
            with open(transcript_file, "w") as f:
                for i in range(transcript_lines):
                    f.write(json.dumps({"type": "message", "index": i}) + "\n")
            transcript_path = transcript_file

        # Build input JSON
        input_data = {
            "tool_input": {"file_path": file_path},
        }
        if not omit_transcript and transcript_path is not None:
            input_data["transcript_path"] = transcript_path

        result = subprocess.run(
            ["bash", HOOK_PATH],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr


class TestTranscriptBasedClearGate:
    """Test the transcript line-count enforcement logic."""

    def test_low_transcript_allows_edit(self):
        """Under 400 lines: no warning, no block."""
        rc, stdout, stderr = _run_hook(transcript_lines=100)
        assert rc == 0
        assert "BLOCKED" not in stderr
        assert "advisory" not in stdout.lower()

    def test_medium_transcript_warns(self):
        """400-799 lines: advisory warning but no block."""
        rc, stdout, stderr = _run_hook(transcript_lines=500)
        assert rc == 0
        assert "Context advisory" in stdout
        assert "BLOCKED" not in stderr

    def test_high_transcript_blocks(self):
        """800+ lines: blocks with exit 2."""
        rc, stdout, stderr = _run_hook(transcript_lines=850)
        assert rc == 2
        assert "BLOCKED" in stderr
        assert "850" in stderr

    def test_exactly_400_warns(self):
        """Boundary: exactly 400 lines triggers warning."""
        rc, stdout, stderr = _run_hook(transcript_lines=400)
        assert rc == 0
        assert "advisory" in stdout.lower() or "Context" in stdout

    def test_exactly_800_blocks(self):
        """Boundary: exactly 800 lines triggers block."""
        rc, stdout, stderr = _run_hook(transcript_lines=800)
        assert rc == 2
        assert "BLOCKED" in stderr

    def test_299_lines_no_warning(self):
        """Just under the 300-line warning threshold: no warning."""
        rc, stdout, stderr = _run_hook(transcript_lines=299)
        assert rc == 0
        assert "advisory" not in stdout.lower()
        assert "Context" not in stdout


class TestSessionModeBypass:
    """Interactive and continuation modes skip enforcement."""

    def test_interactive_mode_skips(self):
        """Interactive mode allows edits regardless of transcript size."""
        rc, stdout, stderr = _run_hook(transcript_lines=1000, session_mode="interactive")
        assert rc == 0
        assert "BLOCKED" not in stderr

    def test_continuation_mode_skips(self):
        """Continuation mode allows edits regardless of transcript size."""
        rc, stdout, stderr = _run_hook(transcript_lines=1000, session_mode="continuation")
        assert rc == 0
        assert "BLOCKED" not in stderr


class TestSessionDocExemptions:
    """Session docs are always allowed even when context is heavy."""

    @pytest.mark.parametrize(
        "path",
        [
            "docs/assessments/session-143-assessment.md",
            "docs/session_logs/session-143-log.md",
            "docs/session_context/session-143-context.md",
            "docs/feedback/session-143-feedback.md",
            "CHANGELOG.md",
            "ROADMAP.md",
            "BACKLOG.md",
            "SESSION_LOG.md",
            ".claude/rules/some-rule.md",
        ],
    )
    def test_session_docs_exempt(self, path):
        """Session documentation files are never blocked."""
        rc, stdout, stderr = _run_hook(transcript_lines=1000, file_path=path)
        assert rc == 0
        assert "BLOCKED" not in stderr


class TestGracefulDegradation:
    """Hook handles missing/invalid transcript gracefully."""

    def test_missing_transcript_path_allows(self):
        """When transcript_path is not in the input, allow the edit."""
        rc, stdout, stderr = _run_hook(transcript_lines=0, omit_transcript=True)
        assert rc == 0

    def test_nonexistent_transcript_file_allows(self):
        """When transcript file doesn't exist, allow the edit."""
        rc, stdout, stderr = _run_hook(transcript_lines=0, transcript_path="/nonexistent/path/transcript.jsonl")
        assert rc == 0

    def test_empty_transcript_allows(self):
        """Empty transcript (0 lines) allows the edit."""
        rc, stdout, stderr = _run_hook(transcript_lines=0)
        assert rc == 0
