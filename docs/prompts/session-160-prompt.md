# Session 160 — rhodes-wiki: First Real FB DOM End-to-End + Person-Hint v1

**Mode**: interactive (user provides real FB post, Claude iterates)
**Predecessor**: [session-159-assessment.md](../assessments/session-159-assessment.md)
**Repo for this session**: `/Users/nolanfox/rhodes-wiki/` (NOT rhodesli code)
**Inherited state**: rhodes-wiki v0.1.0, 173 tests passing, 12 commits, no GitHub remote

This is a SKELETON written at the end of Session 159 Phase 6. The actual prompt will be refined when the session opens.

---

## Pre-flight verification (FIRST action — DO BEFORE anything else)

```bash
cd /Users/nolanfox/rhodes-wiki
git log --oneline | head -3        # expect 12 commits from Session 159
python3 -m pytest -q                # expect 173/173 passing
cat docs/ARCHITECTURE.md | head -10 # contract v0.1.0 is canonical
```

If any of these fail, STOP and diagnose before proceeding.

---

## Phase 0 — User provides the post

User opens 1 Rhodes Jewish community FB post in Chrome (logged in). User manually expands all top-level comments + replies. Claude does NOT navigate.

User confirms post is open and comments are expanded, then prompts Claude to capture.

---

## Phase 1 — Capture DOM

Per `.claude/rules/fb-tos-rule.md`:
- Claude uses `mcp__claude-in-chrome__find` to locate any remaining "View N more replies" buttons INLINE in the open post page only
- Claude clicks each (max 3 retries per button) to expand
- Claude calls `mcp__claude-in-chrome__read_page` once expansion is complete
- Save raw HTML to a temp file (will be moved into inbox)

---

## Phase 2 — Run extraction; iterate against real DOM

```bash
cd /Users/nolanfox/rhodes-wiki
python3 -m scripts.extract_fb_post \
    --input <temp-html-path> \
    --output inbox/pending/<YYYY-MM-DD>_<short-fb-id>/ \
    --unsafe-output-dir  # if needed; remove once path is canonical
```

Inspect output. Iterate `scripts/parse_fb_dom.py` selectors against any real-DOM divergence from synthetic fixtures. Add at least 1 real-fixture regression test (sanitized — strip living-person PII from any test fixture; keep structural markers).

Validate:
```bash
python3 -m scripts.validate_inbox_contract --input inbox/pending/<slug>/post.json
```

Expect: OK.

---

## Phase 3 — PERSON-MATCH-001 (real NER)

Replace `scripts/extract_person_hints.py` regex stub with:
1. Real NER (spaCy English model is fine for v1; Hebrew/Sephardic name corpus deferred)
2. Slug normalization (lowercase + diacritic-fold + hyphen)
3. Match against existing `people/<surname>/` slugs
4. Cross-ref against rhodesli identities table for `community=rhodes` (read-only, via cross-repo bridge)
5. Confidence tier per `docs/reference/confidence-tiers.md`

Tests: ≥10 covering NER + slug match + rhodesli cross-ref (mock the Supabase call).

---

## Phase 4 — First 5 Rhodes person dossiers

From the post, create 5 `people/<Surname>/<given>_<birth-year>.md` dossiers. Use `templates/person.md` as starting frontmatter. Cite the FB post as the source (Tier-3-secondary per confidence-tiers.md).

Also create the corresponding `sources/<YYYY-MM-DD>_fb-post_<short-id>.md` source entry.

If any person matches a known rhodesli identity, populate `rhodesli.identity_ids`.

---

## Phase 5 — Codex audit

```bash
codex exec "Audit the changes in /Users/nolanfox/rhodes-wiki since commit <session-159-tip-sha>. Focus on: NER false positives, slug normalization for diacritics + apostrophes, rhodesli cross-ref query safety, real-DOM parser changes, new person dossier frontmatter completeness. P0/P1/P2/P3 report." </dev/null
```

Save audit to `/Users/nolanfox/rhodesli/docs/session_context/session-160-codex-audit.md`.

Fix P0/P1 in foreground; BACKLOG P2 to `rhodes-wiki/BACKLOG.md`.

---

## Phase 6 — Closeout

- rhodes-wiki: update ROADMAP/CHANGELOG (v0.2.0), `wiki/log.md` one-line entry, commit final state
- rhodesli: update SESSION_HISTORY.md + assessment + push (this session adds NO rhodesli code, just docs)
- Memory: any new lessons surfaced from real FB DOM should be added to `tasks/lessons.md`
- /session-review

---

## Anti-goals (out of scope)

- Multi-post crawling (per fb-tos-rule.md)
- Notion publish
- Translation
- Public dossier publishing
- Mechanical FB TOS hook (TOS-HOOK-001 BACKLOG)
- Atomic write refactor (RELIABILITY-001 BACKLOG)
- rhodesli `/admin/rhodes-inbox` route (Session 161)
