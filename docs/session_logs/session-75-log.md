# Session 75 Log — Post-Gemini Cleanup + Tree Upgrade
Date: 2026-02-28

## Phase A: Data Integrity (Phases 1-2)
- Reverted 9,000+ lines of key-reordering noise in identities.json, annotations.json, gedcom_matches.json
- Preserved 5 real identity renames (Rachel, Rica, Solomon, Netanel, Regina) + 4 annotation updates
- Restored 19 UUID-based relationships wiped by Gemini session 74
- Merged with 1,000 GEDCOM-xref relationships: total 1,019 relationships

## Phase B: Date Parser + Tree Data (Phases 3-5)
- Created parse_gedcom_year() regex parser replacing broken [:4] slice
  - "21 SEP 1887" → "1887" (was "21 S")
  - "ABT 1900" → "~1900", "AFT 1930" → "aft. 1930", etc.
- Rewrote build_family_tree() for family-chart CardHtml format:
  - "first name"/"last name" split, gender, birthday, lifespan, avatar fields
  - Bidirectional relationships: 193 parents with 2+ children (siblings render)
  - 718 people total, 22 confirmed UUID identities with proper names

## Phase C: Tree Frontend (Phases 6-7)
- Rewrote family-tree.js to use CardHtml API (f3.createChart + CardHtmlWrapper)
- Light theme (slate-100) replaces dark SVG overlay
- Default to most-connected confirmed identity when no ?person= specified
- Loading state while tree initializes
- DOMContentLoaded wrapper prevents race conditions

## Phase D: Cleanup + Tests (Phases 4, 8)
- Deleted fake test_tree_rendering.py (standalone Playwright, not pytest)
- Fixed rebuild_full_graph.py: loads existing graph, accepts CLI arg
- 29 tests for parse_gedcom_year() + format_lifespan()
- 9 tests for build_family_tree() integration

## Phase E: xdist Fix (Phase 9)
- Root cause 1: routes.pop()/routes.insert() race condition
  - Fix: atomic _reorder_routes_atomic() using slice assignment
- Root cause 2: 10s timeout too tight for heavy imports under xdist
  - Fix: increased to 30s in Makefile
- Result: 2176 tests, 0 failures across 2 consecutive runs

## Phase F: Documentation (Phase 10)
- AD-175 through AD-178
- Session log, ROADMAP, SESSION_HISTORY updates

## Test Count
- Serial: 3153+ passed
- xdist: 2176 passed, 0 failed
- New tests added: 38

## Lessons Applied
- Lesson 38: Read code before assuming bugs exist
- Lesson 58: Test assertions match correct behavior
- Lesson 72: Context degradation — checkpoint after every phase
- Lesson 77: Verify destination before trimming
- Lesson 88: Monolithic app/main.py prevents parallel worktree execution
