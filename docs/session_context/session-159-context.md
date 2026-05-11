# Session 159 — Rhodes Wiki + Facebook Post Ingestion

**Date opened**: 2026-05-11
**Predecessor**: [session-158e-assessment.md](../assessments/session-158e-assessment.md) (PRD-063 cutover complete, DB 1.3 GB)
**Mode**: implementation → user-checkpoint paced (user at work today)
**Initiating user prompt**: "Build a way to open a specific post in one of the Rhodes Facebook groups, extract caption + comments + images into a wiki similar to fox-genealogy, identify people from caption/comment context, and ingest images into rhodesli via an approval queue. Separate repo. Manual FB navigation, Claude reads DOM. Harness compliance: parallelize, subagents, Codex audit."

---

## Architecture decisions (locked via AskUserQuestion 2026-05-11)

| Decision | Choice | Reasoning |
|---|---|---|
| Repo location | **Separate repo: `/Users/nolanfox/rhodes-wiki`** | Clean boundary; rhodesli stays generalized photo platform; mirrors fox-genealogy sibling pattern |
| Wiki format | **Local markdown only** (no Notion sync) | Simpler than fox-genealogy; can add Notion later if needed |
| Image flow | **Approval queue first** | Extends existing PROPOSED→CONFIRMED gatekeeper pattern; safer for TOS (user clicks "ingest") |
| FB TOS | **Manual navigation, Claude expands comments + reads** | User opens post; Claude clicks "View N more comments" via Chrome MCP, then reads DOM. No cross-post crawling, no pagination, no automation across sessions. |

---

## Why this matters

1. **Rhodes is genealogically distinct**: ~2,000 members in "Jews of Rhodes" FB group share photos, family stories, identifications. This is high-signal data that's currently locked in Facebook (no search, no export, lost when posts age out).
2. **Captions + comments = identification context**: A photo of "Aunt Rebecca at Bouboulina's wedding 1953" with comments naming people is the EXACT context rhodesli's identity-suggestion pipeline (PRD-059) needs. Caption text > embedding distance for identification (Lesson 172).
3. **Rhodesli stays a generalized tool**: Adding Rhodes-specific scraping to rhodesli would violate the architectural boundary set in CLAUDE.md. A separate repo keeps the platform clean while letting Rhodes-specific genealogy compound.
4. **Approval queue compounds existing work**: rhodesli already has identity_suggestions + INBOX state. The FB pipeline becomes another upstream feeder of that queue, alongside direct user uploads.

---

## Reference patterns (fox-genealogy)

The fox-genealogy repo is the canonical template. Key patterns to mirror:

| Pattern | fox-genealogy location | rhodes-wiki adaptation |
|---|---|---|
| Layered architecture | CLAUDE.md "Layered architecture" | Vault → cross-rhodesli bridge → docs → automation (drop Notion publish for now) |
| CRAIGen principles | CLAUDE.md "Critical Invariants" | Reuse all 5 (Accuracy, Disclosure, Privacy-tiered, Education, Decompose-first) |
| People dossiers | `people/Fox/Albert_1893.md` | `people/<surname>/<given>_<birth-year>.md` |
| Source citations | `sources/YYYY_<type>_<desc>.md` | Same; FB posts as `sources/YYYY-MM-DD_fb-post_<short-id>.md` |
| LLM wiki layer | `wiki/` Karpathy-style | Same; load-bearing "link down only" rule |
| Cross-repo bridge | additionalDirectories in `.claude/settings.json` | Same; rhodes-wiki gets read-only access to rhodesli |
| Codex audit | `~/.codex/config.toml` gpt-5.5 xhigh | Same harness |
| Multi-session | Atomic primitives, namespaced locks | Same |

What we are **NOT** copying:
- Notion publishing pipeline (deferred — local markdown only for now)
- GEDCOM / ged4py kinship resolver (fox-family-specific; Rhodes genealogy uses different sources)
- DNA workflow (out of scope)
- Translation pipeline (deferred; Ladino/Greek/French/Italian may need this later)

---

## Cross-repo relationships

