"""Allowlist-parity test for session-end artifact paths (Track 3, Phase 3B / Lesson 177).

Asserts that every canonical session-end artifact path mentioned in
`.claude/rules/session-defaults.md` (and adjacent rules) is allowlisted by
`.claude/hooks/pre-work-clear-gate.sh` so it remains writable even when the
600-line transcript gate fires at session end.

If this test fails, the hook's allowlist drifted from the actual session-end
artifact set — fix the hook (preferred) or update the artifact list with a
note explaining the change. Lesson 177 names this exact failure mode.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

import pytest

# Reuse the helper from test_hooks_clear_gate.py. Importing it directly keeps
# the hook-runner contract in one place.
from tests.test_hooks_clear_gate import _run_hook


# Canonical session-end artifact paths. NN is a session number; the trailing
# basename can be anything in practice (assessment-NNb-foo.md is fine), but the
# allowlist matches the directory or filename anchor, which is what we test.
CANONICAL_ARTIFACT_PATHS = [
    # Per-session artifacts (directories — allowlisted via /<dir>/* glob).
    "docs/assessments/session-NN-assessment.md",
    "docs/session_logs/session-NN-log.md",
    "docs/session_context/session-NN-context.md",
    "docs/session_context/session-NN-codex-audit.md",
    "docs/feedback/session-NN-feedback.md",
    "docs/feedback/session-NN-shadow-eval-detroit-rerun.md",
    "docs/prompts/session-NN-prompt.md",
    # Repo-root canonical files (allowlisted as exact filenames).
    "CHANGELOG.md",
    "ROADMAP.md",
    "docs/BACKLOG.md",
    "BACKLOG.md",
    "SESSION_LOG.md",
    # Lessons + todo (mixture of file + dir match).
    "tasks/lessons.md",
    "tasks/lessons/data-lessons.md",
    "tasks/todo.md",
    # Rules + hooks (allowlisted via .claude/*).
    ".claude/rules/some-rule.md",
    ".claude/hooks/some-hook.sh",
]


def _resolved_in_repo(path_relative_to_repo: str, repo_dir: str) -> str:
    """Return an absolute path inside the test repo for a given relative path.

    The hook canonicalizes via os.path.realpath against `git rev-parse
    --show-toplevel`. We mirror that — pass the realpath of the path inside
    the temporary git repo so the hook treats it as repo-anchored.
    """
    return os.path.realpath(os.path.join(repo_dir, path_relative_to_repo))


@pytest.mark.parametrize("artifact_path", CANONICAL_ARTIFACT_PATHS)
def test_session_end_artifact_is_allowlisted(artifact_path: str) -> None:
    """Each canonical session-end artifact must be exempt from the clear gate.

    Uses a 1000-line transcript (well above the 600-line block threshold) so
    the only way the hook returns 0 is via the allowlist branch. If rc != 0,
    the path slipped out of the allowlist (Lesson 177 regression).
    """
    # The _run_hook helper runs the hook from a fresh git repo at tmpdir.
    # Pass the artifact's repo-relative path so canonicalization resolves to
    # tmpdir/<artifact_path>, which the hook's case statement matches via the
    # $REPO/<dir>/* and $REPO/<file> patterns.
    rc, _stdout, stderr = _run_hook(
        transcript_lines=1000,
        file_path=artifact_path,
    )
    assert rc == 0, (
        f"Hook BLOCKED writes to canonical session artifact {artifact_path!r} "
        f"despite high line count — allowlist drift (Lesson 177). "
        f"stderr: {stderr!r}"
    )


def test_non_artifact_path_is_blocked_at_high_lines() -> None:
    """Sanity check: a non-allowlisted path IS blocked at 1000 lines.

    Without this, the parametrized test above could pass for the wrong reason
    (e.g., if the hook silently returned 0 for everything).
    """
    rc, _stdout, stderr = _run_hook(
        transcript_lines=1000,
        file_path="app/some_random_file.py",
    )
    assert rc != 0, (
        "Hook MUST block writes to non-allowlisted code paths at 1000 lines. "
        "If this passes, the allowlist parity test above is meaningless."
    )
