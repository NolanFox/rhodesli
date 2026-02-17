# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

## Session 2026-02-05: R2 Migration Failures

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

### Lesson 5: 2026-02-05 - Indentation bugs when wrapping code in conditionals
- **Mistake**: When wrapping a `for` loop body inside `if has_dimensions:`, only the first few lines of the loop body were re-indented. The rest stayed at the outer level, causing them to run once after the loop instead of per-iteration.
- **Rule**: When adding a new conditional wrapper around existing code, verify EVERY line in the block got re-indented. Check the last line of the block specifically.
- **Prevention**: After any indentation change, read the full block end-to-end and confirm the closing lines are at the correct depth.

### Lesson 6: Auth should be additive, not restrictive by default
- **Mistake**: Protected entire site with Beforeware login requirement — visitors couldn't view anything
- **Rule**: Start with public access, add protection only to specific routes that need it
- **Prevention**: List all routes and explicitly decide: public, login-required, or admin-only

### Lesson 7: Auth guards must respect "auth disabled" mode
- **Mistake**: Adding `_check_admin(sess)` to POST routes broke tests because auth wasn't configured but the check still rejected requests (no user in session)
- **Rule**: When auth is disabled (`is_auth_enabled() == False`), ALL permission checks must pass through
- **Prevention**: First line of every auth check: `if not is_auth_enabled(): return None`

### Lesson 8: Supabase Management API can automate "manual" config
- **Mistake**: Initially declared email templates and OAuth provider setup as "USER ACTION REQUIRED" / manual steps
- **Rule**: Before marking any task as manual, check: (1) CLI tool? (2) Management API? (3) curl-able?
- **Prevention**: The Supabase Management API at `https://api.supabase.com/v1/projects/{ref}/config/auth` can update email templates, enable OAuth providers, and change auth settings. Use a personal access token (from Dashboard → Account → Access Tokens).
- **API fields**: `mailer_templates_confirmation_content`, `mailer_templates_recovery_content`, `mailer_subjects_*`, `external_google_enabled`, `external_google_client_id`, `external_google_secret`

### Lesson 9: Supabase has TWO types of API keys — use the right one
- **Mistake**: Railway had `sb_publishable_...` (new-style publishable key) set as `SUPABASE_ANON_KEY`, but Supabase Auth API requires the legacy JWT key (`eyJ...`)
- **Rule**: The Supabase Auth REST API (`/auth/v1/*`) requires the legacy JWT anon key. The new `sb_publishable_*` keys are for the Supabase client SDK.
- **Prevention**: Get correct keys via Management API: `GET /v1/projects/{ref}/api-keys` — use the key where `type: "legacy"` and `name: "anon"`

### Lesson 10: Facebook OAuth requires Business Verification for production
- **Mistake**: Planned Facebook OAuth as a simple credential-swap step
- **Rule**: Facebook/Meta requires Business Verification + App Review even for basic "Login with Facebook", making it impractical for small/invite-only projects
- **Prevention**: For small projects, stick with Google OAuth + email/password. Only add Facebook if the user base justifies the weeks-long verification process.

## Session 2026-02-05: UX & Auth Polish

### Lesson 11: HTMX silently follows 3xx redirects — use 401 + beforeSwap for auth
- **Mistake**: `_check_admin()` returned `RedirectResponse("/login", 303)`. HTMX followed the redirect transparently, fetched the full login page HTML, and swapped it into the target element (replacing the identity card).
- **Rule**: For HTMX-triggered auth failures, return 401 (not 303). Use a global `htmx:beforeSwap` handler to intercept 401 and show a login modal.
- **Prevention**: Never use RedirectResponse for auth guards that protect HTMX POST endpoints. Use `Response("", status_code=401)` and handle it client-side.

### Lesson 12: Email clients strip `<style>` blocks — always use inline styles
- **Mistake**: Email template buttons used `class="button"` with styles defined in `<style>` block. Gmail, Outlook, and Apple Mail stripped the `<style>` block, making buttons invisible/unreadable.
- **Rule**: All styling on email `<a>` buttons MUST use inline `style=` attributes.
- **Prevention**: Use `style="display: inline-block; background-color: #2563eb; color: #ffffff !important; ..."` directly on the element.

### Lesson 13: Supabase recovery email redirects to Site URL by default
- **Mistake**: Password reset email link redirected to `/#access_token=...` (the Site URL) instead of `/reset-password#access_token=...`.
- **Rule**: Pass `redirect_to` in the options when calling `/auth/v1/recover` to control where the user lands.
- **Prevention**: Always specify `"redirect_to": f"{site_url}/reset-password"` in the recovery request body.