```
                    ┌──────────────────────────┐
                    │  rhodes-wiki (NEW)       │
                    │                          │
                    │  - FB post extraction    │
                    │  - Wiki markdown vault   │
                    │  - Person dossiers       │
                    │  - Inbox (pending posts) │
                    └────────┬─────────────────┘
                             │ writes JSON
                             │ to inbox/pending/
                             ▼
                    ┌──────────────────────────┐
                    │  rhodesli (existing)     │
                    │                          │
                    │  - /admin/rhodes-inbox   │  ← NEW route
                    │  - Approval UI           │  ← NEW
                    │  - Existing /upload      │
                    │  - identity_suggestions  │
                    └──────────────────────────┘
                             ▲
                             │ approval triggers
                             │ existing ingest path
```

**Boundary rule**: rhodes-wiki is the upstream producer (FB → JSON + markdown). rhodesli is the photo+identity platform. The bridge is a single JSON contract (schema TBD in Phase 1). rhodes-wiki never writes directly to rhodesli's DB.

---

## Facebook DOM reality check

Empirical facts (not researched yet — Phase 1 task):
- FB uses obfuscated CSS class names (e.g., `x1iyjqo2 x6ikm8r ...`)
- DOM structure changes frequently
- Posts in groups have: post header (author, date), text body, image gallery, comment thread (nested)
- "View N more comments" requires click to expand
- "See more" inside long text/comments requires click to expand
- Tagged people get `aria-label` on the link (sometimes)
- Image URLs are signed CDN URLs that expire (must download immediately)
- Multiple image sizes (thumbnail, medium, full) — need to grab full

**Extraction strategy** (Phase 3):
1. User opens post in Chrome (logged in)
2. User expands all top-level comments + replies manually (per TOS choice)
3. Claude invokes `mcp__claude-in-chrome__read_page` to capture rendered DOM
4. Parser script normalizes into structured JSON
5. Save raw HTML alongside parsed JSON for audit + reparse

**Risk**: DOM patterns will break over time. Mitigation: save raw HTML so re-parse is always possible; keep parsing logic in a single module with versioned schema.

---

## Person identification pipeline

For each extracted post:
1. **Caption + comments → name candidates** (NER + manual @mention parsing)
2. **Existing person match**: cross-reference against `people/` directory entries (slug match + name normalization)
3. **Rhodesli identity match**: query rhodesli's identities table for name + community="Rhodes"
4. **Face match (downstream)**: when image is approved in rhodesli, existing ML pipeline runs
5. **Output**: `person_hints: [{name, slug?, rhodesli_identity_id?, confidence, evidence}]`

