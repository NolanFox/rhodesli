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
