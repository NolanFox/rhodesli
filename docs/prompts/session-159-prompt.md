# Session 159 — Rhodes Wiki + Facebook Post Ingestion Pipeline

**Date**: 2026-05-11
**Mode**: implementation → user-checkpoint paced
**Context file**: [docs/session_context/session-159-context.md](../session_context/session-159-context.md) (READ THIS FIRST)

---

## Goal

Build the scaffolding for **rhodes-wiki**, a new sibling repo to rhodesli that:
1. Extracts Facebook group posts (caption + comments + images) into a structured local markdown wiki
2. Maintains person dossiers for the Rhodes Jewish community (parallels fox-genealogy)
3. Produces an inbox of pending photos with person hints that feeds rhodesli's approval queue

**This is a multi-session arc.** Session 159 = architecture, scaffolding, parsing-against-fixture, harness setup. Real FB DOM testing happens in Session 160 with user present.

---

## Architecture (locked — see context file)

- **Repo**: `/Users/nolanfox/rhodes-wiki/` (new sibling to rhodesli + fox-genealogy)
- **Format**: Local markdown only (no Notion sync this session)
- **Image flow**: Approval queue (rhodes-wiki/inbox/ → rhodesli admin → ingest)
- **TOS**: User navigates FB manually; Claude may expand comments + read DOM via Chrome MCP

---

## Harness compliance (NOT NEGOTIABLE)

Per `.claude/rules/session-defaults.md`:

- **Parallelize** independent work via worktree subagents (Phase 1 research, Phase 5 implementation)
- **/clear between phases** — every commit must be followed by /clear before next phase
- **Codex audit after each implementation phase** (gpt-5.5, xhigh) — invoke as `codex exec "<prompt>" </dev/null` (Lesson 155 working form; NEVER --full-auto)
- **Memory backup** at session end via `scripts/backup-memory.sh` (auto-run by stop-gate.sh)
- **Pre-flight budget canary** before parallel subagents (Lesson 182): launch 1, verify ≥30s + ≥100 tokens, then parallelize
- **Worktree commit discipline** (Lessons 166-167): every subagent must `git status --porcelain` clean before returning; stagger worktree creation to avoid git lock
- **Codex model pin freshness**: if `.claude/rules/codex-model-pin.txt` is >14 days old, refresh per `.claude/rules/ai-tool-audit.md` BEFORE Phase 1 audit

---

## Phase 0 — Orient (5 min, single-context)

1. Read `tasks/lessons.md` repeat-offender section + Lessons 155, 166-170, 178-190
2. Read context file: `docs/session_context/session-159-context.md`
3. Read fox-genealogy template:
   - `/Users/nolanfox/fox-genealogy/CLAUDE.md`
   - `/Users/nolanfox/fox-genealogy/README.md` (if exists)
   - `/Users/nolanfox/fox-genealogy/.claude/settings.json` (cross-repo bridge config)
   - Directory listing of `people/`, `sources/`, `scripts/`, `wiki/`
4. Run baseline: `make test-fast` must pass (rhodesli regression baseline)
5. Run `bash scripts/harness-check.sh` — if it fails, fix BEFORE proceeding
6. Verify `.claude/current_session.txt` = `159` and `.claude/session_mode.txt` = `implementation`
7. Commit checkpoint: nothing yet, just confirm baseline

**Acceptance**: Baseline tests green, harness-check green, fox-genealogy patterns understood.

---

## Phase 1 — Research (parallel subagents) (30-45 min)

Launch **ONE canary subagent first** (Lesson 182 budget check). If it returns ≥30s + ≥100 tokens, launch the other two in parallel.

### Subagent A (canary) — fox-genealogy pattern extraction
**Type**: Explore
**Scope**: thorough
**Brief**: "Read `/Users/nolanfox/fox-genealogy/CLAUDE.md`, `/Users/nolanfox/fox-genealogy/.claude/` rules + skills, `/Users/nolanfox/fox-genealogy/wiki/README.md`, plus 3 sample files: `people/Fox/Albert_1893.md`, a recent `sources/*.md`, a recent `hypotheses/*.md`. Extract the EXACT patterns we need to mirror: (1) CLAUDE.md structure, (2) frontmatter schema for person/source/hypothesis files, (3) directory layout, (4) lint rules, (5) cross-repo bridge config, (6) what's Fox-family-specific vs portable. Output: a markdown 'patterns brief' under 500 lines. Do NOT modify any fox-genealogy files."

