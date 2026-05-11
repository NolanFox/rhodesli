---
name: rhodes-wiki key paths
description: Quick reference for navigating the rhodes-wiki sibling repo. Where the contract lives, where the parser lives, where to add Rhodes person dossiers.
type: reference
originSessionId: 53efd8a1-2589-4d9c-9291-7f0b5a60eaa8
---
`/Users/nolanfox/rhodes-wiki/` is the rhodes-wiki sibling repo (Session 159+). Common paths:

## Architecture / contract
- `docs/ARCHITECTURE.md` — full design (~660 lines, architecture anchor)
- `docs/ARCHITECTURE.md` §3 — inbox JSON contract v0.1.0 (the rhodes-wiki↔rhodesli boundary)
- `docs/ARCHITECTURE.md` §4 — FB DOM extraction strategy (8-tier selector priority)
- `docs/ARCHITECTURE.md` §5 — person matching algorithm

## Harness
- `CLAUDE.md` (≤80 lines)
- `.claude/settings.json` — cross-repo bridge (read-only to rhodesli)
- `.claude/rules/fb-tos-rule.md` — manual FB nav rule
- `.claude/rules/browser-read-only.md` — inherited from rhodesli

## Scripts (all under `scripts/`)
- `parse_fb_dom.py` — pure parser module (BeautifulSoup → structured dict). `parse_post(html) → dict`. `PARSER_VERSION = "0.1.0"`.
- `classify_images.py` — post-image vs avatar/icon classifier
- `extract_fb_post.py` — CLI: HTML dump → `inbox/pending/<slug>/{post.json, post.html, meta.json}`
- `write_inbox_entry.py` — pure builder + image downloader (fbcdn allowlist + 50MB cap + path containment from Codex P1-3)
- `extract_person_hints.py` — regex stub (Session 159); real NER replaces in Session 160
- `validate_inbox_contract.py` — schema validator against ARCHITECTURE.md §3.1; exit 0 valid, 1 invalid, 2 file error

## Wiki vault
- `people/<Surname>/<given>_<birth-year>.md` — canonical dossiers
- `families/<surname>.md` — surname-keyed family pages
- `places/<slug>.md` — geographic anchors (`rhodes.md` seed exists)
- `posts/<YYYY-MM-DD>_<short-fb-id>/` — approved FB post archives
- `sources/<YYYY-MM-DD>_<type>_<short-id>.md` — citations
- `inbox/{pending|approved|rejected}/<slug>/` — extraction landing zone
- `templates/*.md` — frontmatter scaffolds
- `wiki/` — LLM Karpathy-style narrative layer (link-down rule)

## Tests
- `tests/fixtures/synthetic_fb_post_*.html` — SYNTHETIC FIXTURE marker required
- `tests/test_integration_e2e.py` — fixture → parse → build_inbox_entry → validate (catches future drift)

## Session 159 research (in rhodesli)
- `/Users/nolanfox/rhodesli/docs/session_context/session-159-research/01-fox-genealogy-patterns.md`
- `/Users/nolanfox/rhodesli/docs/session_context/session-159-research/02-rhodesli-ingest-contract.md`
- `/Users/nolanfox/rhodesli/docs/session_context/session-159-research/03-fb-dom-strategy.md`
- `/Users/nolanfox/rhodesli/docs/session_context/session-159-codex-audit.md`

## Common commands
```bash
# Run tests
cd /Users/nolanfox/rhodes-wiki && python3 -m pytest -q

# Extract a captured FB post
python -m scripts.extract_fb_post --input <html-file> --output inbox/pending/<slug> --unsafe-output-dir
# (--unsafe-output-dir is required if output isn't under <repo>/inbox/{pending|approved|rejected}/<slug>/; real captures should write to the canonical inbox path)

# Validate an inbox entry
python -m scripts.validate_inbox_contract --input inbox/pending/<slug>/post.json

# Build the inbox JSON envelope from parser output
python -m scripts.write_inbox_entry --parsed-json <parsed.json> --output-dir inbox/pending/<slug>
```
