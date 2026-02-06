# Coding Rules & Conventions

Detailed coding, testing, data safety, and workflow rules for Rhodesli development.

---

## Testing & TDD

### Core Principles
- **Red-Green-Refactor**: Always write a failing test before implementation. No exceptions.
- **Green Before Commit**: All tests must pass before committing implementation code.
- **Test Framework**: Use pytest and httpx for testing.
- **Test Location**: Tests mirror source files: `core/crop_faces.py` -> `tests/test_crop.py`.
- **Run Tests**: `pytest tests/ -v` from project root.

### Every change gets tests
When modifying or adding features, ALWAYS write or update tests that cover:
1. **The happy path** -- the feature works as intended
2. **The failure mode** -- what happens when it breaks (wrong auth, missing data, etc.)
3. **The regression case** -- a test that would have caught the bug that prompted this change

### Permission changes get permission tests
Any change to routes, auth checks, or permission logic MUST include:
- Test that public routes remain public
- Test that protected routes reject unauthenticated users (return 401 for HTMX, redirect for browser)
- Test that admin-only routes reject non-admin users
- Test that admin routes work for admin users

### UI changes get content tests
Any change to templates, login pages, or client-side JS MUST include:
- Test that expected elements are present in rendered HTML
- Test that removed elements are NOT present (e.g., disabled OAuth buttons)
- Test that required scripts are included in the page

### Test before declaring done
Before marking any task complete:
1. Run `pytest tests/ -v` -- all tests must pass
2. If the change is deployed, run production verification checks via curl
3. Never skip writing tests because "it's a small change" -- small changes cause regressions

### Test patterns
- Use shared fixtures from `tests/conftest.py` for auth states: `auth_enabled`, `auth_disabled`, `no_user`, `regular_user`, `admin_user`, `google_oauth_enabled`
- Use HTMX headers (`HX-Request: true`) when testing HTMX endpoints
- Test both the response code AND the response content where relevant
- Permission tests should use a matrix: [route] x [auth_state] -> [expected_status]
- Mock `app.main.is_auth_enabled` and `app.main.get_current_user` to control auth state in tests

### Test Isolation
All tests MUST be isolated from production data:
```python
# GOOD - Uses fixture
def test_something(tmp_path):
    test_data = tmp_path / "identities.json"
    test_data.write_text('{"identities": {}}')
    # ... test with test_data

# BAD - Uses production data
def test_something():
    with open("data/identities.json") as f:  # NEVER DO THIS
        data = json.load(f)
```

Before adding any test, ask: "Does this test touch real data in data/?" If yes: rewrite to use fixtures.

---

## Data Safety

### NEVER modify these files directly:
- `data/identities.json`
- `data/photo_index.json`
- `data/embeddings.npy`
- Any file in `data/` directory

### When testing:
- ALWAYS use test fixtures, not production data
- NEVER run tests without proper isolation
- Test files should use `tmp_path` or `tempfile` fixtures
- If a test needs data, create mock data in the test

### When writing scripts:
- ALWAYS include `--dry-run` as the default mode
- ALWAYS require explicit `--execute` or `--force` flag to make changes
- ALWAYS print what WOULD change before changing it

### When debugging:
- Use READ-ONLY inspection (cat, grep, python print statements)
- NEVER "fix" data by editing JSON files directly
- If data is corrupt, write a migration script with --dry-run

### Forbidden patterns:
```python
# NEVER do this:
with open("data/identities.json", "w") as f:
    json.dump(modified_data, f)

# Instead, if data migration is needed:
# 1. Create a script in scripts/
# 2. Add --dry-run flag
# 3. Get user approval before --execute
```

---

## Code Patterns

### Import Hygiene (Critical for Testability)
In `core/` modules, **defer heavy imports** (cv2, numpy, torch, insightface) inside functions that use them. This allows pure helper functions to be unit tested without ML dependencies installed.

```python
# GOOD: Pure functions can be tested without cv2
def add_padding(bbox, image_shape, padding=0.10):
    ...

def main():
    import cv2  # Deferred import
    import numpy as np
    ...

# BAD: Module-level import breaks tests
import cv2  # Tests fail if cv2 not installed
```

### Path Resolution
Always use `Path(__file__).resolve().parent` for file paths to ensure portability.

### Pathing in Data Files
Data files (JSON in `data/`) must use **relative paths** (e.g., `data/uploads/...`) never absolute paths (e.g., `/Users/.../data/uploads/...`).

---

## Git Protocol

### Commit Frequency
- Create a new Git commit after EVERY successful sub-task
- Do not wait for full task completion; prioritize small, incremental saves
- For CSS/styling work, commit after EVERY individual property group (ultra-granular)

### Commit Messages
Use conventional commit format: `feat:`, `test:`, `fix:`, `refactor:`, `docs:`, `chore:`, `style:`.

### TDD Commits
- Commit failing tests separately (`test: add failing tests...`)
- Then commit implementation (`feat: implement...`)

---

## Documentation Update Rules

### After Any Feature Change
Update these files if affected:
- `docs/MANUAL_TEST_CHECKLIST.md` -- Add test cases for new features
- `README.md` -- Update if user-facing behavior changes

