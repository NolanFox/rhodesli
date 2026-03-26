# Session 137 Audit Reports

## Audit 1: Claude Subagent

**Auditor**: Claude Opus 4.6 subagent (same model as orchestrator)
**Agent type**: Resume (shared session context — NOT independent)
**Scope**: All 4 tracks — refactor, flaky tests, ML tests, TOOLS-005 design
**Date**: 2026-03-25
**Files reviewed**: app/components/*.py, tests/conftest.py, rhodesli_ml/tests/test_*.py

### Findings

| Severity | Count | Key Issues |
|----------|-------|------------|
| P0 | 0 | — |
| P1 | 2 | Duplicate divergent `image_transform_toolbar`; fragile `__file__`-relative path |
| P2 | 5 | Silent exception swallowing; brittle cache reset maintenance; file naming |
| P3 | 4 | Observations on structure, patterns, and quality |

### P1 — Fixed in Session 137

#### P1-1: Duplicate `image_transform_toolbar` (FIXED)
- forms.py had divergent implementation from main.py (different HTMX wiring)
- **Fix**: Removed forms.py version, removed from __init__.py re-exports
- **Commit**: b6156e9

#### P1-2: `_get_onboarding_surnames` fragile path (FIXED)
- Used `Path(__file__).resolve().parent.parent.parent` — hardcoded depth
- **Fix**: Replaced with `core.config.DATA_DIR`
- **Commit**: b6156e9

### P2 — Fixed or Deferred
- P2-1: Broad `except Exception: pass` in `_admin_bar` — FIXED (added logging.warning)
- P2-2: Conftest cache reset brittle — DEFERRED
- P2-3: Conftest bare try/except — DEFERRED
- P2-4: login_modal lazy import pattern — ACCEPTED
- P2-5: test_nl_query.py name collision — ACCEPTED

### Value Assessment
- **Rating**: MODERATE
- **Would we have found these ourselves?** P1-1 unlikely before it caused a bug. Others eventually.

---

## Audit 2: Codex CLI (Independent)

**Auditor**: Codex CLI v0.115.0 (gpt-5.4, reasoning effort: xhigh)
**Agent type**: Independent (fresh context, no prior knowledge of Claude's findings)
**Scope**: git diff b653855..HEAD — all Session 137 changes
**Date**: 2026-03-25
**Tokens used**: 301,719

### Findings

| Severity | Count | Key Issues |
|----------|-------|------------|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | DATA_DIR cwd-relative regression; wrong rate-limit patch target; placeholder assertions |
| P3 | 1 | Mobile nav renders clickable `|` separator |

### P2 Issues

#### P2-1: `_get_onboarding_surnames` cwd-relative regression
- `Path(DATA_DIR) / "surname_variants.json"` depends on process working directory when DATA_DIR is relative `"data"`. Codex **reproduced** this: importing from `/tmp` returns `[]`.
- **Note**: Claude's fix (P1-2) traded one fragility for another. The `__file__`-relative path was wrong in depth but always worked. The `DATA_DIR` path is correct conceptually but fails when cwd != repo root.
- **Fix needed**: Use `Path(__file__).resolve().parent.parent.parent / DATA_DIR / "surname_variants.json"` or make DATA_DIR absolute in config.py.

#### P2-2: xfail tests patch wrong rate-limit symbol
- All 3 estimate_v2 test files patch `app.rate_limit.check_rate_limit` but the route imports it as an alias at `app.estimate_routes.check_rate_limit`. Patches are inert. Not blocking now (xfail), but will cause confusion when implementing TOOLS-005.
- **Fix needed in Session 138**: Change patches to `app.estimate_routes.check_rate_limit`.

#### P2-3: Spec placeholder tests assert wrong things
- `test_gedcom_enrichment_level_logged` claims to verify enrichment_level but only checks Gemini was called.
- `test_empty_text_hints_falls_back_to_visual_only` checks `gedcom_context` not text hints.
- **Action**: These are xfail skeletons, so they're roadmap notes not real tests. Acceptable for now, note for TOOLS-005 implementation.

### P3 Issues

#### P3-1: Mobile nav renders clickable `|` separator
- `_public_nav_links()` includes `Span("|")` as separator. Mobile nav clone at nav.py:257 converts ALL items to anchors, creating a clickable `|` entry.
- Codex **reproduced** this by rendering the nav HTML.
- **Fix needed**: Filter out Span elements before mobile clone.

### Security: CLEAN
- No XSS, injection, or auth bypass in components
- No circular import issues confirmed

### ML Tests: CLEAN
- test_multi_pass, test_nl_query, test_prompt_manifest all reviewed — no material issues

### Value Assessment
- **Rating**: STRONG — found 3 issues Claude missed, including a **reproduced regression** (DATA_DIR cwd-relative).
- **Would we have found these ourselves?** The DATA_DIR regression: unlikely until production. Rate-limit patch target: unlikely until TOOLS-005 implementation. Mobile nav `|`: unlikely without visual testing.

---

## Comparison: Claude Subagent vs Codex CLI

| Aspect | Claude Subagent | Codex CLI |
|--------|----------------|-----------|
| Model | Claude Opus 4.6 | gpt-5.4 |
| Independence | NO (shared context) | YES (fresh context) |
| P1 findings | 2 (both real) | 0 |
| P2 findings | 5 | 3 |
| **Unique findings** | Duplicate function, brittle cache reset | cwd-relative regression, wrong patch target, mobile `|` |
| **Reproduced issues** | No | Yes (DATA_DIR, mobile `|`) |
| Tokens | ~127K | ~302K |
| Time | ~24 min | ~10 min |
| **Overlap** | DATA_DIR path issue (both found, different angles) | |

**Key insight**: Claude found structural/design issues (duplicate code, brittle patterns). Codex found behavioral/runtime issues (reproduced the DATA_DIR regression, traced the patch target through import chains). Both missed things the other caught. **Use both for critical sessions.**
