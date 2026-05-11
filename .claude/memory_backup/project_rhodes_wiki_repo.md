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

## Status as of 2026-05-11
- v0.1.0, 12 commits, local-only (no GitHub remote)
- 173 pytest tests passing
- Codex audited (gpt-5-codex/xhigh): all 6 P1 + 2 P2 + 2 P3 findings fixed
- Scripts: parse_fb_dom, classify_images, extract_fb_post, write_inbox_entry, extract_person_hints, validate_inbox_contract
- End-to-end smoke verified against synthetic fixture

## Multi-session arc
- Session 159 (DONE): scaffold + parser stubs + contract
- Session 160: first real FB DOM + real NER (PERSON-MATCH-001) + first 5 Rhodes dossiers
- Session 161: rhodesli `/admin/rhodes-inbox` route + `rhodes_inbox_entries` Supabase table
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
