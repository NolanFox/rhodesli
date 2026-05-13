# Session 160 Assessment

**Date**: 2026-05-11 to 2026-05-13 (2-day session, paused/resumed)
**Mode**: interactive
**Repo of record**: `/Users/nolanfox/rhodes-wiki/` (no rhodesli code changes; rhodesli touched for docs only)
**Sister-repo version**: rhodes-wiki v0.2.0
**Prompt**: `docs/prompts/session-160-prompt.md`
**Log**: `docs/session_logs/session-160-log.md`
**Codex audit**: `docs/session_context/session-160-codex-audit.md`

## Shipped

### Phase 1: Capture FB post DOM
- [x] Captured Martha Girgenti's 2026-04-28 post about Edward + Renee Menasche (1971 Rhodesia) via Chrome MCP. **Evidence**: `inbox/pending/2026-04-28_2360240064471306/extracted.json` (12 top-level comments from JS extraction + 2 nested replies merged from user screenshots = 14/14).
- [x] Discovered that `read_page` returns accessibility tree, NOT raw HTML — pivoted to `javascript_tool` for structured extraction. Documented in ARCHITECTURE.md §4.1.

### Phase 2: Build new JS-structured inbox path
- [x] `scripts/build_inbox_from_js_extraction.py` (288 lines) — second capture path alongside Session 159's HTML-driven `extract_fb_post.py`. **Evidence**: real inbox entry validates clean against the contract.
- [x] Fixed Session 159 schema drift in `extract_fb_post.build_inbox_entry()` — 4 contract fields were silently missing (`reactions_count`, `fb_id`, `language_guess`, `captured_url_seen_at` shape). **Evidence**: 3 new e2e regression tests now catch this.

### Phase 3: PERSON-MATCH-001 (kinship NER)
- [x] `scripts/extract_kinship.py` — regex-based with 6 patterns + Rhodes-Sephardi surname corpus. **Evidence**: 16 tests; end-to-end on real Session 160 inbox produces kinship triples (Sarah Surmany → mother_of → Renee, etc.).

### Phase 4: First 6 person dossiers
- [x] 6 dossiers shipped: Edward, Renee (née Surmany), Zeni (LIVING + privacy gated), Simon, Lionel Menasche, Sarah Surmany. Plus 2 places (Rhodesia, Bath Road), 1 source citation, 1 wiki post entry. **Evidence**: `people/menasche/*.md`, `people/surmany/sarah.md`, `places/rhodesia.md`, `places/bath-road-rhodesia.md`, `sources/2026-04-28_fb-post_2360240064471306.md`, `posts/2026-04-28_martha-girgenti-menasche-rhodesia-1971.md`.

### Phase 5: Codex audit + fixes
- [x] Codex CLI v0.130 (gpt-5.5, xhigh) ran on 2 commits, returned 0 P0 / 2 P1 / 6 P2 / 4 P3.
- [x] Both P1s fixed (path-traversal + byte-hash). 4 P2s fixed inline. 2 P2s partial + backlogged. 2 P3s fixed inline. **Evidence**: `docs/session_context/session-160-codex-audit.md` + commit `0c70304`.

### Phase 6: Closeout
- [x] rhodes-wiki bumped to v0.2.0; CHANGELOG, ROADMAP, wiki/log.md, ARCHITECTURE.md §4.1 updated.
- [x] 7 new Lessons (191-197) added to rhodesli `tasks/lessons.md`.
- [x] Session log + assessment + SESSION_HISTORY backfilled.

## Deferred (with breadcrumbs)

- **FB-DOWNLOAD-001**: Image binary download for the 1971 Menasche photo — needs Chrome MCP site-permissions OR rhodesli upload via FB photo ID `10242118814369834`. → Session 161 task. Note in `posts/2026-04-28_martha-girgenti-menasche-rhodesia-1971.md`.
- **FB-PERMISSIONS-001**: Document how to grant Chrome MCP per-site approval for facebook.com (Claude in Chrome v1.0.70 didn't expose an obvious toggle). → Session 161 documentation.
- **FB-NESTED-001**: JS extraction misses depth>0 nested replies (`[role=article][aria-label^="Comment by"]` selector doesn't catch nested structure). Worked around via screenshot verification for Session 160. → Session 161 parser fix.
- **JS-BUILDER-001 / -002 / -003 / -004**: BACKLOG entries in `rhodes-wiki/BACKLOG.md` for kinship "Aunt and Uncle to us" via-field, inbox JSON privacy markers, kinship regex name coverage, HTML CLI validator parity.

## Red flags

None that block. The key risks identified:

- **(low)** The 2 nested-reply additions to `extracted.json` were manual (from user screenshots), not extracted by the JS path. If a future session re-runs `build_inbox_from_js_extraction.py` against a fresh JS-only extraction, those 2 entries will disappear. Mitigation: extracted.json IS the audit trail; never regenerate from a fresh capture for an existing entry. Documented in the entry's `_session_160_provenance.known_gaps`.

- **(low)** Privacy: Zeni Menasche's dossier has `audience: private` + custom `living: true` flag. Both rhodes-wiki and rhodesli have no published surface for this dossier (rhodes-wiki has no Notion publish enabled; rhodesli admin-only). Risk is theoretical until publish-time. Lesson 197 documents the need for the publish redactor to honor the `living:` flag.

- **(none)** No rhodesli production code changed; rhodesli test baseline (4271 app tests) is intact. Only docs touched: `tasks/lessons.md`, `docs/session_logs/`, `docs/assessments/`, `docs/session_context/`, ROADMAP.md (next commit).

## Next session should verify FIRST

1. `cd ~/rhodes-wiki && python3 -m pytest -q` returns 209 passed
2. `python3 -m scripts.validate_inbox_contract --input inbox/pending/2026-04-28_2360240064471306/post.json` returns OK
3. `git -C ~/rhodes-wiki log --oneline | head -5` shows v0.2.0 + Codex fixes commits intact
4. rhodesli `make test-fast` baseline (4271 tests) — no rhodesli code touched but verify

## AI Tool Usage

- **Tool**: Codex CLI v0.130 (gpt-5.5, xhigh)
- **Agent type**: Independent (fresh context, no prior session knowledge)
- **Task**: Audit Session 160's rhodes-wiki commits (74755b2 + 67cd292)
- **Findings**: 12 total (0 P0, 2 P1, 6 P2, 4 P3)
- **Acted on**: 2 P1s + 4 P2s + 2 P3s fixed inline this session (8 total)
- **Deferred**: 2 P2s (partial fixes; full versions backlogged) + 2 P3s (backlogged as JS-BUILDER-002/003)
- **Discarded**: None
- **Value assessment**: **STRONG**
- **Would we have found this ourselves?** The path-traversal regression (P1-1): probably not — it's a Session-159-fixed-then-forgotten regression that only fires on the new code path. The byte-hash divergence (P1-2): unlikely — would require explicit hash-equivalence testing we hadn't written. Codex caught both.
- **Comparison note**: Single audit run, ~3min wall-clock, 201k tokens. Higher ROI than Session 159's Codex audit (which caught 6 P1 + 4 P2 + 3 P3 in a much larger commit; both runs justify the ~5min/phase cost).

## Memory backup

To be run by stop-gate hook at session-end (per `scripts/backup-memory.sh`).