## Session 2026-02-05: Testing Harness

### Lesson 14: Every UX bug found in manual testing is a missing automated test
- **Mistake**: All 6 UX issues from the polish session (Facebook button, 303 redirects, missing scripts) could have been caught by automated tests, but none existed.
- **Rule**: Write the test that would have caught the bug, not just the fix.
- **Prevention**: After fixing any bug, immediately write a regression test for it.

### Lesson 15: Permission regressions are the most dangerous bugs
- **Mistake**: Changing `_check_admin` to return 303 (redirect) instead of 401 broke HTMX inline actions silently — the page appeared to work but swapped in full login page HTML.
- **Rule**: Always test the full matrix of routes x auth levels (anonymous, user, admin).
- **Prevention**: `tests/test_permissions.py` has matrix tests for all admin routes. Run them after any auth change.

### Lesson 16: Testing should not be a separate phase
- **Mistake**: Built 7 commits of UX fixes with no tests, then had to retrofit tests after the fact.
- **Rule**: Write tests alongside the feature, not after. Test first, implement second.
- **Prevention**: CLAUDE.md now has mandatory testing rules that require tests with every change.

### Lesson 17: HTMX endpoints behave differently than browser requests
- **Mistake**: Testing with a browser showed a redirect working fine, but HTMX silently followed the 303 and swapped the redirect target's HTML.
- **Rule**: Test both HTMX (`HX-Request: true`) and browser request paths. They return different status codes (401 vs 303).
- **Prevention**: Use the `tests/conftest.py` fixtures to test routes with and without HTMX headers.

### Lesson 19: Default to admin-only for new data-modifying features
- **Mistake**: `POST /upload` used `_check_login` (any user), but had no file size limits, rate limiting, or moderation queue. Any logged-in user could fill disk with uploads.
- **Rule**: Default to admin-only for new data-modifying features. Loosen permissions only when moderation/guardrails are in place.
- **Prevention**: When adding a new POST route that writes data, use `_check_admin` first. Add a `# TODO: Revert to _check_login when <guardrail> is built` comment. Only downgrade to `_check_login` after implementing the guardrail.

### Lesson 18: Supabase sender name requires custom SMTP
- **Mistake**: Tried to set `smtp_sender_name` via Management API, but it only works when custom SMTP is configured.
- **Rule**: Supabase's built-in mailer uses a fixed sender name. Custom sender requires configuring custom SMTP (Resend, SendGrid, etc.).
- **Prevention**: Check if custom SMTP is configured before trying to change sender-related fields.

## Session 2026-02-06: Overnight Polish & UX Overhaul

### Lesson 20: Parallel subagents can safely edit the same file
- **Observation**: 5 agents edited `app/main.py` simultaneously, each touching different functions. All changes merged cleanly because each agent re-reads the file before editing.
- **Rule**: When parallelizing work on a single large file, assign each agent to distinct functions/sections. The Edit tool's unique-string matching prevents conflicts.
- **Prevention**: In task prompts, be explicit about which sections/functions each agent owns.

### Lesson 21: Test assertions must match current UI, not historical UI
- **Mistake**: 9 pre-existing test failures were caused by UI changes (new landing page, color changes, URL prefix changes) that weren't accompanied by test updates.
- **Rule**: When changing UI text, CSS classes, or URL patterns, grep for those strings in tests and update assertions.
- **Prevention**: After any UI change, run `grep -r "old_string" tests/` to find stale assertions.

### Lesson 22: Upload permissions should be admin-only until moderation exists
- **Mistake**: Originally had `_check_login` on upload, which was too permissive without rate limiting or moderation.
- **Rule**: Default new data-modifying routes to `_check_admin`. Only downgrade to `_check_login` when the moderation queue (pending uploads) is implemented.
- **Prevention**: The pending upload queue (Phase 3) is the guardrail that allows reverting to `_check_login`.

### Lesson 23: No single doc file should exceed 300 lines
- **Mistake**: `docs/SYSTEM_DESIGN_WEB.md` grew to 1,373 lines / 47.6k chars. Claude Code warned: "Large docs/SYSTEM_DESIGN_WEB.md will impact performance (47.6k chars > 40.0k)". It wasted context window every session.
- **Rule**: Split documentation into focused sub-files (<300 lines each). Use progressive disclosure: CLAUDE.md points to docs, doesn't inline them.
- **Prevention**: Before any doc update, check `wc -l` on the target file. If it's over 250 lines, split before adding content.

