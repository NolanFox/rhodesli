# PRD-035: GEDCOM Multi-Tree Architecture

**Parent:** [PRD-035](../035_multi_community_platform.md)

## Current State (confirmed working post-DATA-007)

- `scripts/import_gedcom_version.py` — versioned import with `--community` flag
- `gedcom_versions` table with `community_id` — multi-tree ready
- Web UI at `/admin/gedcom` — upload + diff preview + version history
- 21,809 individuals in Supabase (Nolan's Ancestry tree, covers both Fox and Capeluto)

## Multi-Tree Model

```
Platform GEDCOM Architecture:
  ├── Tree 1: "Nolan's Ancestry Tree" (community: rhodes + fox-family)
  │     ├── Version 1: Initial import (21,809 individuals)
  │     ├── Version 2: Updated 2026-02
  │     └── Version 3: Current
  ├── Tree 2: "Wife's Family Tree" (community: [wife's-family])
  │     └── Version 1: Initial import
  └── Tree 3: "Uploaded by cousin" (community: fox-family)
        └── Version 1: Initial import
```

**Primary tree:** Used for tree visualization. One primary per community.
**Secondary trees:** All GEDCOM data from secondary trees enriches Gemini API calls
(date estimation, location estimation, relationship context).

## Cross-Tree Identity Linking

A real person can appear in multiple GEDCOM trees:
```
Roland Fox (identity UUID: abc-123)
  ├── GEDCOM link: Tree 1, XREF @I1234@ (primary)
  ├── GEDCOM link: Tree 3, XREF @I567@ (secondary)
  └── All GEDCOM data from both trees feeds Gemini enrichment
```

## Implementation (Phase 3)

| Task | Description |
|------|-------------|
| Multi-GEDCOM assignment | Assign GEDCOM trees to communities, primary/secondary |
| GEDCOM selection in admin UI | Dropdown to pick community when importing GEDCOM |
| Primary/secondary tree display | Tree viz uses primary; Gemini uses all |
| Multiple GEDCOM identities per person | Link person to entries in different trees |
| Context capture post-upload | Structured form for adding context to uploaded photos |
| Link to TOOLS-004 chatbot | Context capture as chatbot use case (future) |

## Pinecone / Vector DB Decision

**Use pgvector (Supabase built-in), not Pinecone.**
- pgvector evaluation doc already written (deferred until 5K+ embeddings)
- For TOOLS-004 chatbot: embed text chunks (photo descriptions, GEDCOM context,
  user-provided NL context) with embedding model, query with cosine similarity
- Same Supabase instance, no new infrastructure
- Activate when chatbot work begins

## Key Files

| File | Purpose |
|------|---------|
| `scripts/import_gedcom_version.py` | CLI import (versioned, multi-community) |
| `scripts/supabase_migration_002_gedcom_versioning.sql` | Schema |
| `app/admin_routes.py` lines 2248+ | `/admin/gedcom` web UI |
| `tests/test_gedcom_versioning.py` | Import logic tests (20+) |
| AD-163 | GEDCOM temporal versioning design |
| AD-206 | GlobalPersonID schema |
