"""Tests for worktree enforcement (merge.sh + Claude Code hooks)."""

import json
import os
import stat
from pathlib import Path


# Resolve project root (two levels up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMergeScript:
    """Tests for scripts/merge.sh — the canonical merge tool."""

    def test_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "merge.sh"
        assert script.exists(), f"merge.sh not found at {script}"

    def test_script_is_executable(self):
        script = PROJECT_ROOT / "scripts" / "merge.sh"
        mode = os.stat(script).st_mode
        assert mode & stat.S_IXUSR, "merge.sh is not executable (user)"

    def test_script_uses_no_ff_merge(self):
        script = PROJECT_ROOT / "scripts" / "merge.sh"
        content = script.read_text()
        assert "--no-ff" in content, "merge.sh must use --no-ff for merge commits"

    def test_script_runs_tests(self):
        script = PROJECT_ROOT / "scripts" / "merge.sh"
        content = script.read_text()
        assert "test" in content.lower(), "merge.sh must include a test step"

    def test_old_scripts_removed(self):
        """Ensure legacy duplicate scripts are cleaned up."""
        for name in ["enforce_worktree.sh", "merge-worktree.sh", "merge_tracks.sh"]:
            script = PROJECT_ROOT / "scripts" / name
            assert not script.exists(), f"Legacy script {name} should be removed"


class TestWorktreeEnforcementRule:
    """Tests for .claude/rules/worktree-enforcement.md."""

    def test_rule_file_exists(self):
        rule = PROJECT_ROOT / ".claude" / "rules" / "worktree-enforcement.md"
        assert rule.exists(), f"worktree-enforcement.md not found at {rule}"

    def test_rule_references_merge_script(self):
        rule = PROJECT_ROOT / ".claude" / "rules" / "worktree-enforcement.md"
        content = rule.read_text()
        assert "merge.sh" in content, "Rule must reference merge.sh"


class TestClaudeCodeHooksEnforcement:
    """Tests that Claude Code hooks enforce worktree discipline."""

    def test_settings_has_pretooluse_hook(self):
        settings = PROJECT_ROOT / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        hooks = data.get("hooks", {})
        assert "PreToolUse" in hooks, "settings.json must have PreToolUse hooks"

    def test_pretooluse_blocks_main_commits(self):
        settings = PROJECT_ROOT / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        pre_hooks = data["hooks"]["PreToolUse"]
        # Find the Bash matcher hook
        bash_hook = next((h for h in pre_hooks if h.get("matcher") == "Bash"), None)
        assert bash_hook is not None, "Must have a Bash PreToolUse hook"
        cmd = bash_hook["hooks"][0]["command"]
        assert "parallel_session_active" in cmd, "PreToolUse hook must check for parallel_session_active"

    def test_stop_hook_allows_merge_sessions(self):
        """Stop hook (inline or script) must handle merge sessions."""
        settings = PROJECT_ROOT / ".claude" / "settings.json"
        data = json.loads(settings.read_text())
        stop_hooks = data["hooks"]["Stop"]
        cmd = stop_hooks[0]["hooks"][0]["command"]
        # Hook may be inline or reference a script file
        if "stop-gate.sh" in cmd:
            # Script file — check the script itself
            script = PROJECT_ROOT / ".claude" / "hooks" / "stop-gate.sh"
            assert script.exists(), "stop-gate.sh script must exist"
            content = script.read_text()
            assert "merge" in content.lower(), "stop-gate.sh must handle merge sessions (skip assessment)"
        else:
            assert "merge" in cmd.lower(), "Stop hook must handle merge sessions (skip assessment)"