### Lesson 24: CLAUDE.md is loaded into every context window — keep it under 80 lines
- **Mistake**: CLAUDE.md grew with inline architecture details that belonged in separate docs.
- **Rule**: CLAUDE.md should be a "project constitution" — rules, key pointers, workflow. Details go in `docs/` files referenced by `@` directives.
- **Prevention**: After editing CLAUDE.md, run `wc -l CLAUDE.md` and verify < 80 lines.

### Lesson 26: CHANGELOG must be updated every session, not retroactively
- **Mistake**: 9+ commits across 3 sessions went without CHANGELOG updates. Had to reconstruct entries retroactively from git log.
- **Rule**: Update CHANGELOG.md before ending any session that includes user-visible changes. Group by version with Keep a Changelog format.
- **Prevention**: Added rule #9 to CLAUDE.md Rules section. The rule already existed in CODING_RULES.md but was buried and not enforced.

### Lesson 25: Photo ID schemes must be consistent within lookup systems
- **Mistake**: `_build_caches()` used SHA256(filename)[:16] as photo IDs but tried to look up sources from photo_index.json which used inbox_* IDs. 12 of 13 Betty Capeluto photos silently got empty source strings.
- **Rule**: When cross-referencing data between systems with different ID schemes, always include a fallback lookup by a shared key (e.g., filename).
- **Prevention**: Add a test that verifies every photo has a non-empty source after cache building.

## Session 2026-02-06: ML Decision Capture

### Lesson 27: Algorithmic decisions need a structured decision log
- **Mistake**: Proposed centroid averaging when multi-anchor was the correct approach. No record existed of past algorithmic decisions or why alternatives were rejected.
- **Rule**: All ML/algorithmic decisions must be recorded in `docs/ml/ALGORITHMIC_DECISIONS.md` with AD-XXX format: context, decision, rejected alternative, why rejected, affected files.
- **Prevention**: Path-scoped rules (`.claude/rules/ml-pipeline.md`) auto-load this requirement when touching ML files.

### Lesson 28: Use path-scoped rules for domain-specific context
- **Observation**: ML rules should load when touching `core/neighbors.py`, but not when working on auth or landing page. Path-scoped rules in `.claude/rules/` achieve this with zero token cost for unrelated work.
- **Rule**: When a set of rules only applies to specific files/directories, use `.claude/rules/` with YAML frontmatter `paths:` instead of adding to CLAUDE.md.
- **Prevention**: Before adding rules to CLAUDE.md, ask: "Does this apply to ALL files, or just a subset?" If subset, use path-scoped rules.

## Session 2026-02-07: Harness Buildout

### Lesson 29: Maintain ONE authoritative backlog
- **Mistake**: Session-scoped todos in `tasks/todo.md` contained only the current session's work, not the full project backlog. Previous sessions' items were lost.
- **Rule**: `tasks/todo.md` is the SINGLE project backlog. Session-scoped checklists are ephemeral — reconcile them into the backlog after every session.
- **Prevention**: At session end, move completed items to the "Completed" section and ensure all known open items are captured.

### Lesson 30: Path-scoped rules can include future planning awareness
- **Observation**: `.claude/rules/planning-awareness.md` triggers when touching `app/main.py` or `core/*.py`, reminding about upcoming Postgres migration and contributor roles.
- **Rule**: Path-scoped rules aren't just for restrictions — they can include "this code will be affected by X planned change" so Claude considers upcoming work without reading full design docs.
- **Prevention**: When adding a planned feature that will affect existing code, add a planning-awareness rule so the context loads automatically.

### Lesson 31: Infrastructure decisions are as important as algorithmic ones
- **Mistake**: The "0 Photos" bug from `.dockerignore` cost more debugging time than any ML issue. Ops decisions weren't documented.
- **Rule**: Capture ops decisions (OD-XXX format in `docs/ops/OPS_DECISIONS.md`) with the same rigor as ML decisions (AD-XXX format).
- **Prevention**: Before modifying Dockerfile, railway.toml, or deployment scripts, read `docs/ops/OPS_DECISIONS.md`.

### Lesson 32: .gitignore and .dockerignore serve different purposes
- **Mistake**: Assumed all ignore files behave the same way.
- **Rule**: `data/` files belong in `.gitignore` (keep repo light) but NOT in `.dockerignore` (allow CLI deployment to include them).
- **Prevention**: Rule is now enforced by `.claude/rules/deployment.md` path-scoped rule.

### Lesson 33: Not every decision needs a formal AD entry
- **Observation**: Some undocumented behaviors (temporal prior penalty values, detection thresholds) exist in code but were never formally decided.
- **Rule**: Use TODO markers for undocumented code behavior and "Known Unknowns" for things not yet discussed (cluster size limits). Formalize only when modifying.
- **Prevention**: `docs/ml/ALGORITHMIC_DECISIONS.md` has a "TODO" section for decisions that need code review before formalizing.

