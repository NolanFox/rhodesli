# fox-genealogy Patterns Brief for rhodes-wiki Scaffold

**Session:** 159 Research Agent  
**Date:** 2026-05-11  
**Source repository:** `/Users/nolanfox/fox-genealogy/` (read-only survey)  
**Target repository:** `/Users/nolanfox/rhodes-wiki/` (to be created)

This document extracts the **portable architecture patterns** from fox-genealogy and clearly separates them from Fox-family-specific content, methodologies, and workflows. See paths explicitly cited; all quotes/findings can be verified against those files.

---

## 1. CLAUDE.md Template Structure

**File location:** `/Users/nolanfox/fox-genealogy/CLAUDE.md` (122 lines, highly structured)

### Section headers (in order)

1. **Title + Purpose** — one-sentence elevator pitch; pointer to README.md
2. **Stack** — tools & APIs (Markdown vault + YAML + GEDCOM + MCP + Notion)
3. **Critical Invariants (CRAIGen 5 principles)** — **PORTABLE; see section 6 below**
4. **Layered architecture** — 5-layer model diagram (see section 3)
5. **LLM Wiki Layer** — Karpathy-style rules; **PORTABLE** (see section 5)
6. **Multi-session** — concurrent-session atomicity patterns
7. **Specialized workflows** — DNA, Translation, Cross-repo skills (deferred; reference existing docs)
8. **Cross-repo bridge** — read-only settings.json pattern
9. **Notion structure** — existing assumption (DO NOT copy verbatim; rhodes-wiki may differ)
10. **Communication channels** — email/ancestry/Notion; **somewhat portable**
11. **Workflow** — session discipline: todos, cross-repo scan, commits, /clear, session-tracking
12. **Naming Conventions** — person/source/hypothesis/prompt file paths
13. **Frozen Files** — (none currently)
14. **Key Skills** — planned skill inventory (DO NOT copy; rewrite for rhodes context)
15. **Reference Docs** — pointer catalog

### Universal vs. Fox-specific

**COPY as-is (with surnames blanked):**
- Critical Invariants (CRAIGen 5) — pure methodology
- Layered architecture (5-layer diagram)
- LLM Wiki Layer rules
- Naming Conventions (pattern only; not the family names)
- Workflow discipline (Phase 0 cross-repo scan, /clear patterns, session-tracking)

**SKIP entirely (Fox-family-specific):**
- Notion structure (section 9) — the "Family History" / "Jewish Family History" hub is fox-genealogy's existing publishing surface
- Specialized workflows (section 7) — DNA_WORKFLOW.md, TRANSLATION_WORKFLOW.md, SHARED_SKILLS.md assume fox-genealogy's phase roadmap
- Cross-repo bridge specifics (section 8) — assumes `/Users/nolanfox/rhodesli` exists; rhodes-wiki will have its own cross-repo rules

**REWRITE for Rhodes:**
- Title + Purpose (different family, different photo archive cross-link)
- Stack (likely unchanged)
- Multi-session + Communication channels (may differ for Rhodes vs. Fox)
- Reference Docs pointer (curate for Rhodes context)

**Line-count target:** 80–120 lines (condensed, assuming you reuse CRAIGen + layered-arch patterns).

---

## 2. .claude/settings.json Template

**File location:** `/Users/nolanfox/fox-genealogy/.claude/settings.json` (40 lines)

