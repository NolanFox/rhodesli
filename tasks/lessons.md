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
