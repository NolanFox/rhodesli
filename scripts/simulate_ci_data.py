#!/usr/bin/env python
"""Simulate CI's DATA environment and run a test selection there — catches the
"passes locally, fails CI because CI lacks my local data files" class (Lesson 211:
CI has ZERO committed crops, so tests asserting avatar/og:image/crop presence on
real data fail only in CI).

How: CI does `git checkout` and gets ONLY git-tracked files. Local additionally has
untracked/gitignored data (app/static/crops/*.jpg, embeddings, volume JSON). So we run
the tests in a TEMPORARY git worktree at HEAD — which by construction contains exactly
the git-tracked fileset = CI's data view — using the current venv's interpreter (deps
shared). Non-destructive: never touches the main working tree's files; the worktree is
always removed in a finally.

This is the DATA-subtraction complement to scripts/check_ml_suite_ci_safe.py (the
DEP-subtraction check). Together they mechanize multimodel-sprint ML-4 (the orchestrator
must simulate CI's *constraints*, not just its commands).

Usage:
    source venv/bin/activate
    python scripts/simulate_ci_data.py [pytest args...]
    # default target: the app fast suite (mirrors CI's `make test-fast`)
    python scripts/simulate_ci_data.py tests/test_public_person_page.py -q
Exit 0 = passes under CI's data view. Non-zero = a test depends on local-only data.
"""
import os
import subprocess
import sys
import tempfile


def main() -> int:
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Warn (don't fail) if there are uncommitted changes — the worktree runs HEAD, so
    # uncommitted edits won't be reflected. Better to know than to be surprised.
    dirty = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print(
            "WARNING: working tree has uncommitted changes; the worktree runs HEAD, so "
            "those edits are NOT included. Commit first for an accurate simulation.\n",
            file=sys.stderr,
        )

    pytest_args = sys.argv[1:] or [
        "tests/",
        "-x", "-q", "-n", "4", "-m", "not slow", "--timeout=30", "--dist", "loadscope",
    ]

    wt = tempfile.mkdtemp(prefix="ci-data-sim-")
    try:
        print(f"[simulate-ci-data] git worktree add {wt} HEAD (CI's git-tracked data view)")
        subprocess.run(
            ["git", "-C", repo, "worktree", "add", "--detach", wt, "HEAD"],
            check=True, capture_output=True, text=True,
        )
        # Run pytest from the worktree cwd using THIS venv's interpreter (deps shared).
        # Imports resolve app/ + tests/ from the worktree = git-tracked files only.
        env = dict(os.environ)
        env["PYTHONPATH"] = wt + os.pathsep + env.get("PYTHONPATH", "")
        cmd = [sys.executable, "-m", "pytest", *pytest_args]
        print(f"[simulate-ci-data] cwd={wt}\n[simulate-ci-data] {' '.join(cmd)}\n")
        rc = subprocess.run(cmd, cwd=wt, env=env).returncode
        print(
            f"\n=== simulate-ci-data rc={rc} "
            f"({'PASS — holds under CI data view' if rc == 0 else 'FAIL — depends on local-only data (Lesson 211 class)'}) ==="
        )
        return rc
    finally:
        subprocess.run(
            ["git", "-C", repo, "worktree", "remove", "--force", wt],
            capture_output=True, text=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