## Session 2026-02-07: Overnight Automation Session

### Lesson 34: HTMX ignores formaction — use hx_post on each button
- **Mistake**: Multi-merge form used `hx_post` on `<form>` and `formaction` on buttons. HTMX always used the form's `hx_post`, ignoring `formaction`.
- **Rule**: When a form has multiple submit buttons with different URLs, put `hx_post` on each button with `hx_include="closest form"`.
- **Prevention**: Never use HTML `formaction` attribute with HTMX forms.

### Lesson 35: toggle @checked modifies HTML attribute, not JS property
- **Mistake**: Hyperscript `toggle @checked on <input/>` toggles the HTML attribute, but `FormData` reads the JS `.checked` property. Checkboxes appeared checked but weren't included in form data.
- **Rule**: For checkbox state changes, use property assignment: `set el.checked to my.checked`
- **Prevention**: When controlling checkboxes via Hyperscript, always use property syntax, not attribute syntax.

### Lesson 36: get_identity() returns a shallow copy — mutate _identities directly
- **Mistake**: `add_note()` and `resolve_proposed_match()` called `get_identity()` which returns `.copy()`. Mutations to the returned dict didn't persist.
- **Rule**: When adding methods to IdentityRegistry that mutate identity data, access `self._identities[id]` directly, not through `get_identity()`.
- **Prevention**: Before adding any mutation method to the registry, check whether `get_identity()` returns a copy.

### Lesson 37: Test data must match the actual schema exactly
- **Mistake**: Test fixtures for IdentityRegistry omitted `"history": []` and used `IdentityRegistry(path)` instead of `IdentityRegistry.load(path)`.
- **Rule**: When creating test fixtures for data classes, mirror the exact schema including all required fields. Use the same load path the app uses.
- **Prevention**: Read the `load()` classmethod before writing test fixtures.

## Session 2026-02-08: Stabilization Session 3

### Lesson 38: Read the code before assuming a bug exists
- **Observation**: BUG-003 (merge direction) was listed as CRITICAL but was already fully fixed in code. `resolve_merge_direction()`, undo_merge, state promotion, and name conflict resolution were all implemented. The only gap was test coverage.
- **Rule**: Before planning a fix, read the actual implementation code. The bug may already be fixed.
- **Prevention**: Start every bug investigation with `grep -n` to find the actual code, not just the design doc.

### Lesson 39: Event delegation is the ONLY stable pattern for HTMX apps
- **Observation**: Lightbox arrows broke 3 times because each fix re-bound to DOM nodes that HTMX later swapped. The permanent fix uses ONE global listener on `document` with `data-action` dispatch.
- **Rule**: ALL JS event handlers in HTMX apps MUST use global event delegation via `data-action` attributes. NEVER bind directly to DOM nodes that HTMX may swap.
- **Prevention**: Added to CLAUDE.md as a non-negotiable rule. Smoke tests verify `data-action` attributes exist.

### Lesson 40: Parallel subagents work well for independent DOM fixes
- **Observation**: 3 subagents fixed BUG-001, BUG-002, and BUG-004 simultaneously, each touching different functions in the same file. All changes merged cleanly. Combined test count went from 663 to 716.
- **Rule**: When UI bugs are in distinct functions, launch parallel subagents. Each should write tests first, then implement, then verify no regression.
- **Prevention**: Use this pattern for future independent UI fixes.

### Lesson 41: Confidence gap > absolute distance for human decision-making
- **Observation**: Showing "15% closer than next-best" is more useful for humans than showing "distance: 0.82". Relative comparisons help adjudicate truth better than absolute scores.
- **Rule**: When displaying ML results to non-technical users, prefer comparative metrics over absolute ones.
- **Prevention**: The confidence_gap pattern can be reused for any ranked list.

## Session 2026-02-10: Sync Infrastructure

### Lesson 42: Token-based API auth is simpler than session cookie sync for machine-to-machine
- **Mistake**: Previous sync approach required exporting browser session cookies as cookies.txt. This never worked because it required manual browser interaction and cookies expire.
- **Rule**: For machine-to-machine data sync, use a simple Bearer token (RHODESLI_SYNC_TOKEN). Set it once on both sides, never expires.
- **Prevention**: When building script-to-server communication, always prefer API tokens over session cookies.

### Lesson 43: Production and local JSON files are completely separate
- **Observation**: Railway has its own copy of identities.json on the persistent volume. Local dev has a separate copy. Admin tagging on the live site does NOT update local data.
- **Rule**: Every ML session MUST start with `python scripts/sync_from_production.py` to get fresh data.
- **Prevention**: `scripts/full_ml_refresh.sh` runs sync as step 1. Never skip it.

