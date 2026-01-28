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
- **Planning Mode**: Before starting any feature, enter Plan Mode (Shift+Tab twice) to create a `tasks.md`.
- **Task Orchestration**: Use the `/task` system to manage complex builds. Break work into steps smaller than 100 lines of code.
- **Git Protocol**: Commit after every successful task completion. Use semantic messages (e.g., "feat: implement face cropping script").
- **Memory Hygiene**: After completing a major feature, run `/compact` to preserve token space.
- **Verification**: Always run `python core/ingest.py` (with a dry run if possible) to verify data integrity before building UI components.

## Testing & TDD Rules

- **Red-Green-Refactor**: Always write a failing test before implementation
- **Green Before Commit**: All tests must pass before committing
- **Test Framework**: Use pytest and httpx for testing
- **Run Tests**: `pytest tests/` from project root