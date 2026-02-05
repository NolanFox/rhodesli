# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the web server
python app/main.py

# Install web dependencies only
pip install -r requirements.txt

# Install full dependencies (including ML/AI for ingestion)
pip install -r requirements.txt && pip install -r requirements-local.txt
```

## Architecture

Rhodesli uses a **Hybrid Architecture** separating heavy AI processing from the lightweight web interface:

- **`app/`** - FastHTML web application (lightweight, no ML dependencies)
- **`core/`** - Heavy AI processing: face detection/recognition with InsightFace, embedding generation
- **`data/`** - SQLite databases and NumPy embeddings (gitignored)
- **`notebooks/`** - Experimental research

The flow is: `core/` processes photos → generates embeddings in `data/` → `app/` queries and displays results.

Two separate requirement files exist intentionally: `requirements.txt` for the web server, `requirements-local.txt` for ML/ingestion pipelines.

## Project Rules

**"Truth-Seeker" Constraint**: NO Generative AI. We use AdaFace/InsightFace for forensic matching. We value uncertainty (PFE) over confident matching.

**"Clean Vercel" Constraint**: `app/` must stay separate from `core/`. Heavy libs (torch, insightface, opencv) go in `requirements-local.txt`, NEVER in `requirements.txt`.

**Pathing**: Always use `Path(__file__).resolve().parent` for file paths in code. Data files (JSON in `data/`) must use **relative paths** (e.g., `data/uploads/...`) never absolute paths (e.g., `/Users/.../data/uploads/...`).

## Workflow Rules

### Planning
- **Plan-then-Execute**: Use Plan Mode (Shift+Tab twice) for all non-trivial tasks. Research and design before writing code.
- **Task Orchestration**: Use the `/task` system to manage complex builds. Break work into steps smaller than 100 lines of code.
- **Parallel Sessions**: Use multiple Claude sessions—one for research/exploration, another for building/implementation.

### Git Protocol
- **Commit Frequency**: Create a new Git commit after EVERY successful sub-task (e.g., after each failing test is made passing).
- **Commit Messages**: Use conventional commit format: `feat:`, `test:`, `fix:`, `refactor:`, `docs:`, `chore:`, `style:`.
- **Auto-Commit**: Do not wait for full task completion; prioritize small, incremental saves. Proceed autonomously.
- **TDD Commits**: Commit failing tests separately (`test: add failing tests...`) before committing implementation (`feat: implement...`).
- **Styling Commits**: For CSS/styling work, commit after EVERY individual property group (e.g., `style: add typography`, `style: add sepia filters`, `style: add border treatments`). Ultra-granular.

### Session Hygiene
- **Context Quality**: Run `/compact` every 20-30 minutes of active coding to maintain context quality.
- **Virtual Environment**: Always run `source venv/bin/activate` when opening a new terminal tab.
- **Verification**: Run `python core/ingest.py` (with a dry run if possible) to verify data integrity before building UI components.

## Testing & TDD Rules

- **Red-Green-Refactor**: Always write a failing test before implementation. No exceptions.
- **Green Before Commit**: All tests must pass before committing implementation code.
- **Test Framework**: Use pytest and httpx for testing.
- **Test Location**: Tests mirror source files: `core/crop_faces.py` → `tests/test_crop.py`.
- **Run Tests**: `pytest tests/` from project root.

## Data Safety Rules

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

### Before Adding Any Test
Ask: "Does this test touch real data in data/?"
If yes: Rewrite to use fixtures.

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

## Documentation Rules

### After Any Feature Change
Update these files if affected:
- `docs/MANUAL_TEST_CHECKLIST.md` - Add test cases for new features
- `README.md` - Update if user-facing behavior changes

### After Any Bug Fix
- Add the bug to the "Known Bug Locations" table in `docs/MANUAL_TEST_CHECKLIST.md`
- Mark as fixed once verified

### Checklist Maintenance

#### After Adding a Feature
1. Add test cases to `docs/MANUAL_TEST_CHECKLIST.md` under appropriate section
2. If it's a new flow, add a new section

#### After Fixing a Bug
1. Update the "Known Bug Locations" table in the checklist
2. Mark as `[x] Fixed` with date
3. Add a regression test case if applicable

#### After Changing a Flow
1. Update the relevant checklist section
2. Remove obsolete test cases
3. Add new test cases

#### Checklist Review Trigger
If any of these files change significantly, review the checklist:
- `app/main.py` (UI routes)
- `core/ingest_inbox.py` (upload flow)
- `templates/*.html` (UI changes)

## ADDITIONAL AGENT CONSTRAINTS (2026-02)

### SENIOR ENGINEER PROTOCOL
1. **Assumption Surfacing:** Explicitly state assumptions before coding or refactoring.
2. **Confusion Management:** If requirements conflict or are ambiguous, STOP and ask for clarification.
3. **Simplicity Enforcement:** Prefer the simplest solution that satisfies constraints; reject over-engineering.

### FORENSIC INVARIANTS (LOCKED)
These invariants are constitutional and override all other agent instructions.
They may ONLY be changed by explicit user instruction.

1. **Immutable Embeddings:** PFE vectors and derived embeddings in `data/` are read-only for UI and workflow tasks.
2. **Reversible Merges:** All identity merges must be reversible; no destructive operations.
3. **No Silent Math:** `core/neighbors.py` algorithmic logic is FROZEN. Changes require an explicit evaluation plan.
4. **Conservation of Mass:** The UI must never delete a face; only detach, reject, or hide with recovery.
5. **Human Authority:** `provenance="human"` decisions override `provenance="model"` in all conflicts.

Any potential violation of these invariants must be surfaced immediately.

## DATA PERSISTENCE INVARIANTS

When introducing any new data directory or file output:
1. **Git Hygiene:** Immediately add the path to `.gitignore`.
2. **Deployment Safety:** Ensure the code checks for existence and creates the directory (`makedirs(exist_ok=True)`) on startup in `app/main.py:startup_event()`. Never assume an ignored directory exists.
3. **Module Execution:** Always invoke scripts as modules (`python -m package.script`) to ensure correct path resolution.

## Pre-Deployment Checklist

Before any deployment or containerization work, audit data files for environment-specific values:

```bash
# Check for absolute paths
grep -rn "/Users/\|/home/" data/ --include="*.json"

# Check for hardcoded hostnames
grep -rn "localhost\|127\.0\.0\.1" data/ --include="*.json"

# Check for case-sensitivity issues (Mac → Linux)
# Look for files that differ only by case
find raw_photos/ -type f | sort -f | uniq -di
```

Any value that assumes a specific machine, OS, or filesystem should be flagged.

## Post-Bug Protocol

When a bug is discovered that could have been caught earlier:

1. Fix the bug
2. Add a rule to CLAUDE.md that would have prevented it
3. Add a check to `docs/MANUAL_TEST_CHECKLIST.md`
4. Note it in `docs/SESSION_LOG.md`

This creates a feedback loop where each bug improves the harness for future sessions.

## RELEASE DOCUMENTATION INVARIANT

Any session that changes user-visible behavior or system capabilities MUST end by:
1. Updating `docs/RELEASE_NOTES.md`
2. Adding an entry to `CHANGELOG.md`

A session is not considered complete until this is done. This is a hard rule, not a suggestion.

## Project Status

### Current State: Phase A Complete (Deployment Ready)

- Web app containerized with Docker
- Railway + Cloudflare deployment configured
- Health endpoint available at `/health`
- Staged upload workflow (files stored, no ML processing in production)

**NOT YET IMPLEMENTED:**
- Auth (Phase B)
- Community annotations (Phase C)
- Photo upload queue (Phase D)
- Admin moderation dashboard (Phase E)
- Automated backups (Phase F)

### Architecture Decisions (Summary)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting | Railway (Hobby plan) | Persistent volumes, simple deploys |
| Auth | Supabase (Phase B) | Managed auth + Postgres |
| DNS | Cloudflare subdomain | `rhodesli.nolanandrewfox.com` |
| Data | JSON = canonical, Postgres = community | Curator controls truth |
| ML Processing | Local only | Heavy deps not on server |

**Full details:** `docs/SYSTEM_DESIGN_WEB.md`

### Phase History

| Phase | Status | What It Does |
|-------|--------|--------------|
| A | ✅ Complete | Docker, Railway config, deployment guide |
| B | Not started | Auth + invite-only signup |
| C | Not started | Annotation engine |
| D | Not started | Photo upload queue |
| E | Not started | Admin moderation dashboard |
| F | Not started | Backup, security, polish |

### Key Files for Context

| File | Purpose |
|------|---------|
| `docs/SYSTEM_DESIGN_WEB.md` | Full architecture (1300+ lines) |
| `docs/DEPLOYMENT_GUIDE.md` | How to deploy to Railway |
| `docs/OPERATIONS.md` | Day-to-day runbook |
| `docs/SESSION_LOG.md` | What was done in each session |
| `CLAUDE.md` | Project conventions + this status |
| `CHANGELOG.md` | Version history |
| `docs/MANUAL_TEST_CHECKLIST.md` | Testing procedures |

### Session Handoff Protocol

At the END of every implementation session:
1. Update `docs/SESSION_LOG.md` with what was done
2. Update this Project Status section if phase status changed
3. Update `docs/RELEASE_NOTES.md` if user-visible changes
4. Update `CHANGELOG.md` with version entry