## Session 2026-02-10: Skipped Faces Fix

### Lesson 44: "Skipped" is a deferral, not a resolution
- **Mistake**: Clustering script only included INBOX and PROPOSED faces as candidates. SKIPPED faces (192 — the largest pool of unresolved work) were silently excluded. The script reported "0 candidates" while 192 faces remained unidentified.
- **Rule**: SKIPPED means "I don't recognize this person right now." It is NOT a terminal state. ML pipelines, UI navigation, and stats must all treat skipped faces as active work items.
- **Prevention**: When adding state-based filters, always list what's EXCLUDED (confirmed, dismissed, rejected) rather than what's included. The default should be to include faces, not exclude them.

### Lesson 45: Every identity state must have a defined click behavior
- **Mistake**: Lightbox face overlays were plain `<div>` elements for non-highlighted faces — no click handler, no cursor change. Confirmed faces worked because the main photo viewer had logic, but the lightbox used a simpler renderer that skipped interactivity.
- **Rule**: Every face overlay in every view (photo viewer, lightbox, grid card) must have: (1) cursor-pointer, (2) a click handler appropriate for its state, (3) a tooltip showing the identity name.
- **Prevention**: When creating a new face overlay rendering path, copy the interaction pattern from the canonical `_build_photo_view_content()`, don't simplify.

### Lesson 46: Navigation links must derive section from identity state, not hardcode
- **Mistake**: `neighbor_card` and `identity_card_mini` hardcoded `section=to_review` in all links. When skipped faces used Find Similar, clicking a neighbor routed to the empty Inbox instead of the skipped section.
- **Rule**: Use `_section_for_state(identity.get("state"))` for all identity navigation links. Never hardcode a section.
- **Prevention**: Created canonical `_section_for_state()` helper. Grep for `section=to_review` periodically to catch new hardcoded links.

## Session 2026-02-10: Upload Pipeline Stress Test

### Lesson 48: Route handlers must use canonical save functions, not direct .save()
- **Mistake**: `/api/photo/{id}/collection` called `photo_reg.save(photo_index_path)` directly instead of `save_photo_registry(photo_reg)`. Tests patched `save_photo_registry` but the route bypassed it, causing test fixture data to overwrite real `data/photo_index.json` on every test run.
- **Rule**: All data-modifying route handlers MUST use the canonical save functions (`save_registry()`, `save_photo_registry()`, etc.), never call `.save()` directly on registry objects.
- **Prevention**: Grep for `.save(` in route handlers. Any direct `.save(path)` call outside of canonical save functions is a bug.

### Lesson 49: A push-to-production API is essential for the ML pipeline
- **Mistake**: `process_uploads.sh` attempted `git add data/` but data/ is gitignored. There was no way to push locally-processed data back to Railway.
- **Rule**: Any two-stage pipeline (local processing -> remote deployment) needs a push mechanism. Don't rely on git for pushing gitignored data.
- **Prevention**: `POST /api/sync/push` + `scripts/push_to_production.py` now handle this. Token-authenticated, creates backups.

### Lesson 50: Downloaded files should match the existing directory convention
- **Mistake**: `download_staged.py` puts files in `raw_photos/pending/` but the photo_index path recorded `raw_photos/pending/filename.jpg`. All 124 existing photos are at `raw_photos/filename.jpg` (no subdirectory).
- **Rule**: After downloading, move files to match the canonical location before registering them.
- **Prevention**: The `process_uploads.sh` script should move files from pending/ to raw_photos/ root after download.

## Session 2026-02-10: Harness Improvement

### Lesson 47: Documentation drift is invisible until it's severe
- **Mistake**: `docs/BACKLOG.md` fell 6 versions behind (v0.10.0 → v0.14.1, 663 → 900 tests) because CLAUDE.md only instructed updating ROADMAP.md. The reference "see `docs/BACKLOG.md`" read as "go look at it", not "keep it current."
- **Rule**: When maintaining parallel tracking documents, the update rule must explicitly name EVERY file. "Update ROADMAP.md" does NOT imply "also update BACKLOG.md."
- **Prevention**: CLAUDE.md now has explicit triple-update rule (ROADMAP + BACKLOG + CHANGELOG). `scripts/verify_docs_sync.py` and `tests/test_docs_sync.py` catch drift automatically.

## Session 2026-02-10: Data Integrity Fix

