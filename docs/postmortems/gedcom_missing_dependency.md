# GEDCOM Upload Missing Dependency

Date: 2026-02-17
Severity: Critical

## What Happened

The GEDCOM upload feature on the production admin page (/admin/gedcom) returned 500 with a `ModuleNotFoundError` for the `python-gedcom` package. The feature worked in local development but was completely broken in production.

## Root Cause

`rhodesli_ml/importers/gedcom_parser.py` depended on the `python-gedcom` package, but it was never added to `requirements.txt`. The package was installed in the local virtualenv (so development worked), but the Docker build never installed it.

## Which Session Introduced It

Session 35 (GEDCOM Import + Relationship Graph), which added the GEDCOM parser and identity matcher.

## Why Tests Didn't Catch It

Tests mocked the GEDCOM parsing layer, so the actual `python-gedcom` import was never exercised during the test suite. The import succeeded locally because the package existed in the development venv.

## Fix Applied

Added `python-gedcom` to `requirements.txt` so the Docker build installs it.

## Prevention Added

`tests/test_dependency_gate.py` now scans all imports used by `app/` and `core/` modules and verifies each resolves successfully. Critical imports that have broken production get explicit test cases. CLAUDE.md rules require checking `requirements.txt` when adding new package dependencies.
