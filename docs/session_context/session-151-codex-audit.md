# Session 151 Codex Audit

**Auditor**: Codex CLI v0.120.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: scripts/batch_event_context.py, tests/test_batch_event_context.py
**Date**: 2026-04-14

## Findings

### P0: None

### P1 (2 findings — both FIXED)

1. **Path traversal in resolve_photo_path()** — DB-backed `photos.path` could read arbitrary local files via `..` traversal. Fix: reject `..` in basename, only resolve within `raw_photos/`. Regression test added.

2. **Upsert failure silently counted as success** — Supabase write failure was caught but item still counted as success, meaning Gemini budget spent without data persisted. Fix: upsert failures now increment error_count and continue to next photo.

### P2 (3 findings — accepted, matches existing pattern)

1. **Malformed JSON in date_labels.data** — `json.loads` on DB data without try/except. Accepted: data is written by our own scripts, schema is controlled. Same pattern as batch_gemini_for_person.py.

2. **Brittle 429 detection** — Substring matching on exception text for quota exhaustion. Accepted: matches existing batch script pattern. Google's genai SDK doesn't expose structured error codes.

3. **Dry-run is opt-in** — Script defaults to live execution. Accepted: admin-only CLI tool, consistent with all other batch scripts. Adding `--execute` flag would break existing workflow.

### P3 (1 finding — noted)

1. **Shallow test coverage** — Tests cover helpers but not end-to-end run_batch with mocked Gemini/Supabase. Noted: adequate for a batch script; the 5-photo live validation provides stronger coverage than mocked e2e.

## Summary
- 0 P0, 2 P1 (fixed), 3 P2 (accepted), 1 P3 (noted)
- Value: MODERATE — caught real path traversal and silent failure bugs
