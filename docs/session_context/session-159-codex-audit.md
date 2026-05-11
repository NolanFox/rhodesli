# Session 159 Phase 5 — Codex Audit (rhodes-wiki Phase 2-4)

**Auditor**: Codex CLI v0.130.0
**Model**: gpt-5-codex (latest, pinned via `~/.codex/config.toml`)
**Reasoning effort**: high (config `model_reasoning_effort = xhigh`)
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: rhodes-wiki `docs/ARCHITECTURE.md`, `CLAUDE.md`, `.claude/rules/*`, `.claude/settings.json`, all `scripts/`, all `tests/`
**Date**: 2026-05-11
**Phase audited**: Session 159 Phases 2-4 (architecture doc + scaffold + parser stubs)
**Invocation**: `codex exec "<prompt>" </dev/null` (working form, no `--full-auto`)

---

## Executive Summary

| Severity | Count | Status |
|---|---|---|
| P0 | 0 | n/a |
| P1 | 6 | **All FIXED in Phase 5 commits** |
| P2 | 4 | 2 FIXED, 2 BACKLOG |
| P3 | 3 | 2 FIXED, 1 BACKLOG (stub-by-design) |

**Verdict from Codex**: FAIL (before fixes)
**Post-fix expected verdict**: PASS (re-audit deferred to Session 160)

---

## Findings (verbatim from Codex)

### P1-1 — Cross-repo bridge not mechanically read-only
- **File:Line**: `.claude/settings.json:8`, `:18`, `:24`
- **Description**: Broad `Bash(python:*)`, `Bash(find:*)`, `Bash(ruff:*)` allows can write/delete inside rhodesli, bypassing the read-only bridge.
- **Recommendation**: Add deny rules for bash targeting `/Users/nolanfox/rhodesli`. Tighten the allow list.
- **Mapped Lesson**: 170, 180, 162
- **Status**: FIXED — tightened settings.json deny list

### P1-2 — Inbox writers accept arbitrary output targets
- **File:Line**: `scripts/write_inbox_entry.py:231,407,475`; `scripts/extract_fb_post.py:193,259,305`
- **Description**: CLIs write to any caller-supplied output path; `build_inbox_entry` has side effects despite name.
- **Recommendation**: Resolve paths, constrain to repo inbox root; reject symlinks/escape paths; strict slug regex; separate pure builder from disk writes.
- **Mapped Lesson**: 162, 168, 170, 180
- **Status**: FIXED — added `_validate_output_path()` guard + slug regex enforcement

### P1-3 — Image download path traversal + SSRF/disk-fill risk
- **File:Line**: `scripts/write_inbox_entry.py:251,253,255,373,383`
- **Description**: `image_id` from parsed JSON used in path → `../../x` escape; URLs unrestricted (no fbcdn allowlist, no private-IP guard, no byte cap).
- **Recommendation**: Internal ordinal filenames; reject path separators; `https://*.fbcdn.net` allowlist; max bytes cap; verify final path under `<entry>/images`.
- **Mapped Lesson**: 168, 170, 180
- **Status**: FIXED — ordinal filenames, fbcdn allowlist, 50MB cap, path containment check

### P1-4 — Validator does not enforce documented §3.1 contract
- **File:Line**: `scripts/validate_inbox_contract.py:28,54,71`; `tests/test_validate_inbox_contract.py:26`
- **Description**: Missing required-field checks for: `fb_post_id`, `post_date`, `post_date_source`, `comments_count_claim`, `comments_count_extracted`, `expansion_complete`, `tagged_people_in_caption`, `places_mentioned`, `language_guesses`, `captured_url_seen_at`, `notes`. Tests bless a non-contract minimal entry.
- **Recommendation**: Schema-driven validator; require all contract keys (nullable explicit); tests fail on drift.
- **Mapped Lesson**: 105, 152
- **Status**: FIXED — validator now checks all §3.1 keys; new tests assert each missing-key path

### P1-5 — Parser output / inbox writer input incompatible
- **File:Line**: `scripts/parse_fb_dom.py:337,539`; `scripts/write_inbox_entry.py:194,319`; `tests/conftest.py:67`
- **Description**: `parse_post()` emits `images[*].src` + nested `post_date`; `write_inbox_entry.py` expects `images[*].original_url` + flat `post_date`. Real parser→writer path silently loses data.
- **Recommendation**: Align one side; integration test: fixture HTML → parse → build_inbox_entry → validate.
- **Mapped Lesson**: 105, 152, 162
- **Status**: FIXED — parser emits `original_url` (renamed from `src`); flat `post_date` (str|null) and `post_date_source` returned at top level; new integration test in `tests/test_integration_e2e.py`