### Subagent B — rhodesli ingest surface mapping
**Type**: Explore
**Scope**: medium
**Brief**: "Survey rhodesli's existing photo upload + identity creation surface. Identify: (1) the route(s) where new photos enter the system, (2) the auth model (which routes need admin vs logged-in), (3) the data shape required (filename, source, collection, community_id, etc.), (4) how PROPOSED identities are created and how identity_suggestions populate, (5) the schema of any 'inbox' or 'pending upload' tables. Find: app/upload_*.py, app/ingest_*.py, app/identity_suggestions_*.py if they exist. Output: a 'rhodesli ingest contract' brief — what fields rhodes-wiki must produce in inbox JSON for the approval handoff to work. Under 400 lines."

### Subagent C — Facebook group post DOM patterns
**Type**: general-purpose
**Brief**: "Research, via WebSearch + WebFetch, the current DOM patterns Facebook uses for group posts (as of 2026). Topics: (a) how comments are loaded (lazy/expand), (b) image URLs in posts (signed CDN, expiration), (c) common selectors that survive obfuscation (aria-label, role, data-* attrs), (d) how 'View N more comments' and 'See more' buttons are structured, (e) tagged-person link patterns. Do NOT scrape live Facebook. Use public docs, dev blogs, browser-automation Stack Overflow answers, and the Claude in Chrome MCP tool documentation. Output: a 'FB DOM brief' with concrete selector strategies + caveats + a 'parser fixture' recommendation. Under 600 words."

After all three return:
- Save outputs to `docs/session_context/session-159-research/` (3 files)
- Commit: `docs(session-159): Phase 1 research briefs (fox-genealogy patterns, rhodesli ingest, FB DOM)`
- /clear

**Acceptance**: 3 research briefs in repo, committed, /clear executed.

---

## Phase 2 — Architecture decisions doc (15-20 min, single-context)

In a single foreground pass (NOT a subagent — this is design work that benefits from the just-loaded research):

1. Create `/Users/nolanfox/rhodes-wiki/` directory (do NOT git init yet — Phase 3)
2. Write `/Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md` covering:
   - **Repo layout**: directory tree with purpose per directory
   - **Frontmatter schemas**: YAML for person.md, post.md, source.md, place.md, family.md (mirror fox-genealogy where applicable)
   - **Inbox JSON contract** (the rhodes-wiki ↔ rhodesli boundary):
     ```yaml
     inbox_entry_id: <slug>
     fb_post_url: <permalink>
     fb_post_id: <derived hash>
     captured_at: <iso8601>
     post_author_name: <string>
     post_author_fb_id: <string|null>
     post_date: <iso8601 or null>
     caption_text: <string>
     comments: [{author, text, timestamp, replies: [...]}]
     images: [{local_path, original_url, alt_text, image_hash}]
     person_hints: [{name, normalized_name, slug?, rhodesli_identity_id?, confidence, evidence}]
     source_md_path: <path within rhodes-wiki>
     wiki_post_md_path: <path within rhodes-wiki>
     status: pending | approved | rejected
     ```
   - **FB DOM extraction strategy** (informed by Subagent C brief)
   - **Person matching algorithm** (NER + slug normalization + rhodesli cross-ref)
   - **Codex audit cadence + rhodes-wiki harness rules**
   - **Anti-goals** (copy from context file)
3. Commit: `docs(session-159): rhodes-wiki ARCHITECTURE.md` (commit happens INSIDE the new repo — see Phase 3.0)
4. /clear

**Note**: This commit can't happen until Phase 3 git-inits the repo. Stage the file, do Phase 3, then first commit will include this.

**Acceptance**: ARCHITECTURE.md exists, covers all 6 sections, ≤300 lines (split into sub-files if larger per doc-size rule).

---