Confidence tiers (mirror fox-genealogy's confidence-tiers.md):
- **Strong**: Name appears in caption AND in comments AND matches existing person slug
- **Good**: Name in caption OR comment, matches existing slug
- **Possible**: Name mentioned, no slug match
- **Weak**: Family surname only, no specific person

---

## Pipeline summary (target end-state, multi-session)

| Step | Owner | Trigger |
|---|---|---|
| User opens FB post in Chrome | User | Manual |
| User expands all comments | User (per TOS choice) | Manual |
| Claude reads DOM | rhodes-wiki tool | User invokes `extract-fb-post` |
| Parser writes inbox/pending/<id>/ | rhodes-wiki script | Automatic |
| Person hint extraction | rhodes-wiki script | Automatic |
| Wiki post markdown created | rhodes-wiki script | Automatic |
| Image download | rhodes-wiki script | Automatic (URLs expire) |
| User reviews in `/admin/rhodes-inbox` | rhodesli UI | User opens admin panel |
| Approve → ingest image to rhodesli | rhodesli endpoint | User clicks approve |
| Face detection + identity matching | rhodesli ML | Automatic post-ingest |
| Final approval (PROPOSED→CONFIRMED) | rhodesli admin | User |

---

## Known gaps / decisions deferred

- **Multi-image posts**: how to handle 5+ image post? Approve all, or one at a time?
- **Comment reply attribution**: if a comment names a person, is it about the post or about another comment? (Likely heuristic: same post unless reply chain indicates otherwise.)
- **Author identification**: post author may BE the person being discussed. Track separately.
- **Source URL stability**: FB post URLs work for logged-in users; what about future researchers? Save permalink + screenshot of the post page as canonical citation evidence.
- **Comment author privacy**: FB commenters are living people. Apply CRAIGen privacy redactor before any external publish (but rhodes-wiki is private internal research, like fox-genealogy — same audience-tiered rule).
- **Notion publishing**: deferred. Local markdown only this session.
- **Translation**: deferred. Many Rhodes posts may be in Ladino, French, Italian, Greek, Hebrew. Mark text language in frontmatter; defer translation pipeline.

---

## Anti-goals (explicitly NOT in scope this session)

- Full Facebook scraping / pagination / cross-post crawling
- Real-time monitoring of group activity
- Automated posting back to FB
- Notion sync
- Translation
- DNA / GEDCOM integration
- Public publishing to a website

---

## Success criteria for Session 159

**Autonomous phases (while user at work)** — must complete:
1. rhodes-wiki repo scaffolded at `/Users/nolanfox/rhodes-wiki/` with git initialized, CLAUDE.md, README, directory structure, harness rules ported from fox-genealogy
2. Architecture doc `rhodes-wiki/docs/ARCHITECTURE.md` covering: data model, JSON contract with rhodesli, FB DOM strategy, person matching algorithm
3. Inbox JSON schema defined + documented + example fixture
4. Stub extraction script `rhodes-wiki/scripts/extract_fb_post.py` with placeholder DOM parser + unit tests against fixture
5. Wiki markdown templates: `person.md`, `post.md`, `family.md`, `place.md` (frontmatter + skeleton)
6. Codex audit on the scaffolded repo (Phase 1.5 + Phase 2 + Phase 3 batched)
7. rhodesli ROADMAP updated, Session 159 in "Recently Completed" with proper provenance, AD entry for this cross-repo architecture if applicable

**User-checkpoint phases (when user returns)** — START but don't block on:
8. Real FB post DOM sample (user pastes/captures one)
9. Parser updated against real DOM patterns
10. End-to-end test: extract → wiki write → rhodesli inbox display

**Stretch (only if Phase 8 lands)**:
11. rhodesli `/admin/rhodes-inbox` route with HTMX preview
12. Approval endpoint that triggers existing upload path

---

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| FB DOM differs from assumptions | High | Phase 1 captures real sample before parser commits; raw HTML saved for re-parse |
| Codex CLI hangs (Sessions 152-155 pattern) | Medium | Use `codex exec "<prompt>" </dev/null` form (working invocation per Lesson 155); fall back to Claude subagent if hangs |
| User-level Anthropic budget exhaustion (L182) | Low | Launch ONE canary subagent first; verify ≥30s wall-clock + ≥100 tokens before parallelizing |
| Worktree subagent doesn't commit (L166-167) | Medium | Explicit "git status --porcelain must be clean before returning" in agent prompts; stagger launches to avoid git lock |
| Memory file loss (L169) | Low | stop-gate.sh auto-runs backup-memory.sh; verify at session end |
| Image URLs expire before download | High | Download IMMEDIATELY during parse, before writing JSON; never defer image fetch |
| Living person privacy (CRAIGen) | High | rhodes-wiki is private internal research (mirror fox-genealogy audience-tiered rule); privacy redactor only fires at public-publish boundary (none this session) |

---

## Breadcrumbs

- Predecessor: [session-158e-assessment.md](../assessments/session-158e-assessment.md)
- fox-genealogy template: `/Users/nolanfox/fox-genealogy/CLAUDE.md`
- Related rhodesli systems:
  - identity_suggestions table (PRD-059)
  - INBOX state (data/identities.json + Supabase)
  - Cross-collection person search (TOOLS-007, Session 148b)
  - Family Cluster Score (AD-235)
- Memory entries to honor:
  - `feedback_never_modify_production_data.md` — READ-ONLY browser on rhodesli production
  - `feedback_retry_tools.md` — retry Chrome MCP failures
  - `feedback_voice_mode.md` — original prompt was voice-dictated; distilled to structured plan above

## Next-session candidates

Once Session 159 completes:
- **Session 160**: First real FB post end-to-end (user provides post URL, full pipeline test)
- **Session 161**: Approval queue UI in rhodesli + first batch of approved Rhodes photos
- **Session 162**: Person dossier auto-update when new posts arrive (existing dossier gets new photo evidence appended)
