# Session 16 Plan
## Tracks: A (navigation), B (UX polish), C (ML kickoff)
## Test baseline: 1423 passing (ignoring e2e)
## Top 3 risks:
1. Photo lightbox navigation is the biggest feature — needs careful HTMX/keyboard integration
2. Triage filter bugs A2.1-A2.5 may already be partially fixed in v0.22.1 — need to verify before fixing
3. ML kickoff (Track C) may be blocked on missing API keys or Supabase schema access

## Track A: Navigation hardening
- A1: Photo lightbox nav (arrows, keyboard, mobile) — significant feature work
  - Photos section already has photoNavTo() and nav arrows — works when clicking photo cards
  - Need: collection-context nav, search-result-context nav, identity-context nav
  - Need: boundary indicators (first/last photo)
- A2: Verify triage filter bugs (v0.22.1 claims many fixed)
  - A2.1: Match mode + filter — appears implemented
  - A2.2: Up Next + filter — appears implemented
  - A2.3: Up Next links + filter — identity_card_mini passes triage_filter
  - A2.4: Promotion banners context — promotion_context populated in grouping
  - A2.5: Verify 3 promoted clusters — data validation
- A3: Navigation consistency audit

## Track B: UX polish
- B1: Clear stale pending uploads
- B2: Grammar/pluralization micro-polish
- B3: Landing page stats accuracy

## Track C: ML kickoff
- Task 1: Repository analysis (data audit, photo metadata, ML code audit)
- Task 2: rhodesli_ml/ directory structure
- Task 3: Date label generation script
- Task 4-5: Docs and backlog updates
