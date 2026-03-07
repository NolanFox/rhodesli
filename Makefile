SHELL := /bin/bash
# Find venv: local venv first, then main repo's venv (for worktrees)
REPO_ROOT := $(shell git rev-parse --git-common-dir 2>/dev/null | xargs dirname)
VENV := $(shell [ -d venv ] && echo venv || echo $(REPO_ROOT)/venv)
PYTEST := $(VENV)/bin/pytest

.PHONY: test test-fast test-full test-ml

test-fast:
	$(PYTEST) tests/ -x -q -n 8 -m "not slow" --timeout=30 --dist loadscope

test-full:
	$(PYTEST) tests/ -x -q -n auto --timeout=60

test-ml:
	$(PYTEST) rhodesli_ml/tests/ -x -q -n auto --timeout=60

test: test-fast