### Lesson 51: Tests that POST to data-modifying routes MUST mock BOTH load AND save
- **Mistake**: `test_bulk_photos.py::test_updates_source_successfully` called the real `load_photo_registry()` and the real `save_photo_registry()`. It picked the first 2 photos (Image 001, Image 054) and wrote "Test Collection" to production `data/photo_index.json`. Similarly, `test_regression.py::test_rename_identity` renamed a real identity and `test_metadata.py::test_metadata_update_success` wrote metadata to a real identity.
- **Rule**: Any test that calls a route handler (via TestClient POST) that modifies data MUST patch both the load function (to return mock data) and the save function (to prevent disk writes). Patching only one is insufficient.
- **Prevention**: `.claude/rules/test-isolation.md` enforces this for all tests. `scripts/check_data_integrity.py` detects contamination. CLAUDE.md Rule #14 codifies the requirement. Verify with `md5 data/*.json` before/after test runs.

### Lesson 52: "Restore original" is not isolation — history and version still change
- **Mistake**: `test_rename_identity` used a try/finally to rename Victoria Cukran Capeluto to "Test Person Name" and back. The test "worked" but added 2 history entries and bumped version_id from 76 to 79 every run.
- **Rule**: Don't use "rename and restore" patterns for test isolation. The side effects (history, version_id, updated_at) still accumulate. Use mock registries instead.
- **Prevention**: Tests must use `MagicMock()` or in-memory registries with test data, never touch production registries.

## Session 2026-02-10: Production HTML Verification

### Lesson 53: Verify production bugs by fetching rendered HTML, not checking local data
- **Mistake**: Multiple previous sessions claimed to fix production issues by checking local JSON files and API responses. But the live site still showed 5 bugs because the data never actually reached the production rendering pipeline.
- **Rule**: For EVERY production fix, verification means `curl -s https://rhodesli.nolanandrewfox.com/[page] | grep [expected content]`. Checking local data files is necessary but NOT sufficient.
- **Prevention**: Every deployment fix must end with HTML-based verification.

### Lesson 54: ALL essential data files must be in BOTH git tracking AND REQUIRED_DATA_FILES
- **Mistake**: `embeddings.npy` was gitignored (so not in Docker builds) AND not in `REQUIRED_DATA_FILES` (so not synced to volume). The init script had nothing to sync FROM.
- **Rule**: For a data file to reach production: (1) it must be tracked in git (or the Docker image won't have it), (2) it must be in `REQUIRED_DATA_FILES` (or `_sync_essential_files` won't update the volume copy), (3) the init script must handle binary files correctly.
- **Prevention**: Added `embeddings.npy` to `.gitignore` whitelist and `REQUIRED_DATA_FILES`. Any new data file for production needs BOTH.

### Lesson 55: Crop filename formats differ between legacy and inbox — don't assume quality is encoded
- **Mistake**: `face_card()` parsed quality from crop filenames using pattern `_{quality}_{index}.jpg`. Inbox crops use format `inbox_{hash}.jpg` with no quality encoded. Result: "Quality: 0.00" for all inbox faces.
- **Rule**: When a computed value (quality, score, etc.) is stored in different places for different face formats, the lookup must have a fallback chain: filename parse → embeddings cache → default.
- **Prevention**: `get_face_quality()` helper provides the fallback. `face_card()` now falls back to embeddings when filename parse returns 0.

## Session 2026-02-11: Data Integrity + ML-UI Integration

### Lesson 56: Blind push-to-production overwrites admin actions
- **Mistake**: `push_to_production.py` did `git add data/ && git commit && git push` without checking production state. Admin merged "Zeb Capuano" on production, but local data still had the unmerged identities. Next push overwrote the merge.
- **Rule**: NEVER push data to production without first fetching and merging with the current production state. Production wins on conflicts (state changes, name changes, face set changes, merges, rejections).
- **Prevention**: `push_to_production.py` now has `perform_merge()` that fetches via sync API, detects user-modified identities via `_is_production_modified()`, and preserves them. Use `--no-merge` only for known-clean states.

### Lesson 57: FastHTML `cls` is stored as `class` in `.attrs`
- **Mistake**: After creating a FastHTML `Div(cls="...")`, tried to modify via `card.attrs["cls"]` — KeyError. FastHTML maps the `cls` kwarg to `class` in the attrs dict.
- **Rule**: Access `element.attrs["class"]` (not `"cls"`) to read/modify CSS classes on FastHTML elements after creation.
- **Prevention**: Added to `.claude/rules/ui-scalability.md` as a rule.

