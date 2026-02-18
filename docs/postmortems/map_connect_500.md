# /map and /connect 500 Errors in Production

Date: 2026-02-17
Severity: Critical

## What Happened

Both /map and /connect returned 500 Internal Server Error on the production site. Locally, both routes worked fine because the `rhodesli_ml/` package existed on disk.

## Root Cause

Sessions 35-38 added `from rhodesli_ml.graph import ...` and `from rhodesli_ml.importers import ...` to `app/main.py`, but the Dockerfile was never updated to include the `rhodesli_ml/` package. The Docker image had no copy of these modules, so the imports failed at runtime with `ModuleNotFoundError`.

## Which Session Introduced It

Sessions 35-38 (GEDCOM Import, Social Graph, Collections, Map). Each session added new imports from `rhodesli_ml/` subpackages without updating the Dockerfile.

## Why Tests Didn't Catch It

Tests mocked the `rhodesli_ml` imports or ran in the local environment where the package was installed. No test verified that the Dockerfile included COPY directives for every package the web app imports at runtime.

## Fix Applied

Added selective COPY directives to the Dockerfile for the pure-Python runtime modules only:

```dockerfile
COPY rhodesli_ml/graph/ rhodesli_ml/graph/
COPY rhodesli_ml/importers/ rhodesli_ml/importers/
```

This copies only the modules needed at runtime (~200KB), excluding the full ML package with .venv and checkpoints (~3.2GB).

## Prevention Added

`TestDockerfileModuleCoverage` deploy safety tests in `tests/test_sync_api.py` now verify the Dockerfile has COPY directives for every `rhodesli_ml` subpackage that `app/main.py` imports. Lesson 70 in `tasks/lessons.md` codifies the rule: when adding a new import to `app/main.py`, the Dockerfile must be updated in the same commit.
