---
name: rhodes-wiki sibling repo
description: New sibling repo at /Users/nolanfox/rhodes-wiki/ scaffolded in Session 159 for Rhodes Jewish community FB post ingestion + person dossiers. rhodes-wiki ↔ rhodesli via inbox JSON contract.
type: project
originSessionId: 53efd8a1-2589-4d9c-9291-7f0b5a60eaa8
---
`/Users/nolanfox/rhodes-wiki/` — private research workspace, sibling to rhodesli (photo platform) and fox-genealogy (Fox-family).

## Purpose
Captures Facebook group posts from "Jews of Rhodes" (~2,000 members) into a structured markdown vault. Produces an `inbox/pending/<slug>/post.json` per ARCHITECTURE.md §3.1 contract that feeds rhodesli's approval queue (Session 161 builds the rhodesli-side route).

## Cross-repo boundary
- rhodes-wiki NEVER writes to rhodesli. `.claude/settings.json` denies it explicitly.
- Single contract = `inbox/pending/<slug>/post.json` (versioned `contract_version: "0.1.0"`)
- Any contract change requires coordinated update on rhodesli's `/admin/rhodes-inbox` route (planned Session 161)

## Architecture choices (locked Session 159)
- Separate repo (not in rhodesli) — keeps rhodesli generalized photo platform
- Local markdown only (no Notion sync)
- Approval queue first (extends PROPOSED→CONFIRMED gatekeeper)
- Manual FB nav by user; Claude reads DOM + may expand inline comments via Chrome MCP (narrow exception to browser-read-only)

## Status as of 2026-05-13 (Session 160 close)
- **v0.2.0**, 17 commits, **PRIVATE GitHub** remote: `github.com/NolanFox/rhodes-wiki` (since 2026-05-13)
- **209 pytest tests** passing (was 173 → +36 from Session 160 JS builder + kinship)
- Codex audited twice: Session 159 (gpt-5-codex/xhigh, all P1/P2/P3 addressed); Session 160 (gpt-5.5/xhigh, 0 P0 / 2 P1 fixed / 6 P2 mostly fixed / 4 P3)
- Scripts: parse_fb_dom, classify_images, extract_fb_post, write_inbox_entry, extract_person_hints, validate_inbox_contract, **build_inbox_from_js_extraction** (NEW S160), **extract_kinship** (NEW S160 — regex-based kinship NER w/ Rhodes-Sephardi corpus)
- First real inbox entry: `inbox/pending/2026-04-28_2360240064471306/` (Martha Girgenti / 1971 Menasche family Rhodesia, 14/14 comments)
- First 6 dossiers: Edward / Renee (née Surmany) / Zeni (LIVING) / Simon / Lionel Menasche + Sarah Surmany. 2 places: rhodesia, bath-road-rhodesia.

## Multi-session arc
- Session 159 (DONE 2026-05-11): scaffold + parser stubs + contract
- Session 160 (DONE 2026-05-13): first real FB DOM via Chrome MCP javascript_tool (NOT HTML — Lesson 191), kinship NER v1, first 6 dossiers, JS-structured capture path documented, private GitHub remote
- Session 161 (NEXT): rhodesli `/admin/rhodes-inbox` route + `rhodes_inbox_entries` Supabase table + FB image binary download (FB-DOWNLOAD-001) + nested-reply parser fix (FB-NESTED-001) + Chrome MCP site-permission docs (FB-PERMISSIONS-001)
- Session 162: dossier auto-update + first wiki/ narrative pages

## Critical rules in rhodes-wiki/.claude/rules/
- `fb-tos-rule.md` — manual nav, narrow comment-expand exception, no cross-post navigation
- `browser-read-only.md` — inherited from rhodesli (Lesson 149)

## Key paths
- Architecture: `/Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md`
- Contract definition: ARCHITECTURE.md §3.1
- FB DOM strategy: ARCHITECTURE.md §4 (plus `/Users/nolanfox/rhodesli/docs/session_context/session-159-research/03-fb-dom-strategy.md`)
- Person matching: ARCHITECTURE.md §5
- Codex audit: `/Users/nolanfox/rhodesli/docs/session_context/session-159-codex-audit.md`