### Lesson 58: Test assertions must match CORRECT behavior, not historical behavior
- **Mistake**: Existing test asserted `"1 photos"` — which was the buggy grammar. When fixing the bug to output `"1 photo"`, the test correctly failed. The fix is to update the test, not revert the fix.
- **Rule**: When a grammar/display fix causes test failures, verify whether the test was asserting the bug. Update the test to assert correct behavior.
- **Prevention**: When writing display string assertions, always include a negative assertion for the known-incorrect form (e.g., `assert "1 photos" not in html`).

## Session 2026-02-11: Proposals Deployment Fix

### Lesson 59: Optional data files need explicit sync, not just bundling
- **Mistake**: `proposals.json` was tracked in git, bundled in Docker, but never synced to the Railway volume because `_sync_essential_files()` only processed `REQUIRED_DATA_FILES`. The "add missing files" fallback only copies files that DON'T exist — proposals.json already existed (empty) on the volume.
- **Rule**: Any data file that (a) changes over time and (b) needs to reach production must be in either `REQUIRED_DATA_FILES` or `OPTIONAL_SYNC_FILES` in `init_railway_volume.py`. Being in the Docker bundle alone is NOT sufficient if the file already exists on the volume.
- **Prevention**: When adding a new data file, ask: "Will this file change after initial deployment?" If yes, add it to the sync list. Added `OPTIONAL_SYNC_FILES` for non-critical files like proposals.json.

### Lesson 60: Empty proposals means clustering wasn't re-run, not a UI bug
- **Mistake**: Assumed the UI was broken because proposals weren't showing. The actual issue was proposals.json had 0 proposals because `cluster_new_faces.py` hadn't been re-run after data changes.
- **Rule**: When "feature X doesn't work on production", check the DATA first (is it populated?), then check the DEPLOYMENT PIPELINE (does it reach the server?), then check the UI code (does it read the data?).
- **Prevention**: After any data change (sync, merge, ingest), re-run clustering to regenerate proposals.

## Session 2026-02-11: Global Reclustering + Inbox Triage

### Lesson 61: SKIPPED faces must participate in clustering, not just proposals
- **Mistake**: `group_inbox_identities()` only included INBOX faces (line 139). The 196 SKIPPED faces were excluded from peer-to-peer grouping forever. But `cluster_new_faces.py` already included them for proposal generation against confirmed identities.
- **Rule**: Status boundaries (INBOX vs SKIPPED) should not be clustering boundaries. "Skip" means "I can't identify this right now," not "exclude from ML forever." Every major photo system (Apple, Google, Immich) continuously re-evaluates all unresolved faces.
- **Prevention**: `group_all_unresolved()` now includes both INBOX and SKIPPED. Use `--inbox-only` flag only for legacy behavior. Added `.claude/rules/ml-ui-integration.md` section documenting this.

### Lesson 62: Triage by actionability, not chronology
- **Mistake**: The inbox showed all items sorted by creation date. Admin had to scroll past 60+ unidentified faces to find the one that had an ML match at 0.61 distance — a near-certain identification.
- **Rule**: Sort the inbox by actionability: confirmed matches first (one-click merge), then proposals (high-confidence), then promotions (new evidence), then unmatched. The admin's time is best spent on the highest-confidence actions.
- **Prevention**: Focus mode `_focus_sort_key` now uses 6-tier priority. Triage bar shows counts by category with filter links.

### Lesson 63: Filters must be preserved across all navigation paths
- **Mistake**: Match mode ignored `?filter=` entirely — `_get_best_match_pair()` had no filter parameter. Up Next thumbnails linked to `?current=UUID` without `&filter=X`, so clicking navigated to the unfiltered context. Promotion banners had empty `promotion_context` because grouping code never set it.
- **Rule**: When a filter parameter (`?filter=X`) is active, every UI element must respect it: main content, Up Next thumbnails, action buttons, Skip button, and the decide endpoint. Breaking filter context is disorienting. Promotion banners must show specific context (which faces grouped) not generic text.
- **Prevention**: Match mode now passes filter through the full HTMX chain. `identity_card_mini` accepts `triage_filter` param. `core/grouping.py` populates `promotion_context` with group member names. Rule added to `.claude/rules/ui-scalability.md`.

## Session 2026-02-13: Suggest Button Fix

### Lesson 64: Toasts inside modals are invisible if z-index is wrong
- **Mistake**: `#toast-container` had `z-50` while `#photo-modal` had `z-[9999]`. Non-admin "Suggest" button in the face tag dropdown POSTed successfully to `/api/annotations/submit`, annotation was saved, toast was returned — but the toast rendered BEHIND the photo modal. User saw "nothing happens."
- **Rule**: Toast container must ALWAYS have the highest z-index in the app — above all modals, overlays, and dropdowns. Any action inside a modal that returns a toast will be invisible if the toast z-index is lower.
- **Prevention**: Z-index hierarchy is now: toast(10001) > guest-modal(10000) > photo-modal(9999). Comment in `photo_modal()` documents the hierarchy. E2E test + unit test verify the ordering.

