# Testing & TDD Lessons

Lessons about test methodology, test isolation, assertions, and regression prevention.
See also: `docs/CODING_RULES.md` (Testing & TDD section)

---

### Lesson 1: Test ALL code paths, not just the obvious one
- **Mistake**: Fixed image URLs for image_* identities but missed inbox_* identities
- **Rule**: When fixing URL generation, grep for ALL places that generate URLs and test each one
- **Prevention**: Before declaring done, list every code path and verify each

### Lesson 2: Regressions require before/after comparison
- **Mistake**: Face box overlays broke during dimension fix -- indentation error caused only 1 box instead of N
- **Rule**: Before committing, compare behavior for ALL affected features
- **Prevention**: Write down what worked before, verify it still works after

### Lesson 3: "It compiles" is not "it works"
- **Mistake**: Declared success when crops loaded, but didn't test Photo Context modal
- **Rule**: Test every UI state, not just the first one you see
- **Prevention**: Create explicit checklist of ALL UI states before starting

### Lesson 4: Staff engineer approval test
- **Question**: "Would a staff engineer at a top company approve this PR?"
- **If no**: Stop and fix before continuing
- **If unsure**: Probably no -- investigate further

### Lesson 14: Every UX bug found in manual testing is a missing automated test
- **Mistake**: All 6 UX issues from the polish session (Facebook button, 303 redirects, missing scripts) could have been caught by automated tests, but none existed.
- **Rule**: Write the test that would have caught the bug, not just the fix.
- **Prevention**: After fixing any bug, immediately write a regression test for it.

### Lesson 16: Testing should not be a separate phase
- **Mistake**: Built 7 commits of UX fixes with no tests, then had to retrofit tests after the fact.
- **Rule**: Write tests alongside the feature, not after. Test first, implement second.
- **Prevention**: CLAUDE.md now has mandatory testing rules that require tests with every change.

### Lesson 17: HTMX endpoints behave differently than browser requests
- **Mistake**: Testing with a browser showed a redirect working fine, but HTMX silently followed the 303 and swapped the redirect target's HTML.
- **Rule**: Test both HTMX (`HX-Request: true`) and browser request paths. They return different status codes (401 vs 303).
- **Prevention**: Use the `tests/conftest.py` fixtures to test routes with and without HTMX headers.

### Lesson 21: Test assertions must match current UI, not historical UI
- **Mistake**: 9 pre-existing test failures were caused by UI changes (new landing page, color changes, URL prefix changes) that weren't accompanied by test updates.
- **Rule**: When changing UI text, CSS classes, or URL patterns, grep for those strings in tests and update assertions.
- **Prevention**: After any UI change, run `grep -r "old_string" tests/` to find stale assertions.

### Lesson 37: Test data must match the actual schema exactly
- **Mistake**: Test fixtures for IdentityRegistry omitted `"history": []` and used `IdentityRegistry(path)` instead of `IdentityRegistry.load(path)`.
- **Rule**: When creating test fixtures for data classes, mirror the exact schema including all required fields. Use the same load path the app uses.
- **Prevention**: Read the `load()` classmethod before writing test fixtures.

### Lesson 38: Read the code before assuming a bug exists
- **Observation**: BUG-003 (merge direction) was listed as CRITICAL but was already fully fixed in code. `resolve_merge_direction()`, undo_merge, state promotion, and name conflict resolution were all implemented. The only gap was test coverage.
- **Rule**: Before planning a fix, read the actual implementation code. The bug may already be fixed.
- **Prevention**: Start every bug investigation with `grep -n` to find the actual code, not just the design doc.

### Lesson 51: Tests that POST to data-modifying routes MUST mock BOTH load AND save
- **Mistake**: `test_bulk_photos.py::test_updates_source_successfully` called the real `load_photo_registry()` and the real `save_photo_registry()`. It picked the first 2 photos (Image 001, Image 054) and wrote "Test Collection" to production `data/photo_index.json`. Similarly, `test_regression.py::test_rename_identity` renamed a real identity and `test_metadata.py::test_metadata_update_success` wrote metadata to a real identity.
- **Rule**: Any test that calls a route handler (via TestClient POST) that modifies data MUST patch both the load function (to return mock data) and the save function (to prevent disk writes). Patching only one is insufficient.
- **Prevention**: `.claude/rules/test-isolation.md` enforces this for all tests. `scripts/check_data_integrity.py` detects contamination. CLAUDE.md Rule #14 codifies the requirement. Verify with `md5 data/*.json` before/after test runs.

### Lesson 52: "Restore original" is not isolation — history and version still change
- **Mistake**: `test_rename_identity` used a try/finally to rename Victoria Cukran Capeluto to "Test Person Name" and back. The test "worked" but added 2 history entries and bumped version_id from 76 to 79 every run.
- **Rule**: Don't use "rename and restore" patterns for test isolation. The side effects (history, version_id, updated_at) still accumulate. Use mock registries instead.
- **Prevention**: Tests must use `MagicMock()` or in-memory registries with test data, never touch production registries.

### Lesson 58: Test assertions must match CORRECT behavior, not historical behavior
- **Mistake**: Existing test asserted `"1 photos"` — which was the buggy grammar. When fixing the bug to output `"1 photo"`, the test correctly failed. The fix is to update the test, not revert the fix.
- **Rule**: When a grammar/display fix causes test failures, verify whether the test was asserting the bug. Update the test to assert correct behavior.
- **Prevention**: When writing display string assertions, always include a negative assertion for the known-incorrect form (e.g., `assert "1 photos" not in html`).

### Lesson 79: NEVER use manual patch.start()/patch.stop() without try/finally — use ExitStack
- **Mistake**: test_nav_consistency.py used `for p in patches: p.start()` then `client.get()` then `for p in patches: p.stop()`. When client.get() threw TypeError, stop() never ran — leaving 9 patches active for all subsequent tests. Caused 128 cascading failures (person/photo routes returning 404).
- **Rule**: Always use `contextlib.ExitStack` for multiple patches, or `with patch(...):` for single patches. Never use manual start/stop without try/finally.
- **Prevention**: `grep -rn "\.start()" tests/ | grep -v "ExitStack\|try:"` — flag any manual patch.start() calls.

### Lesson 80: Always run tests in venv — `source venv/bin/activate && pytest`
- **Mistake**: Running `pytest` without activating venv used system Python, which lacks fasthtml/torch. This caused 28 collection errors and reported only 1293 tests instead of 2909.
- **Rule**: Always prefix pytest commands with `source venv/bin/activate &&`.
- **Prevention**: Add to session startup checklist. The first command should always be `source venv/bin/activate`.