### Portable structure

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "_comment": "[YOUR REPO] — [description]",
  "permissions": {
    "additionalDirectories": [
      "[CROSS-REPO PATH, IF ANY]"
    ],
    "allow": [
      "Read([CROSS-REPO]/**)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(ls:*)",
      "Bash(grep:*)",
      "Bash(find:*)",
      "Bash(wc:*)",
      "Bash(cat:*)"
    ],
    "deny": [
      "Edit([CROSS-REPO]/**)",
      "Write([CROSS-REPO]/**)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "[YOUR PHASE-0 SCRIPT]",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Fox-specific to replace

- `additionalDirectories` = `/Users/nolanfox/rhodesli` (fox's cross-repo). For rhodes-wiki, use the equivalent Rhodes archive path (if any).
- Session-start hooks (lines 26–36) — currently scan `scan_rhodesli_prompt.py` + `check_new_gedcoms.py`. For rhodes-wiki, create equivalent advisory hooks (never blocking; exit 0 always).

### Portable allow/deny pattern

The 8-line `allow` list (git read, bash read-only) + 2-line `deny` (no cross-repo writes) is standard across both repos. Reuse as-is.

---

## 3. Directory Layout

**Source:** `/Users/nolanfox/fox-genealogy/` listing + CLAUDE.md § Layered architecture

| Directory | Purpose | Portable? |
|-----------|---------|-----------|
| `people/` | Per-person dossiers (canonical vault) | ✓ Yes, pattern only |
| `sources/` | Source records + citations | ✓ Yes, pattern only |
| `events/` | Dated events (reserved; not yet in use) | ✓ Yes |
| `hypotheses/` | Open research questions | ✓ Yes |
| `docs/` | Architecture, research, session context | ✓ Yes (rewrite Rhodes-specific) |
| `wiki/` | LLM-curated narrative (Karpathy-style) | ✓ Yes |
| `blog/` | Draft posts → publishing surface | ~ Adapt (Rhodes may use different publish lane) |
| `scripts/` | Automation, GEDCOM, OCR, etc. | ~ Some portable (lint, validate), some Fox-specific |
| `inbox/` | Triage (gmail/, ancestry/, etc.) | ~ Adapt (Rhodes comms workflow may differ) |
| `tasks/` | todos.md, lessons.md, ideas-inbox.md | ✓ Yes (pattern; rewrite tasks) |
| `posts/` | (listed; usage unclear) | ~ Skip initially |
| `tests/` | Pytest (currently sparse) | ✓ Yes |
| `.claude/` | Harness (settings.json, skills, agents) | ✓ Yes (rewrite skills) |

### Sub-directories to mirror

```
docs/
├── architecture/      (OVERVIEW, CROSS_REPO, COMMS, DNA, TRANSLATION, SHARED_SKILLS, etc.)
├── research/          (genealogy-ai-best-practices, ancestry-access, mcp-landscape, etc.)
├── reference/         (confidence-tiers, living-person-rule, frontmatter-specs, GEDCOM versions)
├── session_context/   (session-NNN-prompt, session-NNN-assessment, etc.)
└── audit/             (GENEALOGY_DECISIONS.md GD-NNN log, living-person-bypass.log)

wiki/
├── _templates/        (concept-page.md, place-page.md, methodology-page.md)
├── people/            (person narratives)
├── places/            (place studies)
├── methodology/       (how-we-verify notes)
└── index.md, log.md, README.md

scripts/
├── lint_wiki.py       (PORTABLE: wiki linter; no Fox-specific paths)
├── validate_person_dossier.py  (PORTABLE: frontmatter validator)
├── validate_source_record.py    (PORTABLE)
└── validate_hypothesis.py       (PORTABLE)
```

---

## 4. Frontmatter Schemas

All schemas live in `/Users/nolanfox/fox-genealogy/docs/reference/`.

### person.md (`person-frontmatter-spec.md`, 265 lines)

**YAML keys (required / optional):**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | string | ✓ | Always `person` |
| `person_id` | string | ✓ | Stable slug; never changes |
| `display_name` | string | ✓ | Full name as used in prose |
| `sort_name` | string | ✓ | "Surname, Given" for indexing |
| `surname_at_birth` | string | ✓ | May differ from current surname |
| `given_names` | array | ✓ | `["Given", "Middle", ...]` |
| `birth_year` | integer | ✓ | Year only; full date in facts |
| `death_year` | integer or null | ✓ | Year or `null` if living |
| `living` | boolean | ✓ | See living-person-rule.md |
| `gender` | string | ✓ | `male | female | unknown | other` |
| `created` | date | ✓ | YYYY-MM-DD |
| `updated` | date | ✓ | YYYY-MM-DD |
| `disclosure` | string | ✓ | AI assistance + source compliance note |
| `notion_id` | string or null | ~ | Notion Members DB page URL |
| `rhodesli_identity_id` | string or null | ~ | Cross-repo identity UUID (fox-specific: replace with your archive's identity key) |
| `gedcom_xref` | string or null | ~ | `@I123@` from any GEDCOM |
| `overall_tier` | string | ✓ | `confirmed | strong | probable | weak | hypothesis | rejected` (per confidence-tiers.md) |
| `facts` | dict | ✓ | Each claim → sources (see Mills 3-Layer) |
| `relationships` | dict | ~ | `parents`, `spouses`, `children`, `siblings` (NOT computed by AI) |
| `hypotheses` | array | ~ | Links to open research questions in `hypotheses/` |
| `rhodesli_evidence` | dict | ~ | Cross-repo photo/face evidence (Fox-specific; adapt or remove) |

**Audience-tiered privacy:**
- Field `audience: internal | family | public` (optional; defaults to internal per `living-person-rule.md`)
- Only public-bound artifacts trigger the privacy gate

**Conflict preservation block:**
```yaml
conflicts:
  - description: "Two sources disagree on birth year"
    sources: [list of conflicting sources]
    resolution: "Working assumption; awaiting primary record"
```

**Markdown body structure:**
- `# [Person Name] (YYYY–YYYY)` — heading
- `## Brief` — one-paragraph summary
- `## Tier explanation` — why this tier
- `## Detailed Biography` — multi-paragraph narrative
- `## Key Sources` — 5–10 most important sources
- `## Open Questions` — research targets
- `## Cross-references` — links to related dossiers
- `## Disclosure` — AI-generated sections flagged

### source.md (`source-frontmatter-spec.md`, 192 lines)

**YAML keys (required / optional):**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | string | ✓ | Always `source` |
| `source_id` | string | ✓ | Stable slug |
| `source_class` | string | ✓ | `original_record | derivative_official | derivative_published | derivative_user_curated | user_tree | anecdote | ai_inference` (per confidence-tiers.md) |
| `title` | string | ✓ | Human-readable source title |
| `record_date` | date | ✓ | When the record was created (event date) |
| `record_date_confidence` | string | ✓ | `exact | estimated | range` |
| `language` | string | ✓ | `english | russian | yiddish | hebrew | ...` |
| `script` | string | ~ | `cyrillic_pre1918 | latin | hebrew_square | ...` |
| `location` | dict | ✓ | `empire`, `modern_country`, `region_at_time`, `modern_region`, `locality` |
| `provenance` | dict | ✓ | `obtained_from`, `obtained_date`, `collection_id`, `filing_reference`, `url`, `retrieved_url_date`, `translator` (if translated) |
| `original_image` | string | ~ | Path to scan (gitignored if living-person content) |
| `image_format` | string | ~ | `jpeg | tiff | pdf | ...` |
| `pages` | integer | ~ | Number of pages |
| `transcription` | dict | ~ | `ocr_tool`, `ocr_date`, `critique_tool`, `critique_date`, `confidence: high|medium|low`, `preserved_orthography: true|false` |
| `translation` | dict | ~ | `translator`, `translation_date`, `cultural_context_added: true|false`, `reverse_translation_check: true|false` |
| `disclosure` | string | ~ | AI-assisted flag |
| `related_people` | array | ~ | Links to `people/` dossiers |
| `related_hypotheses` | array | ~ | Links to `hypotheses/` |
| `citation_ee` | string | ✓ | Mills Evidence Explained format |

**Source-class specific sub-schemas:**
- `census_metadata` — enumeration district, page, household_id, enumeration_date
- `vital_record` — record_type, jurisdiction, certificate_number, registrant, informant, informant_relationship
- `manifest` — vessel, port_of_departure, port_of_arrival, arrival_date, manifest_line
- `dna` — platform, match_type, shared_cm, match_pseudonym (anonymized!), segment_count

**Markdown body:**
- Image
- Raw Transcription (original script, verbatim)
- English Translation (with cultural context notes)
- Cultural Context Notes (terminology, orthography, naming patterns)
- People Mentioned (extracted as a table)
- Confidence Notes (OCR/translation flagged uncertain passages)
- Citations Of This Source (back-references to person dossiers using it)

### hypothesis.md (`hypothesis-frontmatter-spec.md`, 149 lines)

**YAML keys (required / optional):**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | string | ✓ | Always `hypothesis` |
| `hypothesis_id` | string | ✓ | Stable slug |
| `title` | string | ✓ | The research question |
| `status` | string | ✓ | `proposed | investigating | supported | refuted | inconclusive | confirmed | rejected` |
| `proposed_date` | date | ✓ | When opened |
| `last_active` | date | ✓ | Last session touched it |
| `proposed_by` | string | ✓ | `nolan | ai | <name>` |
| `overall_tier` | string | ✓ | Evidence tier: `confirmed | strong | probable | weak | hypothesis | rejected` |
| `notion_id` | string or null | ~ | Notion Research page URL (if mirrored) |
| `primary_people` | array | ✓ | Subjects of the hypothesis |
| `peripheral_people` | array | ~ | Supporting cast |
| `disclosure` | string | ~ | AI-assisted flag |

**Markdown body:**
- `## Question` — refined statement
- `## Why This Matters` — stakes & significance
- `## Decomposition` — Type 1/2/3 per Steve Little framework (PORTABLE methodology)
- `## Evidence For` — sourced table
- `## Evidence Against` — sourced table
- `## Open Investigation Threads` — checklist of next steps
- `## AI-Assisted Analysis` — if any; must include disclosure footer
- `## Resolution Criteria` — what would promote to supported/confirmed/refuted/inconclusive
- `## Related Hypotheses` — cross-references
- `## Notion Cross-Reference` — sync note

### event.md (`event-frontmatter-spec.md`, 65 lines)

**Minimal YAML:**
```yaml
type: event
event_id: string (stable slug)
title: string
event_date: date
event_date_confidence: exact | estimated | range
location: {empire, modern_country, region, locality}
participants: [array of people/ references]
sources: [array of source/ references]
```

---

## 5. LLM Wiki Layer Rules

**Source:** `/Users/nolanfox/fox-genealogy/wiki/README.md` (114 lines)

**Portable in full:**

### Load-bearing rule

> **Wiki links DOWN to canonical dossier; dossier never trusts wiki upward.**

Every wiki page cites at least one canonical dossier using `[dossier:<vault-path>.md]`. No dossier may cite a wiki page as evidence. If wiki diverges from dossier, the dossier wins; wiki is re-derived.

### Disclosure-stamp footer (required on every page)

```markdown
---
*AI-generated narrative — <model> / <prompt-version> / <YYYY-MM-DD>. Citations live in linked dossiers. No fact in this page should be trusted without verifying against the dossier it cites.*
```

### Lint rules (8 checks; enforce with `scripts/lint_wiki.py`)

1. **Frontmatter check** — required YAML fields per template
2. **Dossier-link resolution** — `[dossier:...]` must exist
3. **Citation back-reference** — every dossier referenced must be listed in index.md or tagged `wiki: skip`
4. **Conflict-flag check** — if dossier has conflicts, wiki page must acknowledge in its Conflicts section
5. **Staleness check** — `last_synced:` within 90 days, OR `frozen: true`
6. **Length cap** — soft 400, hard 800 lines
7. **Disclosure-stamp check** — footer present and parseable
8. **Orphan check** — every page linked from index.md or another wiki page

### Directory layout

```
wiki/
├── README.md
├── index.md (catalog)
├── log.md (append-only operation log, format: `## [YYYY-MM-DD] <op> | <subject>`)
├── _templates/
│   ├── concept-page.md
│   ├── place-page.md
│   └── methodology-page.md
├── people/
├── places/
└── methodology/
```

### Inline link conventions

- **DOWN to dossier:** `[dossier:<vault-path>.md]` (parsed by lint script)
- **WITHIN wiki:** `[wiki:path/to/page.md]` or relative markdown
- **Out to docs:** standard markdown `[label](path)`

### Why Karpathy pattern (vs. RAG, Tana, vector DB)

At scale ≤1000 dossiers, Markdown vault + long-context Claude + index.md outperforms on citation transparency, debuggability, total cost. This is **portable reasoning**; use it for rhodes-wiki.

---

## 6. CRAIGen 5 Principles

**Source:** `/Users/nolanfox/fox-genealogy/CLAUDE.md` lines 11–18 (verbatim; no fox-genealogy-specific content)

These principles are **PORTABLE IN FULL**. Quote them directly in rhodes-wiki CLAUDE.md:

1. **Accuracy**: Never propose a relationship without a citation. Use tooling (e.g., `ged4py`) for kinship; never ask the LLM to compute relationships.

2. **Disclosure**: Every AI-generated narrative gets a footer stamp (model + prompt version + date).

3. **Privacy (audience-tiered)**: Internal research is unrestricted; public publishing is strict. The privacy gate fires at the **public-publish boundary** (paths like `blog/published/` or frontmatter `audience: public`), not at write-time.

4. **Education / Compliance**: Conflicting evidence is preserved, never silently resolved.

5. **Decompose first, prompt second**: Classify every question Type 1/2/3 (Steve Little framework). Never give Type 3 (open-ended) to the AI whole.

### Rhodes-specific adaptation note

The living-person rule (`docs/reference/living-person-rule.md`, 161 lines) applies fox-genealogy's audience-tiered gate. For rhodes-wiki, the **principle is portable; the implementation may differ based on Rhodes family privacy expectations and your intended publishing surface** (Notion, blog, etc.). The gate precedence rule (audience field + public-glob paths) is a general pattern you can reuse; just update the glob list and family names.

---

## 7. Naming Conventions

**Source:** `/Users/nolanfox/fox-genealogy/CLAUDE.md` lines 78–83

| Type | Pattern | Example |
|------|---------|---------|
| Person | `people/[surname]/[given-name]_[birth-year].md` | `people/Fox/Albert_1893.md` |
| Source | `sources/[year]_[type]_[short-description].md` | `sources/1894_minsk-revision_fox-family.md` |
| Hypothesis | `hypotheses/[short-slug].md` | `hypotheses/fox-heft-marriage-noim.md` |
| Event | `events/[short-slug].md` | (reserved; not yet used) |
| Session prompt | `docs/prompts/session-[NNN]-prompt.md` | `docs/prompts/session-001-prompt.md` |
| Session context | `docs/session_context/session-[NNN]-[phase]/` | `docs/session_context/session-003-multi-session-audit.md` |

**Portable pattern:** Yes. Reuse these conventions for rhodes-wiki; only change family surnames.

---

## 8. Tooling

**Source:** `/Users/nolanfox/fox-genealogy/pyproject.toml` (67 lines)

### Python dependencies (portable core)

```
python-gedcom>=1.0.0          # GEDCOM parsing (reused from rhodesli)
PyYAML>=6.0                   # YAML frontmatter
python-frontmatter>=1.1.0     # Frontmatter extraction
notion-client>=2.0.0          # Notion API batch sync
Pillow>=10.0.0                # Image processing
python-dotenv>=1.0.0          # .env files
click>=8.1.0                  # CLI tools in scripts/
```

### Dev dependencies (portable)

```
pytest>=7.4.0
pytest-xdist>=3.5.0
ruff>=0.1.0
mypy>=1.7.0
```

### Optional extras (deferred/specialized; reuse pattern)

```
[ocr]                         # FamilySearch, Transkribus, Gemini Vision
[dna]                         # pandas, pyarrow for DNA CSV workflow
```

### Scripts (location: `/Users/nolanfox/fox-genealogy/scripts/`)

**Portable (general-purpose):**
- `lint_wiki.py` — LLM wiki linter (enforce 8 rules above); no Fox-specific hardcoding
- `validate_person_dossier.py` — YAML + link resolution check (planned Session 002; reuse for rhodes-wiki)
- `validate_source_record.py` — source frontmatter validator (planned)
- `validate_hypothesis.py` — hypothesis frontmatter validator (planned)

**Fox-specific (SKIP for rhodes-wiki):**
- `scan_rhodesli_prompt.py` — checks cross-repo Session N scope (assumes `/Users/nolanfox/rhodesli` exists; rewrite for Rhodes)
- `check_new_gedcoms.py` — watches for GEDCOM updates in `~/Downloads` (rhodesli-specific)
- `list_active_sessions.py` — multi-session discovery (portable pattern; reuse)

**Not yet written but referenced:**
- `gedcom_lib.py` / `gedcom_cli.py` — GEDCOM parsing (planned GEDCOM_TOOLKIT.md)
- `dna_normalize.py` — DNA CSV unification (planned DNA_WORKFLOW.md)

---

## 9. Skills Inventory

**Source:** `/Users/nolanfox/fox-genealogy/.claude/skills/` directory listing + ROADMAP.md § Key Skills

Current state (2026-05-08):

| Skill | Type | Purpose | Portable? |
|-------|------|---------|-----------|
| `evidence-log/` | project-level | (Not yet documented; appears to be a stub) | ~ Unclear |
| `family-snapshot/` | project-level | Research summary artifact | ~ Explore |
| `prompt-parallelizer` | symlink to rhodesli | Analyze multi-phase prompts for parallelization | ✓ User-level (shared) |
| `research-plan/` | project-level | Decompose research question into Type 1/2/3 | ✓ Portable pattern |

**Planned (ROADMAP.md § Key Skills, Section 2):**

| Planned Skill | Purpose | Portable? |
|---------------|---------|-----------|
| `/decompose` | Type 1/2/3 question classifier | ✓ Yes |
| `/three-layer` | Mills Evidence Explained source/info/evidence | ✓ Yes |
| `/conflict-preserve` | Generate conflict block, never collapse | ✓ Yes |
| `/gps-proof` | Genealogical Proof Standard 5-element summary | ✓ Yes (with methodology tweaks) |
| `/disclosure-stamp` | Auto-footer on AI narratives | ✓ Yes |
| `/notion-sync` | Vault page → Notion publish (with privacy gate) | ~ Adapt (depends on Notion structure) |
| `/comms-triage` | Gmail + Ancestry threads → action queue | ~ Adapt (depends on comms workflow) |

**User-level skills (shared across fox-genealogy + rhodesli, location `~/.claude/skills/`):**
- Mentioned in ROADMAP.md § Shared Skills Migration (Phase J) — not yet migrated

**Implication for rhodes-wiki:**
- Start with portable skill list above
- Build project-level `/research-plan` first (decompose framework)
- Defer `/notion-sync` and `/comms-triage` until you know rhodes-wiki's publishing surface and comms workflow

---

## 10. What NOT to Copy

**Explicit fox-genealogy specifics that should NOT bleed into rhodes-wiki:**

1. **GEDCOM kinship resolution** — `ged4py` + `relationship_graph.py` tools assume Nolan's existing GEDCOM from rhodesli. Rhodes-wiki starts fresh; may or may not have a GEDCOM source.

2. **DNA workflow** — `docs/architecture/DNA_WORKFLOW.md`, `scripts/dna_normalize.py`, `/dna-analysis` skill — assumes Ancestry, GEDmatch, MyHeritage, FTDNA CSV exports specific to Fox DNA research. Skip unless Rhodes family also does DNA analysis.

3. **Translation pipeline** — `docs/architecture/TRANSLATION_WORKFLOW.md`, `/translate-source` skill, Transkribus/Gemini Vision setup — assumes Russian imperial records + Cyrillic orthography preservation. Reuse pattern only if Rhodes also has non-English-language sources.

4. **Notion publish pipeline** — `docs/research/notion-inventory.md`, `/notion-sync` skill — assumes a specific Notion structure ("Family History" hub + "Jewish Family History" + family wiki databases). Rhodes may use different publishing surface (blog, static site, etc.) or different Notion structure.

5. **Specific family memory + research threads** — Notion research pages, "Albert Fox and Dora Shane Made the Cut", Movsha Fuks Y-DNA cluster, Lebov-Heft connections, etc. These are Fox-specific projects; do not port.

6. **Cross-repo read bridge to rhodesli** — `.claude/settings.json` `additionalDirectories: /Users/nolanfox/rhodesli`, Session-start hooks `scan_rhodesli_prompt.py` + `check_new_gedcoms.py`. Adapt to Rhodes archive structure (if one exists) or remove entirely.

7. **Notion notion_id field mappings** — person frontmatter `notion_id` and hypothesis `notion_id` assume existing Notion Members DB and Research pages. Rewrite for Rhodes or remove if publishing to a different surface.

8. **rhodesli_identity_id + rhodesli_evidence** — person dossier fields specific to the rhodesli photo archive. Replace with equivalent archive/photo-evidence system for Rhodes (or remove).

9. **Specific archive references** — NHAB Minsk (Belarus), JewishGen databases, Ancestry searches, Russian imperial revision lists. Reuse as prior art / citation model, but don't hardcode paths.

10. **Lesson + memory files** — `tasks/lessons.md`, session-context feedback files (e.g., `feedback_context_utilization_monitoring.md`). These are Fox-family-specific research lessons; Rhodes may need its own.

---

## 11. Key Reference Docs to Adapt or Reuse

**From `/Users/nolanfox/fox-genealogy/docs/`:**

| File | Portable? | Action |
|------|-----------|--------|
| `docs/architecture/OVERVIEW.md` | ✓ | Adapt (rewrite for Rhodes 5-layer model) |
| `docs/architecture/AGENT_PATTERNS.md` | ✓ | Reuse (sub-agents, skills, hooks, autoresearch patterns) |
| `docs/architecture/CROSS_REPO.md` | ~ | Adapt (if Rhodes has a cross-repo; rewrite or skip) |
| `docs/architecture/COMMS_PIPELINE.md` | ~ | Adapt (Gmail + comms workflow) |
| `docs/architecture/SHARED_SKILLS.md` | ✓ | Reuse (HD-009 symlink pattern for user-level skills) |
| `docs/architecture/GEDCOM_TOOLKIT.md` | ~ | Adapt (if Rhodes uses GEDCOM; otherwise skip) |
| `docs/architecture/DNA_WORKFLOW.md` | ~ | Skip unless Rhodes does DNA research |
| `docs/architecture/TRANSLATION_WORKFLOW.md` | ~ | Skip unless Rhodes has non-English sources |
| `docs/research/genealogy-ai-best-practices.md` | ✓ | Reuse (methodological sourcing; no family-specific content) |
| `docs/research/ancestry-access-2026.md` | ~ | Reuse if Rhodes uses Ancestry; otherwise adapt |
| `docs/research/gedcom-tooling.md` | ~ | Reuse (GEDCOM decision tree); adapt if not using GEDCOM |
| `docs/research/notion-inventory.md` | ~ | Reuse as prior art; rewrite for Rhodes Notion structure |
| `docs/research/llm-wiki-knowledge-base-2026.md` | ✓ | Reuse (LLM wiki justification; methodology-pure) |
| `docs/reference/confidence-tiers.md` | ✓ | Reuse verbatim (Mills 3-Layer + 6-tier enum; portable) |
| `docs/reference/living-person-rule.md` | ✓ | Adapt (principle portable; implementation may differ) |
| `docs/reference/person-frontmatter-spec.md` | ✓ | Reuse (remove fox-specific fields like rhodesli_identity_id) |
| `docs/reference/source-frontmatter-spec.md` | ✓ | Reuse (DNA sub-schema portable if Rhodes does DNA) |
| `docs/reference/hypothesis-frontmatter-spec.md` | ✓ | Reuse verbatim (Steve Little Type 1/2/3 is portable) |
| `docs/reference/event-frontmatter-spec.md` | ✓ | Reuse (minimal; reserved but not yet used) |
| `docs/GENEALOGY_DECISIONS.md` | ~ | Reuse pattern (GD-NNN decision log); rewrite Rhodes decisions |
| `docs/HARNESS_DECISIONS.md` | ✓ | Reuse (HD-NNN Harness decision patterns) |

---

## 12. Bootstrap Checklist for rhodes-wiki

1. **Create directory scaffold** — `people/`, `sources/`, `hypotheses/`, `docs/`, `wiki/`, `scripts/`, `tasks/`, `.claude/`
2. **Write CLAUDE.md** — adapt template; reuse CRAIGen 5 + layered architecture + LLM wiki rules; blank Fox family references
3. **Write README.md** — elevator pitch + layout + quick-reference links
4. **Write ROADMAP.md** — phases A–J (adapt; DNA/Translation may differ for Rhodes)
5. **Create .claude/settings.json** — cross-repo additionalDirectories (if applicable); reuse allow/deny pattern; write Phase-0 advisory hooks
6. **Copy frontmatter specs** — `docs/reference/{person,source,hypothesis,event}-frontmatter-spec.md` (remove fox-genealogy field names; blank fields like `rhodesli_identity_id`)
7. **Copy confidence-tiers.md** — verbatim from `/Users/nolanfox/fox-genealogy/docs/reference/confidence-tiers.md`
8. **Adapt living-person-rule.md** — audience-tiered pattern portable; update family names + public-glob paths
9. **Create wiki/README.md** — copy `/Users/nolanfox/fox-genealogy/wiki/README.md` verbatim (methodology is pure)
10. **Create lint_wiki.py** — copy `/Users/nolanfox/fox-genealogy/scripts/lint_wiki.py` (no Fox-specific hardcoding)
11. **Create pyproject.toml** — use fox-genealogy version as template; remove optional extras until needed (dna, ocr)
12. **Create initial skills stubs** — `/research-plan/`, `/decompose/` (placeholder MDPs)
13. **Bootstrap `.claude/current_session.txt`** — track session number for this repo (start at Session 001)
14. **Write `tasks/todo.md` and `tasks/lessons.md`** — empty initially; grow with sessions

---

## Reference Path Verification

All paths cited above exist and are readable in `/Users/nolanfox/fox-genealogy/`:

- `/Users/nolanfox/fox-genealogy/CLAUDE.md` ✓
- `/Users/nolanfox/fox-genealogy/README.md` ✓
- `/Users/nolanfox/fox-genealogy/ROADMAP.md` ✓
- `/Users/nolanfox/fox-genealogy/.claude/settings.json` ✓
- `/Users/nolanfox/fox-genealogy/docs/reference/person-frontmatter-spec.md` ✓
- `/Users/nolanfox/fox-genealogy/docs/reference/source-frontmatter-spec.md` ✓
- `/Users/nolanfox/fox-genealogy/docs/reference/hypothesis-frontmatter-spec.md` ✓
- `/Users/nolanfox/fox-genealogy/docs/reference/confidence-tiers.md` ✓
- `/Users/nolanfox/fox-genealogy/docs/reference/living-person-rule.md` ✓
- `/Users/nolanfox/fox-genealogy/wiki/README.md` ✓
- `/Users/nolanfox/fox-genealogy/people/Fox/Albert_1893.md` ✓
- `/Users/nolanfox/fox-genealogy/people/Fox/Harry_1881.md` ✓
- `/Users/nolanfox/fox-genealogy/sources/1894_minsk-revision_fox-family.md` ✓
- `/Users/nolanfox/fox-genealogy/hypotheses/fox-heft-marriage-noim.md` ✓
- `/Users/nolanfox/fox-genealogy/pyproject.toml` ✓

---

**End of patterns brief.** This document is ready for the orchestrator to use as the input for the rhodes-wiki scaffold subagent(s).