## Phase 3 — Scaffold rhodes-wiki repo (20-30 min, single-context)

### 3.0 Initialize repo
```bash
cd /Users/nolanfox/rhodes-wiki
git init
git branch -M main
```

### 3.1 Directory structure
```
rhodes-wiki/
├── CLAUDE.md                    # Ported from fox-genealogy, adapted
├── README.md
├── ROADMAP.md
├── CHANGELOG.md
├── .gitignore                   # node_modules, __pycache__, .DS_Store, .env, raw_html/
├── .claude/
│   ├── settings.json            # additionalDirectories: rhodesli (READ-ONLY)
│   ├── current_session.txt
│   └── rules/
│       ├── session-defaults.md  # Mirror rhodesli's
│       ├── verification-gate.md
│       ├── browser-read-only.md (rhodesli production AND Facebook)
│       └── fb-tos-rule.md       # NEW: manual nav, Claude reads only
├── docs/
│   ├── ARCHITECTURE.md          # Written in Phase 2
│   └── reference/
│       └── confidence-tiers.md  # Ported from fox-genealogy
├── people/
│   └── README.md                # explains naming convention
├── sources/
│   └── README.md
├── posts/                       # Approved FB post archives (markdown)
│   └── README.md
├── places/
│   └── rhodes.md                # Seed: island of Rhodes overview
├── families/
│   └── README.md
├── inbox/
│   ├── README.md                # explains pending/ approved/ rejected/ flow
│   ├── pending/
│   ├── approved/
│   └── rejected/
├── templates/
│   ├── person.md
│   ├── post.md
│   ├── family.md
│   ├── place.md
│   └── source.md
├── scripts/
│   ├── extract_fb_post.py       # Phase 4
│   ├── parse_fb_dom.py          # Phase 4
│   ├── write_wiki_post.py       # Phase 5
│   ├── extract_person_hints.py  # Phase 5
│   └── lint_wiki.py             # Phase 6 (ported from fox-genealogy)
├── tests/
│   ├── fixtures/
│   │   └── sample_fb_post.html  # placeholder for Phase 4
│   ├── test_parse_fb_dom.py
│   └── test_write_wiki_post.py
├── pyproject.toml               # Python deps
└── wiki/                        # LLM-curated narrative layer
    ├── README.md                # link-down rule
    ├── index.md
    └── log.md
```

Create all directories. README.md files for stub directories should be 5-20 lines explaining purpose.

### 3.2 Port `CLAUDE.md` from fox-genealogy
Adapt headers:
- "Purpose" section: rhodes-wiki is the **Rhodes Jewish community research workspace**. Sister repo to rhodesli (photo platform) + fox-genealogy (different community).
- "Stack": Markdown vault + YAML frontmatter | local-only (no Notion this session) | Python parsers | Claude Chrome for FB DOM reads
- "Critical Invariants": port CRAIGen 5 principles verbatim — they're universal
- "Layered architecture": adapt for rhodes-wiki specifically (no GEDCOM/DNA/translation layers yet)
- "Cross-repo bridge (rhodesli)": rhodes-wiki gets read-only access to rhodesli
- "Workflow": port the Phase 0 cross-repo scan pattern
- **Keep ≤ 80 lines** per rhodesli's CLAUDE.md size rule

### 3.3 Write `.claude/settings.json`
Mirror fox-genealogy's pattern with `additionalDirectories: ["/Users/nolanfox/rhodesli"]`. Include any hooks rhodesli/fox-genealogy share that are useful.

### 3.4 Write `.claude/rules/fb-tos-rule.md` (NEW)
Content:
```markdown
# Facebook TOS Rule — Manual Nav, Claude Reads Only

ABSOLUTE rules for any rhodes-wiki tool that touches Facebook:

1. **User opens the post.** Claude does NOT navigate to facebook.com URLs.
2. **User expands all top-level comments + replies manually.** Claude MAY click
   inline "View N more comments" or "See more" buttons ONCE the user has the
   post page open — but ONLY to expand text/comments on the SAME post.
3. **No cross-post navigation.** Claude never clicks links that leave the
   currently-open post page.
4. **No pagination / no group feed scrolling.**
5. **No automated session re-use.** Each post is a single, user-initiated event.
6. **Read-only after expansion.** Claude reads the rendered DOM via Chrome MCP
   `read_page` or `get_page_text`. No form fills, no posting, no reactions.
7. **No downloading from FB CDN at scale.** Images are downloaded only when a
   post is being archived to inbox — one post at a time.

Violation = TOS risk. If you find yourself wanting to "just check the next
post automatically," STOP — that's the bug. Tell the user to open it.
```

