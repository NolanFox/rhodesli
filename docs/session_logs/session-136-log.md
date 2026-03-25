# Session 136 Log
Started: 2026-03-24
Mode: Interactive → Research → Planning
Predecessor: Session 135c (v0.99.46, 3746 tests)

## Baseline
- Tests: 3746 passed (36.80s)
- Branch: main (clean)
- Version: v0.99.46

## What Happened
Session started as interactive triage but pivoted immediately when Supabase
egress restriction was discovered (13.79 GB / 5.5 GB, service restricted).

### Phase 1: Diagnosis
- Community filtering failed open for Rhodes (showed Fox Family data)
- Root cause: Supabase 402 → `_get_community_identity_ids()` returned None for Rhodes
- Fix: fail closed for ALL communities

### Phase 2: Egress Analysis
- Research agent audited all 21 Supabase reads in codebase
- Found: 120s TTL SWR fires 24/7 from bot traffic, SELECT * on biggest tables
- Estimated: ~14 GB/month → ~3 GB/month after fixes
- Fixes: TTLs 120s→600s, selective columns, SWR bot guard

### Phase 3: Migration Research
- Explored: JSON fallback (rejected), new Supabase org (feasible), Convex (rejected)
- Codex CLI review: recommends Pro upgrade, don't migrate during outage
- Planning agent: migration feasible but abort if GEDCOM views fail
- User decision: pay $25 Pro upgrade tomorrow

### Phase 4: Overnight Planning
- Planned Session 137: 4 parallel tracks (main.py refactor, flaky tests, ML tests, TOOLS-005)
- All work independent of Supabase

## Commits
- c0deffa docs: session 136 setup
- d7b0585 fix: community filtering fails closed for ALL communities
- ee409de perf: reduce Supabase egress — TTLs 120s→600s, selective columns, SWR bot guard
- 84a4ba3 docs: OD-012 Supabase egress crisis
- af99d6b docs: session 136 feedback + migration research
- de48e10 docs: Codex CLI migration review
- 61b8042 docs: planning agent migration review
- 9fab537 docs: pre-migration row counts

## Feedback Items
- FB-001: Community filtering failed open (P0, FIXED)
- FB-002: Egress TTLs too aggressive (P1, FIXED)
- FB-003: AI subscription waste during downtime (P1, process)
- FB-004: Egress issue should have been caught in OD-011 (P2, process)
