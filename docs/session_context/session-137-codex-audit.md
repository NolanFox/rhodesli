# Session 137 Codex Audit Report

**Tool**: Claude subagent (audit role, not Codex CLI — Supabase down, overnight session)
**Scope**: All 4 tracks — refactor, flaky tests, ML tests, TOOLS-005 design
**Files reviewed**: app/components/*.py, tests/conftest.py, rhodesli_ml/tests/test_*.py

## Findings

| Severity | Count | Key Issues |
|----------|-------|------------|
| P0 | 0 | — |
| P1 | 2 | Duplicate divergent `image_transform_toolbar`; fragile `__file__`-relative path |
| P2 | 5 | Silent exception swallowing; brittle cache reset maintenance; file naming |
| P3 | 4 | Observations on structure, patterns, and quality |

## P1 — Fixed in Session 137

### P1-1: Duplicate `image_transform_toolbar` (FIXED)
- forms.py had divergent implementation from main.py (different HTMX wiring)
- **Fix**: Removed forms.py version, removed from __init__.py re-exports
- **Commit**: b6156e9

### P1-2: `_get_onboarding_surnames` fragile path (FIXED)
- Used `Path(__file__).resolve().parent.parent.parent` — hardcoded depth
- **Fix**: Replaced with `core.config.DATA_DIR`
- **Commit**: b6156e9

## P2 — Fixed or Deferred

### P2-1: Broad `except Exception: pass` in `_admin_bar` (FIXED)
- Added `logging.warning()` with exc_info
- **Commit**: b6156e9

### P2-2: Conftest cache reset brittle (DEFERRED)
- 30+ caches reset by name — no enforcement that new caches get added
- **Mitigation**: Comments near cache declarations recommended for Phase 2

### P2-3: Conftest bare `try/except (ImportError, AttributeError): pass` (DEFERRED)
- Silent swallow if cache renamed — low risk given existing test infrastructure

### P2-4: `login_modal` lazy import pattern (ACCEPTED)
- Correct behavior for test patching, inconsistent with badges.py but not harmful

### P2-5: test_nl_query.py in both tests/ and rhodesli_ml/tests/ (ACCEPTED)
- Different scopes: route-level vs parser-level. Naming collision noted.

## Security Review: CLEAN
- No auth bypass, no XSS, no injection risks
- Components are pure rendering — auth guards stay in route modules

## Data Integrity Review: CLEAN
- No data file modifications
- No write path changes

## Value Assessment
- **Rating**: MODERATE — caught the duplicate function (P1-1) which would have caused confusion. Path fix (P1-2) prevents future silent breakage. Logging fix (P2-1) improves observability.
- **Would we have found P1-1 ourselves?** Unlikely before it caused a bug.