### 3.5 Write templates (`templates/*.md`)
Each template is a markdown file with YAML frontmatter + skeleton sections. Examples:

`templates/person.md`:
```markdown
---
type: person
name: "Family, Given Middle"
slug: family-given
birth: {date: "YYYY-MM-DD", place: "Rhodes, Greece", source: "[citation]"}
death: {date: "", place: "", source: ""}
family: family-slug
aliases: []
photos: []
sources: []
audience: private
confidence: tier-tbd
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---

# Family Given Middle

## Biography

## Family

## Photos

## Sources

## Notes
```

Similar skeletons for `post.md`, `family.md`, `place.md`, `source.md`.

### 3.6 Write `places/rhodes.md` seed
~50 lines: brief overview of Rhodes Jewish community, key locations (Juderia, La Bashilica synagogue, etc.), timeline anchors (1492 Sephardic arrival, 1944 deportation, post-war diaspora to Belgian Congo / Rhodesia / US / Israel).

### 3.7 Write `pyproject.toml`
Minimal Python project (Python 3.11+):
- deps: pyyaml, beautifulsoup4, pytest, python-slugify
- dev deps: pytest, ruff
- entry: `extract-fb-post = "rhodes_wiki.scripts.extract_fb_post:main"`

### 3.8 First commit
```bash
cd /Users/nolanfox/rhodes-wiki
git add -A
git commit -m "$(cat <<'EOF'
scaffold(rhodes-wiki): initial repo structure

- CLAUDE.md ported from fox-genealogy template (≤80 lines)
- Directory layout: people/, sources/, posts/, places/, families/, inbox/, templates/, scripts/, tests/, wiki/
- Cross-repo bridge: read-only access to /Users/nolanfox/rhodesli via additionalDirectories
- FB TOS rule: manual nav, Claude reads only (.claude/rules/fb-tos-rule.md)
- Templates for person/post/family/place/source markdown
- Inbox JSON contract defined in docs/ARCHITECTURE.md
- Initial commit; no FB parsing yet

Session 159 (rhodesli) — see /Users/nolanfox/rhodesli/docs/prompts/session-159-prompt.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### 3.9 /clear

**Acceptance**: rhodes-wiki repo exists at `/Users/nolanfox/rhodes-wiki/`, git initialized, first commit landed, CLAUDE.md ≤80 lines, ARCHITECTURE.md ≤300 lines, structure matches Phase 3.1.

---

## Phase 4 — Parser stub + fixture-based tests (30-45 min)

**This phase can be parallelized.** Launch two subagents:

### Subagent D — Build extract_fb_post.py CLI
**Type**: general-purpose (with Edit/Write/Bash)
**Worktree**: yes
**Brief**: "Build `scripts/extract_fb_post.py` in `/Users/nolanfox/rhodes-wiki/`. This is a CLI that takes a path to an HTML file (raw DOM dump from Chrome MCP read_page) and an output directory, parses the FB post structure, downloads images, and writes inbox/pending/<id>/ entries. For Session 159 the HTML parsing logic is a STUB — use BeautifulSoup to extract: (1) post text (heuristic: first big text block), (2) image URLs (img tags inside the post region), (3) comment text blocks. Don't try to handle FB's obfuscated classes — just produce a defensible v0 that we'll refine against real DOM in Session 160. Include type hints, docstrings, and 5+ pytest tests in tests/test_parse_fb_dom.py using a synthetic fixture HTML you also create at tests/fixtures/synthetic_fb_post.html (write your own minimal FB-like HTML; do NOT copy real FB HTML). Tests must pass. Commit each logical unit. Final commit message: 'feat(rhodes-wiki): extract_fb_post.py v0 + synthetic fixture'. Verify git status --porcelain is clean before returning."

### Subagent E — Build inbox JSON writer + person hint stub
**Type**: general-purpose (with Edit/Write/Bash)
**Worktree**: yes (different from D)
**Brief**: "Build `scripts/write_inbox_entry.py` in `/Users/nolanfox/rhodes-wiki/`. Takes parsed FB post dict (matching docs/ARCHITECTURE.md inbox JSON contract) + a target directory, writes `inbox/pending/<slug>/post.json` + downloads images to `inbox/pending/<slug>/images/`. Also build `scripts/extract_person_hints.py` as STUB: takes caption + comments text, returns list of candidate names via simple regex (capitalized word pairs/triples). Don't do real NER yet — Session 160 task. Tests: 4+ pytest tests in tests/test_write_inbox_entry.py + tests/test_extract_person_hints.py. Use mocked image downloads (don't hit real URLs). All tests pass. Commit each logical unit. Final commit: 'feat(rhodes-wiki): inbox JSON writer + person hint stub'. Verify clean git status."

After both return:
- Verify each worktree's `git status --porcelain` is clean
- Merge worktree branches into main:
  ```bash
  cd /Users/nolanfox/rhodes-wiki
  # Merge subagent D's branch
  # Merge subagent E's branch
  # Run pytest after each merge
  ```
- /clear

**Acceptance**: extract_fb_post.py + write_inbox_entry.py + extract_person_hints.py exist in main; all tests in tests/ pass; synthetic fixture committed.

---

## Phase 5 — Codex audit batch (15-20 min, single-context)

Audit the work of Phases 2-4 in a single Codex pass:

```bash
codex exec "$(cat <<'EOF'
Audit the new repo at /Users/nolanfox/rhodes-wiki. Review:
1. docs/ARCHITECTURE.md — soundness of the inbox JSON contract, FB DOM strategy, person matching algorithm. Any missing edge cases?
2. CLAUDE.md — does it follow the fox-genealogy template faithfully? Any rhodes-wiki-specific rules missing?
3. .claude/rules/fb-tos-rule.md — gaps in TOS protection?
4. scripts/extract_fb_post.py + parse_fb_dom.py — security (path traversal, untrusted HTML parsing, image download from untrusted URLs), code quality, test quality, error handling
5. scripts/write_inbox_entry.py — file system safety (slug normalization, path traversal), atomicity of writes
6. scripts/extract_person_hints.py — false positive rate of regex name detection, what's missing for real NER

