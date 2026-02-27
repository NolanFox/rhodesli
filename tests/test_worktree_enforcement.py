"""Tests for worktree enforcement scripts (Session 71D Phase 4)."""

import os
import stat
from pathlib import Path


# Resolve project root (two levels up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestEnforceWorktreeScript:
    """Tests for scripts/enforce_worktree.sh."""

    def test_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "enforce_worktree.sh"
        assert script.exists(), f"enforce_worktree.sh not found at {script}"

    def test_script_is_executable(self):
        script = PROJECT_ROOT / "scripts" / "enforce_worktree.sh"
        mode = os.stat(script).st_mode
        assert mode & stat.S_IXUSR, "enforce_worktree.sh is not executable (user)"

    def test_script_checks_main_branch(self):
        script = PROJECT_ROOT / "scripts" / "enforce_worktree.sh"
        content = script.read_text()
        assert '"main"' in content, "enforce_worktree.sh must check for 'main' branch"

    def test_script_checks_master_branch(self):
        script = PROJECT_ROOT / "scripts" / "enforce_worktree.sh"
        content = script.read_text()
        assert '"master"' in content, "enforce_worktree.sh must check for 'master' branch"

    def test_script_exits_nonzero_on_main(self):
        script = PROJECT_ROOT / "scripts" / "enforce_worktree.sh"
        content = script.read_text()
        assert "exit 1" in content, "enforce_worktree.sh must exit 1 when on main"


class TestMergeTracksScript:
    """Tests for scripts/merge_tracks.sh."""

    def test_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "merge_tracks.sh"
        assert script.exists(), f"merge_tracks.sh not found at {script}"

    def test_script_is_executable(self):
        script = PROJECT_ROOT / "scripts" / "merge_tracks.sh"
        mode = os.stat(script).st_mode
        assert mode & stat.S_IXUSR, "merge_tracks.sh is not executable (user)"

    def test_script_contains_test_gate(self):
        script = PROJECT_ROOT / "scripts" / "merge_tracks.sh"
        content = script.read_text()
        assert "pytest" in content, "merge_tracks.sh must include a pytest test gate"

    def test_script_uses_no_ff_merge(self):
        script = PROJECT_ROOT / "scripts" / "merge_tracks.sh"
        content = script.read_text()
        assert "--no-ff" in content, "merge_tracks.sh must use --no-ff for merge commits"

    def test_script_checks_uncommitted_files(self):
        script = PROJECT_ROOT / "scripts" / "merge_tracks.sh"
        content = script.read_text()
        assert "status --porcelain" in content, (
            "merge_tracks.sh must check for uncommitted files"
        )


class TestWorktreeEnforcementRule:
    """Tests for .claude/rules/worktree-enforcement.md."""

    def test_rule_file_exists(self):
        rule = PROJECT_ROOT / ".claude" / "rules" / "worktree-enforcement.md"
        assert rule.exists(), f"worktree-enforcement.md not found at {rule}"

    def test_rule_references_enforce_script(self):
        rule = PROJECT_ROOT / ".claude" / "rules" / "worktree-enforcement.md"
        content = rule.read_text()
        assert "enforce_worktree.sh" in content, (
            "Rule must reference enforce_worktree.sh"
        )

    def test_rule_references_merge_script(self):
        rule = PROJECT_ROOT / ".claude" / "rules" / "worktree-enforcement.md"
        content = rule.read_text()
        assert "merge_tracks.sh" in content, "Rule must reference merge_tracks.sh"
