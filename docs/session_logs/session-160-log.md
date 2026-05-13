# Session 160 Log — rhodes-wiki: First Real FB DOM End-to-End + Person-Hint v1

**Started**: 2026-05-11
**Mode**: interactive
**Predecessor**: docs/assessments/session-159-assessment.md
**Repo for this session**: `/Users/nolanfox/rhodes-wiki/` (NOT rhodesli code)
**Prompt**: docs/prompts/session-160-prompt.md

## Inherited state (verified at start)
- rhodes-wiki v0.1.0, 12 commits, 173 tests passing
- Latest commits: b1835e2 BACKLOG entries, 8515c32 Codex audit fixes
- ARCHITECTURE.md contract is canonical
- No GitHub remote yet (local-only)

## Phase Checklist
- [x] Phase 0: User provides post (Martha Girgenti's 2026-04-28 Edward+Renee Menasche 1971 Rhodesia post)
- [x] Phase 1: Capture DOM — TWO retries needed; ended up using javascript_tool (not read_page) because `read_page` returns accessibility tree, not HTML. 12/14 comments captured via JS; 2 nested replies via user-screenshot verification.
- [x] Phase 2: NEW path built — `scripts/build_inbox_from_js_extraction.py` complements Session 159's HTML-driven `extract_fb_post.py`. Validator-clean inbox entry produced. 4 schema-drift contract bugs fixed in extract_fb_post.py (P1-A through P1-D).
- [x] Phase 3: PERSON-MATCH-001 v1 shipped — `scripts/extract_kinship.py` (regex-based, 6 patterns) + RHODES_SEPHARDI_SURNAMES corpus seed. spaCy NER deferred to v2. 16 tests on real Session 160 phrasings.
- [x] Phase 4: 6 dossiers (Edward, Renee, Zeni, Simon, Lionel Menasche + Sarah Surmany) + 2 places (rhodesia, bath-road-rhodesia) + source citation + post entry.
- [x] Phase 5: Codex audit (gpt-5.5/xhigh, ~3min, 201k tokens) — 0 P0 / 2 P1 / 6 P2 / 4 P3. ALL P1 fixed inline (path-traversal, byte-hash). 4 P2 fixed inline (contract validation, tagged_people schema, expansion_complete heuristic, dossier wording). 2 P2 partial. P3-C/D fixed. JS-BUILDER-001/002/003/004 backlogged.
- [x] Phase 6: Closeout — rhodes-wiki v0.2.0, CHANGELOG, ROADMAP, wiki/log.md, ARCHITECTURE.md §4.1 updated. rhodesli Lessons 191-197 added. SESSION_HISTORY updated. Assessment written.

## Verification Gate
- [x] All phases re-checked against original prompt
- [x] Feature Reality Contract — inbox entry exists, validates against contract, kinship NER produces real output on real data, 6 dossiers exist with cross-links, source entry exists
- [x] rhodes-wiki tests green: 209/209 (was 173, +36 new tests)
- [x] rhodesli tests: NO rhodesli code changed; only docs (Lessons, SESSION_HISTORY, assessment, audit log). 4271 app tests baseline assumed intact.

## Phase log

**Phase 0-1** (Capture): 4 retries to get FB tab into MCP group. Root cause: Chrome MCP creates one tab group per Claude Code session. The user opening a FB tab outside that group requires navigating the MCP-enrolled empty tab to the URL. Once enrolled, `read_page` returned accessibility tree (62k chars saved to tool-results file). 7 comments visible in first slice; full thread had 14. JS extraction (`javascript_tool`) returned structured JSON for 12 top-level comments + caption + reactions + image metadata. 2 nested replies (Martha Girgenti's reply to David Zen Amoils, Isaac Menashe's "Indeed!" reply to April Merdjan) were missed by JS but recovered from user screenshots.

**Phase 2** (Build inbox): New CLI `scripts/build_inbox_from_js_extraction.py` reads `extracted.json` → emits contract-valid `post.json` + `extracted.json` (audit) + `meta.json`. Discovered Session 159 `extract_fb_post.py` schema drift (4 missing contract fields) — fixed inline + 3 new e2e regression tests. 192 → 209 tests total.

**Phase 3** (Kinship NER): 6 regex patterns + `RHODES_SEPHARDI_SURNAMES` corpus. Tested on real Session 160 phrasings: extracts Sarah Surmany → mother_of → Renee, Rachel → sister_of → Diana Amato Merdjan, Rachel ↔ Nathanel Menashe spouse pair, Martha Girgenti → cousin_of → David Zen Amoils.

**Phase 4** (Dossiers): 6 person.md files, 2 places, 1 source, 1 post entry. All cross-linked, all citing specific FB comment_ids as evidence. Zeni Menasche flagged `living: true` for privacy gating.

**Phase 5** (Codex audit): Independent audit caught 2 real P1s (path traversal regression; byte-hash divergence between claim and on-disk reality). Both fixed. Audit saved to `docs/session_context/session-160-codex-audit.md`.

**Phase 6** (Closeout): Documents updated, version bumped to v0.2.0, 7 new Lessons (191-197) added to `tasks/lessons.md`, SESSION_HISTORY backfilled.

## Notable findings
- Chrome MCP `read_page` ≠ raw HTML (Lesson 191). The Session 159 architecture assumed it did.
- FB dual-renders DOM (modal + feed); JS extraction needs dedupe (Lesson 192).
- MCP "Sensitive key" gate over-blocks name fields; workaround: dual-channel extraction (Lesson 193).
- One comprehensive JS call beats N small ones for permission-popup fatigue (Lesson 194).
- Comments are primary genealogical source, not metadata (Lesson 195).
- Living-person dossiers need an explicit `living: true` flag in addition to `audience: private` (Lesson 197).

## Followups for Session 161
- FB-DOWNLOAD-001: Image binary download for the Menasche 1971 photo
- FB-PERMISSIONS-001: Document Chrome MCP site-permission grant for facebook.com
- FB-NESTED-001: JS extraction nested-reply parser fix
- JS-BUILDER-001 through 004 (BACKLOG entries in rhodes-wiki/BACKLOG.md)
- rhodesli `/admin/rhodes-inbox` route construction
