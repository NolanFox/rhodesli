---
name: rhodes-wiki key paths
description: Quick reference for navigating the rhodes-wiki sibling repo. Where the contract lives, where the parser lives, where to add Rhodes person dossiers.
type: reference
originSessionId: 53efd8a1-2589-4d9c-9291-7f0b5a60eaa8
---
`/Users/nolanfox/rhodes-wiki/` is the rhodes-wiki sibling repo (Session 159+). **PRIVATE GitHub remote since 2026-05-13 / Session 160**: `github.com/NolanFox/rhodes-wiki`. Common paths:

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
- `parse_fb_dom.py` — HTML parser (BeautifulSoup → dict). `parse_post(html) → dict`. `PARSER_VERSION = "0.1.0"`.
- `classify_images.py` — post-image vs avatar/icon classifier
- `extract_fb_post.py` — CLI for HTML-driven path: HTML dump → `inbox/pending/<slug>/{post.json, post.html, meta.json}`
- `write_inbox_entry.py` — pure builder + image downloader (fbcdn allowlist + 50MB cap + path containment from Codex P1-3)
- **`build_inbox_from_js_extraction.py`** (Session 160 NEW) — CLI for JS-structured path: `extracted.json` (from Chrome MCP `javascript_tool`) → `inbox/pending/<slug>/{post.json, extracted.json, meta.json}`. Used because Chrome MCP `read_page` returns accessibility tree, NOT HTML (Lesson 191).
- **`extract_kinship.py`** (Session 160 NEW) — regex-based kinship NER w/ 6 patterns + `RHODES_SEPHARDI_SURNAMES` corpus. PERSON-MATCH-001 v1.
- `extract_person_hints.py` — regex stub (Session 159); superseded by `extract_kinship.py` for relationships but still active for name extraction
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
cd /Users/nolanfox/rhodes-wiki && python3 -m pytest -q       # 209 tests as of S160

# JS-STRUCTURED PATH (use this for Chrome MCP captures — Session 160+ default)
python3 -m scripts.build_inbox_from_js_extraction \
    --input <extracted.json> \
    --output inbox/pending/<YYYY-MM-DD>_<fb-post-id>/

# HTML-DRIVEN PATH (use for stored HTML dumps — Session 159 path)
python3 -m scripts.extract_fb_post --input <html-file> --output inbox/pending/<slug>/

# Validate an inbox entry (works for either path)
python3 -m scripts.validate_inbox_contract --input inbox/pending/<slug>/post.json

# Kinship NER on a captured post.json (Session 160 NEW)
python3 -c "import json; from scripts.extract_kinship import extract_kinship_from_post; \
  post = json.loads(open('inbox/pending/<slug>/post.json').read()); \
  [print(t.to_dict()) for t in extract_kinship_from_post(post)]"

# Push to GitHub (PRIVATE remote, set Session 160)
cd /Users/nolanfox/rhodes-wiki && git push origin main
```