### After Any Bug Fix
- Add the bug to the "Known Bug Locations" table in `docs/MANUAL_TEST_CHECKLIST.md`
- Mark as fixed once verified
- Write a regression test

### After Changing a Flow
1. Update the relevant checklist section
2. Remove obsolete test cases
3. Add new test cases

### Checklist Review Trigger
If any of these files change significantly, review the checklist:
- `app/main.py` (UI routes)
- `core/ingest_inbox.py` (upload flow)
- `templates/*.html` (UI changes)

### Release Documentation
Any session that changes user-visible behavior MUST end by:
1. Updating `docs/RELEASE_NOTES.md`
2. Adding an entry to `CHANGELOG.md`

---

## Data Persistence Invariants

When introducing any new data directory or file output:
1. **Git Hygiene:** Immediately add the path to `.gitignore`.
2. **Deployment Safety:** Ensure the code creates the directory (`makedirs(exist_ok=True)`) on startup. Never assume an ignored directory exists.
3. **Module Execution:** Always invoke scripts as modules (`python -m package.script`) to ensure correct path resolution.

---

## Deployment Rules

### Pre-Deployment Checklist
Before any deployment or containerization work, audit data files for environment-specific values:
```bash
# Check for absolute paths
grep -rn "/Users/\|/home/" data/ --include="*.json"

# Check for hardcoded hostnames
grep -rn "localhost\|127\.0\.0\.1" data/ --include="*.json"
```

### Deployment Impact Rule
Any change that affects how the app is built, configured, started, or where it reads/writes data MUST also update:
1. `docs/DEPLOYMENT_GUIDE.md` -- reflect the new setup steps
2. `.env.example` -- reflect any new/changed environment variables
3. `Dockerfile` -- if build process changed
4. `CHANGELOG.md` -- note the deployment-relevant change

### Gitignore vs Dockerignore vs Railwayignore

| File | Purpose | `data/` and `raw_photos/` |
|------|---------|---------------------------|
| `.gitignore` | What shouldn't be in version control | EXCLUDED (too large for git) |
| `.dockerignore` | What shouldn't be in Docker build context | INCLUDED (needed for bundles) |
| `.railwayignore` | What Railway CLI should upload | INCLUDED (needed for seeding) |

**Railway CLI uses `.gitignore` by default**, even when `.railwayignore` exists. Always use `railway up --no-gitignore` when deploying data that's gitignored but needed in the Docker image.

### Init Script Marker Files
When using marker files (like `.initialized`) to track deployment state:
1. NEVER create the marker unless the operation actually succeeded
2. ALWAYS validate the marker -- check that expected files exist even if marker is present
3. ALWAYS provide recovery -- if state is corrupted, detect and fix automatically
4. ALWAYS log clearly -- make it obvious what happened and what to do next

---

## Agent Behavior Rules

### Senior Engineer Protocol
1. **Assumption Surfacing:** Explicitly state assumptions before coding or refactoring.
2. **Confusion Management:** If requirements conflict or are ambiguous, STOP and ask for clarification.
3. **Simplicity Enforcement:** Prefer the simplest solution that satisfies constraints; reject over-engineering.

### Session Workflow (Boris Cherny Method)
1. **Start:** Read `tasks/lessons.md`, then `tasks/todo.md`, then recent `docs/SESSION_LOG.md`
2. **Plan:** Write plan to `tasks/todo.md` with checkboxes
3. **Execute:** Check off items as completed; commit after every sub-task
4. **Document:** Update session log, release notes, changelog as needed
5. **Learn:** After ANY correction from the user, add to `tasks/lessons.md`

### Regression Prevention Checklist
Before declaring ANY fix complete:
- [ ] Listed all features that could be affected
- [ ] Tested EACH feature explicitly
- [ ] Compared behavior before vs after change
- [ ] Checked edge cases (empty states, many items, errors)
- [ ] Ran verification scripts
- [ ] Passes staff engineer review standard

### Post-Bug Protocol
When a bug is discovered that could have been caught earlier:
1. Fix the bug
2. Add a rule to the appropriate doc that would have prevented it
3. Add a check to `docs/MANUAL_TEST_CHECKLIST.md`
4. Note it in `docs/SESSION_LOG.md`

---

## External Service CLIs & APIs

### Supabase Management API
- Endpoint: `https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth`
- Auth: Bearer token (personal access token from Dashboard -> Account -> Access Tokens)
- Get API keys: `GET /v1/projects/{ref}/api-keys` -- use `type: "legacy"`, `name: "anon"` for auth API
- **Always set `SUPABASE_ANON_KEY` to the legacy JWT key** (`eyJ...`), not the new `sb_publishable_...` key

### Railway CLI
- `railway variables set KEY=VALUE` -- set env vars
- `railway variables --json` -- list env vars
- `railway logs --tail N` -- view logs
- Always use CLI for env var changes, never ask user to do it manually

### General Rule
Before marking any task as "Manual Setup Required", check:
1. Does the service have a CLI tool?
2. Does the service have a Management/Admin API?
3. Can it be done via curl?
Only mark as manual if all three are unavailable.
