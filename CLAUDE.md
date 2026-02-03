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

**Pathing**: Always use `Path(__file__).resolve().parent` for file paths.

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