### P1-6 — `download_status` enum drift
- **File:Line**: `docs/ARCHITECTURE.md:352`; `scripts/extract_fb_post.py:127`; `scripts/write_inbox_entry.py:271`; `scripts/validate_inbox_contract.py:25`
- **Description**: Contract docs `ok|failed|expired`; code emits `deferred` too.
- **Recommendation**: Either add `deferred` to §3.1 or remove it from code.
- **Mapped Lesson**: 105, 152
- **Status**: FIXED — added `deferred` to ARCHITECTURE.md §3.1 with semantics note ("--download-images not set or image was skipped intentionally")

### P2-1 — Writes not atomic, not read-back verified
- **File:Line**: `scripts/extract_fb_post.py:262,272`; `scripts/write_inbox_entry.py:417`
- **Description**: Direct file writes; crash leaves partial JSON; no post-write validate.
- **Status**: **BACKLOG** — added as `RELIABILITY-001` (Session 160 polish; not blocking first real-post test)

### P2-2 — Empty captures written as successful entries
- **File:Line**: `scripts/parse_fb_dom.py:516,518`; `scripts/extract_fb_post.py:381,394`
- **Description**: No post article found → skeleton emitted with exit 0; validator only requires `post_author.name` exist (not non-empty).
- **Status**: FIXED — `extract_fb_post` now exits non-zero if `post_author.name` is empty AND no `--allow-empty` flag; validator requires non-empty `post_author.name` AND non-empty `caption.text` OR explicit `notes` field

### P2-3 — Raw HTML hash format inconsistent
- **File:Line**: `scripts/parse_fb_dom.py:466,469`; `scripts/write_inbox_entry.py:98,308`
- **Description**: parser returns `sha256:<hex>`; writer computes bare `<hex>`.
- **Status**: FIXED — canonical form is bare hex (no prefix); ARCHITECTURE.md §3.1 documents this; both helpers use shared `_compute_html_sha256()` returning bare hex; regex check in validator

### P2-4 — FB TOS rule behavioral only
- **File:Line**: `.claude/rules/fb-tos-rule.md:64,66`
- **Description**: No mechanical hook blocking unsafe Chrome MCP calls.
- **Status**: **BACKLOG** — added as `TOS-HOOK-001` (Session 160+ design work; complex hook on transcript pattern matching)

### P3-1 — Person-hint stub uncovered edge cases
- **File:Line**: `scripts/extract_person_hints.py:79,132,179`
- **Description**: Regex misses initials/hyphens/apostrophes/diacritics; emits places/phrases.
- **Status**: **BACKLOG** — stub-by-design; `PERSON-MATCH-001` (Session 160 task) supersedes

### P3-2 — Doc-size rule conflict (600 vs 700)
- **File:Line**: `docs/ARCHITECTURE.md:626`; `CLAUDE.md:44`; `.claude/rules/doc-size-enforcement.md:14`
- **Description**: ARCHITECTURE.md says split at 600; CLAUDE.md + rule file allow 700.
- **Status**: FIXED — canonical 700-line cap for architecture anchor; aligned all three files

### P3-3 — pyproject console script target wrong
- **File:Line**: `pyproject.toml:27`
- **Description**: Entry point `rhodes_wiki.scripts.extract_fb_post:main` doesn't exist; should be `scripts.extract_fb_post:main`.
- **Status**: FIXED — corrected to `scripts.extract_fb_post:main`

---

## AI Tool Usage (per `.claude/rules/ai-tool-audit.md`)

- **Tool**: Codex CLI v0.130.0 (gpt-5-codex, xhigh)
- **Agent type**: Independent (fresh context)
- **Task**: Audit rhodes-wiki Phase 2-4 (architecture doc, scaffold, parser stubs)
- **Findings**: 13 total (0 P0, 6 P1, 4 P2, 3 P3)
- **Acted on**: 6 P1 fixed, 2 P2 fixed, 2 P3 fixed (10 total fixes this session)
- **Deferred**: 2 P2 + 1 P3 to BACKLOG (RELIABILITY-001, TOS-HOOK-001, PERSON-MATCH-001 supersedes)
- **Discarded**: 0
- **Value assessment**: **STRONG** — caught contract drift (P1-4, P1-5, P1-6) and security issues (P1-2, P1-3) that would have caused real bugs in Session 160 with real DOM. P1-3 image-download SSRF would have been a real exposure if I'd enabled `--download-images` against live fbcdn URLs.
- **Would we have found these ourselves?** P1-3 (SSRF + path traversal): unlikely in Phase 4; would have caught when first real image download crashed. P1-4 (validator coverage): yes eventually via integration test failures, but the explicit Codex catalog gave a complete picture. P1-5 (parser/writer drift): YES — my own smoke test caught the download_status variant (Codex caught all of them). The "we would have found this in Session 160" path would have cost ~1-2 hours of debugging.
- **Notable**: Codex correctly identified that `tests/conftest.py:parsed_post_subset` was "blessing" a non-contract shape — a subtle dependency-injection trap.
