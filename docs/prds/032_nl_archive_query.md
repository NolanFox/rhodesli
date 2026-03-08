# PRD-032: Natural Language Archive Query

**Author:** Session 92
**Date:** 2026-03-07
**Status:** Draft
**Session:** 92 (PRD + query parsing prototype only)
**References:** PRODUCT-003 in ROADMAP.md

---

## Problem Statement

Users cannot ask natural language questions about the Rhodesli archive.
Current search is keyword-only (name matching). Community members want to ask:

- "Show me photos from weddings in the 1940s"
- "Who are the children of Nace Capeluto?"
- "Find photos taken in Rhodes before 1944"
- "Which people appear in the most photos?"

The archive contains rich structured data (identities, GEDCOM relationships,
photo metadata, Gemini-extracted descriptions, life events) that could answer
these queries — but there is no query interface beyond name search.

## Who This Is For

| Role | Need |
|------|------|
| **Community member** | Ask questions about family history in plain English |
| **Researcher** | Query across photos, people, and relationships |
| **Admin** | Find specific photos or people by description |

## Architecture

### Query Pipeline
```
User query → Intent parsing → Query plan → Supabase search → Response
              (LLM or rule)   (SQL/filter)  (Postgres)        (formatted)
```

### Intent Categories

| Intent | Example | Backend |
|--------|---------|---------|
| `person_search` | "Find Nace Capeluto" | Identity name search |
| `relationship` | "Who are the children of X?" | GEDCOM relationship graph |
| `photo_filter` | "Wedding photos from 1940s" | Photo metadata + Gemini labels |
| `aggregate` | "How many photos show Y?" | COUNT queries |
| `location` | "Photos from Rhodes" | photo_locations + Gemini data |
| `temporal` | "Photos before 1944" | Date estimates + Gemini data |

## User Flows

### Flow 1: Natural Language Search
1. User navigates to `/search` (or uses search bar)
2. User types a natural language question
3. System parses intent and extracts entities
4. System queries Supabase with structured filters
5. Results displayed as photo grid or person list

### Flow 2: Conversational Follow-up (Future)
1. User asks initial question, sees results
2. User refines: "Show me only the ones from New York"
3. System applies additional filter to previous results

## Acceptance Criteria

```
TEST 1: parse_query_intent exists and is importable
  - from rhodesli_ml.nl_query import parse_query_intent
  - Assert: function exists and is callable

TEST 2: Basic intent parsing
  - parse_query_intent("Find Nace Capeluto")
  - Assert: returns {"intent": "person_search", "entities": {"name": "Nace Capeluto"}}

TEST 3: Temporal intent parsing
  - parse_query_intent("Photos from the 1940s")
  - Assert: returns {"intent": "photo_filter", "filters": {"decade": "1940s"}}

TEST 4: Unknown intent fallback
  - parse_query_intent("asdfghjkl")
  - Assert: returns {"intent": "unknown", "raw_query": "asdfghjkl"}
```

## Technical Approach

### Phase 1: Rule-Based Parsing (This Session)
Pattern matching with regex for common query structures:
- Name mentions → `person_search`
- Date/decade references → `temporal` filter
- Location references → `location` filter
- Relationship words (child, parent, spouse) → `relationship`
- Aggregation words (how many, count) → `aggregate`

### Phase 2: LLM-Assisted Parsing (Future)
- Use Gemini to parse complex/ambiguous queries
- Structured output: intent + entities + filters
- Cost: ~$0.001 per query (Gemini Flash)

### Phase 3: Full Query Execution (Future)
- Wire parsed intents to Supabase queries
- Photo grid and person list rendering
- Conversation context for follow-ups

## Data Sources

| Source | Data Available | Access |
|--------|---------------|--------|
| `identities` (Supabase) | Names, states, face counts | Direct query |
| `photos` (Supabase) | Metadata, collections, dates | Direct query |
| `gedcom_individuals` | Birth/death dates, locations | Direct query |
| `gedcom_relationships` | Parent-child, spouse links | Graph traversal |
| `photo_locations` | Gemini-estimated locations | Direct query |
| `date_labels` | Gemini-estimated dates | Direct query |
| `gemini_analysis` | Full text descriptions | Full-text search |

## Technical Constraints

- **No LLM dependency in Phase 1** — rule-based parsing only
- **Supabase is source of truth** — all queries go to Postgres
- **Cost awareness** — LLM parsing (Phase 2) must log API calls per AD-152
- **Response time** — queries should complete in < 2s

## Out of Scope

- LLM-powered parsing (Phase 2+)
- Conversational context / follow-ups
- Voice input
- Multi-language support
- Semantic similarity search (requires pgvector)

## Priority Order

1. PRD document (this session)
2. `parse_query_intent()` with rule-based parsing (this session)
3. Supabase query execution (future)
4. UI integration (future)
5. LLM-assisted parsing (future)