Report P0/P1/P2/P3 findings with file:line references. Be specific about which Lesson (from /Users/nolanfox/rhodesli/tasks/lessons.md) each finding maps to where applicable.
EOF
)" </dev/null
```

- Save output to `/Users/nolanfox/rhodesli/docs/session_context/session-159-codex-audit.md` with the standard provenance header
- Fix P0/P1 immediately in foreground (NEW commits, not amend per CLAUDE.md)
- BACKLOG P2 to `/Users/nolanfox/rhodes-wiki/BACKLOG.md` (create if needed)
- Note P3 in session log
- Commit fix(es) atomically: `fix(rhodes-wiki): session-159 Codex audit P0/P1 fixes`
- /clear

**Fallback if `codex exec` hangs**: Use general-purpose Claude subagent with the same prompt. Note the fallback in the audit file's provenance header.

**Acceptance**: codex-audit file written; P0/P1 fixed and committed; BACKLOG.md has any P2 entries.

---

## Phase 6 — Closeout (15-20 min)

### 6.1 USER CHECKPOINT (announce + wait)
At this point, Phases 0-5 are complete and rhodes-wiki is scaffolded. The session is at a natural pause.

Write a short status message to the user describing:
- What shipped (concrete commits)
- What was deferred (real FB DOM parsing → Session 160)
- How to test today: open a Rhodes FB post, capture HTML, run `python scripts/extract_fb_post.py` against it, see what works/breaks
- Any open questions discovered during the session

Then **continue with closeout (autonomous)** — do not block on user response.

### 6.2 rhodesli-side updates
In `/Users/nolanfox/rhodesli/`:
- Update `ROADMAP.md`:
  - Add `[x] 2026-05-11: **v0.99.80 — Session 159**: rhodes-wiki scaffolded` to "Recently Completed" with phase-by-phase summary
  - Add a new ROADMAP section "## Rhodes Wiki Integration" with planned sessions 160, 161, 162
  - Update "Planned Sessions" with Session 160 entry
- Update `CHANGELOG.md` with v0.99.80 entry
- Update `docs/roadmap/SESSION_HISTORY.md` with Session 159 entry
- Create `docs/assessments/session-159-assessment.md` per `.claude/rules/self-assessment.md` template
- Add any new lessons to `tasks/lessons.md` (likely candidates: pattern for cross-repo session-arc, FB TOS rule design)

### 6.3 rhodes-wiki-side closeout
In `/Users/nolanfox/rhodes-wiki/`:
- Update `ROADMAP.md` with "Recently Completed" entry for the scaffolding session
- Update `CHANGELOG.md` with v0.1.0 entry
- Run `pytest` one more time — must pass
- `git log --oneline` should show 5-8 clean commits

### 6.4 Memory updates (rhodesli memory dir)
Add memory entries:
- `project_rhodes_wiki_repo.md` — pointer to new repo, its purpose, the rhodesli↔rhodes-wiki contract
- `reference_rhodes_wiki_paths.md` — key file paths
- Update MEMORY.md index

### 6.5 Final commits + push
- rhodesli: `git push origin main`
- rhodes-wiki: stays local (no GitHub remote yet — user can add later)
- Verify rhodesli `git log origin/main..HEAD` is empty

### 6.6 Session-end checks
- /session-review skill (mandatory)
- /ux-review only if screenshots were taken (probably none this session)
- Memory backup auto-runs via stop-gate.sh
- Final assessment file committed

**Acceptance**:
- rhodesli pushed to main, health verified
- rhodes-wiki has 5+ clean commits locally
- All 8 SUCCESS CRITERIA from the context file (autonomous phases 1-7) are met
- /session-review run

---

## When user returns / Session 160 handoff

Write `docs/prompts/session-160-prompt.md` skeleton at end of Phase 6 with these planned tasks:
1. User provides 1 real Rhodes FB post URL + opens in Chrome
2. User expands all comments
3. Claude captures DOM, runs extract_fb_post.py
4. Compare output to expected → iterate parser
5. End-to-end test: extract → wiki write → first inbox entry visible
6. If time: build rhodesli `/admin/rhodes-inbox` route

---

## Verification gate (end of session)

Per `.claude/rules/verification-gate.md`, before declaring done:

| Check | Method |
|---|---|
| rhodes-wiki repo exists | `ls /Users/nolanfox/rhodes-wiki/.git` |
| Scaffolding complete | All 10 top-level dirs from Phase 3.1 present |
| CLAUDE.md ≤80 lines | `wc -l /Users/nolanfox/rhodes-wiki/CLAUDE.md` |
| ARCHITECTURE.md present | `ls /Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md` |
| Tests pass | `cd /Users/nolanfox/rhodes-wiki && pytest` |
| Codex audit done | `ls /Users/nolanfox/rhodesli/docs/session_context/session-159-codex-audit.md` |
| rhodesli tests still pass | `cd /Users/nolanfox/rhodesli && make test-fast` |
| rhodesli pushed | `git log origin/main..HEAD` empty |
| Assessment written | `ls /Users/nolanfox/rhodesli/docs/assessments/session-159-assessment.md` |
| Memory backed up | stop-gate.sh ran |

If any FAIL: fix it. The verification gate is not advisory.

---

## Notes for future sessions

- Session 160: real FB DOM test (user-paced)
- Session 161: rhodesli `/admin/rhodes-inbox` UI + first approvals
- Session 162: dossier auto-update from new posts
- Eventually: Ladino/Greek/Italian translation pipeline (deferred — see fox-genealogy DNA/translation patterns for template)
- Eventually: Notion publishing (deferred — fox-genealogy pattern is portable when needed)