## Session 2026-02-13: Community Upload Processing

### Lesson 65: push_to_production.py must be run AFTER ingest completes, not before
- **Mistake**: `push_to_production.py` committed `data/embeddings.npy` before ingest_inbox finished writing the new face to it. The committed version had 657 entries (156 photos), but the working copy had 658 entries (157 photos). Production never got the new embedding.
- **Rule**: The full upload pipeline sequence must be: (1) download → (2) ingest → (3) upload to R2 → (4) push to production. Step 4 must come LAST and include ALL modified data files. Verify with `git diff --stat` before pushing.
- **Prevention**: After `push_to_production.py`, always run `git status` to check for unstaged changes to data files. If any exist, the push was incomplete.

### Lesson 66: identities.json "history" key is REQUIRED — ingest_inbox doesn't write it
- **Mistake**: `core/ingest_inbox.py` writes identities.json with only `schema_version` and `identities` keys, omitting `history`. `IdentityRegistry.load()` requires `history` and throws `ValueError` when it's missing. `load_registry()` catches the error and returns an empty registry → 0 identities on production.
- **Rule**: Any code that writes identities.json MUST include the `history` key (even if empty: `[]`). Use `IdentityRegistry.save()` for all writes, never `json.dump()` directly.
- **Prevention**: The ingest pipeline should load via `IdentityRegistry.load()`, modify, then save via `registry.save()` to preserve the full schema.

### Lesson 67: sync push must invalidate ALL in-memory caches, not just some
- **Mistake**: `/api/sync/push` invalidated `_photo_registry_cache` and `_face_data_cache` but missed `_photo_cache` and `_face_to_photo_cache`. After pushing new photo data, the photos page showed stale data.
- **Rule**: When adding a new in-memory cache, add it to the sync push invalidation list. Grep for `= None` patterns in the push handler.
- **Prevention**: Added `_photo_cache = None` and `_face_to_photo_cache = None` to the sync push cache invalidation block.

### Lesson 68: Multiple community uploads may come in separate batches
- **Mistake**: Assumed the contributor uploaded 2 photos in 1 batch. They actually uploaded in 2 separate batches (2 separate upload form submissions). `download_staged.py` was run once and cleared only the first batch. The second batch sat in staging for days.
- **Rule**: After processing community uploads, always run `download_staged.py --dry-run` one more time to check for additional batches. Contributors may upload photos incrementally.
- **Prevention**: Add a final verification step to the upload pipeline: "Verify staging is empty."

## Session 2026-02-13: Annotation Persistence Fix

### Lesson 69: Production-origin data must NEVER be in deploy sync lists
- **Mistake**: `annotations.json` was in both `OPTIONAL_SYNC_FILES` (init_railway_volume.py) and `DATA_FILES` (push_to_production.py). Users submit annotations on the live site, but the deploy pipeline would overwrite the production copy with the local empty one. The user's annotation appeared to vanish.
- **Rule**: Data files written by users on production (annotations.json) must NOT be in OPTIONAL_SYNC_FILES or push DATA_FILES. They need their own pull mechanism (sync API endpoint) to flow production→local. The deploy must never touch them.
- **Prevention**: Before adding a data file to any sync list, ask: "Who writes this file?" If production users → do NOT sync from bundle. If local ML pipeline → sync from bundle. Added deploy safety tests that assert annotations.json is NOT in sync lists. Added `/api/sync/annotations` pull endpoint.

## Session 2026-02-17: /connect Production 500 Fix

### Lesson 70: Dockerfile must COPY every package the web app imports at runtime
- **Mistake**: `rhodesli_ml/` was never added to the Dockerfile when its graph/importer modules were first imported by app/main.py (sessions 35-38). The Dockerfile only had `COPY app/`, `COPY core/`, `COPY scripts/`. Routes /connect, /tree, and /admin/gedcom all 500'd in production with `ModuleNotFoundError` — but worked locally because `rhodesli_ml/` existed on disk.
- **Rule**: When adding a NEW `from X import ...` to `app/main.py` where X is a package not already in the Dockerfile, you MUST update the Dockerfile in the SAME commit. "Works locally" is not "works in production."
- **Prevention**: Added 5 deploy safety tests (`TestDockerfileModuleCoverage`) that verify the Dockerfile has COPY directives for every rhodesli_ml subpackage the web app imports. Selectively copy only pure-Python runtime modules (graph/ + importers/ = 200KB), not the full ML package (3.2GB with .venv + checkpoints).
