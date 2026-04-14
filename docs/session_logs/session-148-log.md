# Session 148 Log — Interactive Fader Collection Fox Search
Started: 2026-04-13
Mode: Interactive (feedback-driven)

## Session Goal
Search the Sarah Fox Fader Collection (147 photos, 328 faces) for Fox family members — siblings, nieces/nephews of Albert Fox. Collect feedback on cross-collection search UX to inform future expansion.

## Phases
- [ ] Phase 0: Fix Person 82863849 erroneous rejection + harden
- [ ] Phase 1: Systematic Fader collection review for Fox identifications
- [ ] Phase 2: UX feedback on cross-collection search workflow
- [ ] Phase 3: Session close (assessment, docs, deploy)

## Feedback Log

### FB-001: Person 82863849 erroneously REJECTED (P0)
- **Severity:** P0
- **Context:** User saw Person 82863849 in Fader Collection "Dismissed" section. Never rejected it.
- **Root cause:** `_cleanup_orphaned_identities_for_upload()` auto-rejects ALL non-CONFIRMED identities whose faces come from a rejected upload batch. Bypasses registry.reject_identity(), no audit logging, no guard for triaged identities.
- **Secondary cause:** Session 147 "fix" wrote to local JSON only, never Supabase. Production reads Supabase.
- **Fix:** (1) Supabase direct restore + audit entry. (2) Guard: only INBOX auto-rejected. (3) Audit logging added. (4) 2 new tests.
- **Commit:** dc4f3415, e131e536

### FB-002: No Gemini date labels on Fader collection (P1)
- **Severity:** P1
- **Context:** All 147 Fader photos have zero date labels. Gemini batch estimation was never run on this collection (only on Fox Family/Albert+Esther). Without date estimates, temporal bracketing for identification is impossible in-app.
- **Fix needed:** Run Gemini batch estimation on Fader collection (same as Sessions 142-144b did for Fox Family).
- **BACKLOG:** BATCH-FADER-001

### FB-003: Cross-batch clustering missed Sherry matches (P1)
- **Severity:** P1
- **Context:** Sherry has 3 confirmed anchors but only 1 embedding exists in local embeddings.npy. The other 2 were uploaded via web pipeline and only exist on Railway volume. Cross-batch clustering compared Fader faces against existing collections but couldn't find Sherry because her local embedding coverage is incomplete. Result: 0 auto-clustered Sherry matches despite 21 candidates under distance 1.0.
- **Root cause:** Embeddings.npy on local and production are out of sync (Lesson 147). Cross-batch matching only uses local embeddings.
- **Fix needed:** Sync production embeddings to local, re-run cross-batch clustering for Fader collection.
- **BACKLOG:** CLUSTER-FADER-001

### FB-004: No "search by person across collections" feature (P2)
- **Severity:** P2
- **Context:** To find Sherry in the Fader collection, we had to write a custom script. There's no in-app way to say "show me faces in Collection X that look like Person Y." This is the core use case for expanding to new collections.
- **Fix needed:** Admin tool: "Search for [Person] in [Collection]" → ranked face results with distances. Maps to existing Find Similar but scoped to a specific collection.
- **BACKLOG:** TOOLS-007

## Phase 0: DONE
Fixed Person 82863849, hardened auto-rejection, lessons 168-170.

## Family Research — Josowitz/Fader/Fox

### Key People (from Ancestry screenshots)
- **Sherry Ann Fader** (1944-2018): Daughter of Abraham I. Fader (1901-1993) and Nadia Kubrin (1909-1988)
  - 1st marriage: 1965 to Ira Leon Josowitz (marriage license NYC, license #4285)
  - 2nd marriage: Jan 1976 to Paul DiPasquale (Lakewood Township, NJ, cert #09137)
  - Children: Erik Alan Josowitz, Michael H (from 2nd marriage?)
- **Ira Josowitz**: Son of David Josowitz (head, age 45) and Anna Josowitz (wife, age 42)
  - 1940 Census: Brighton 12th Street, house 3029, apt A1, Brooklyn
  - Siblings: Renee Josowitz (16), Greta Josowitz (12), Ira (6)
- **Abraham I. Fader** (Oki): 1901-1993 — Sarah Fox Fader's husband? Or son?
- **Nadia Kubrin**: 1909-1988 — Sherry's mother
- **Erik's great-grandparents (paternal)**: Harry H (Onhejm?) and Susan (S.D. Fox/Fader?)
- **Erik's great-grandparents (maternal)**: [need to confirm] — linked to Fox family

### Strategy
1. Start with confirmed Sherry photos → find her across Fader collection
2. Use wedding photos (1965, 1976) as temporal anchors
3. Grandparents Abraham (d.1993) and Nadia (d.1988) — bracket older photos
4. Work outward: identify Ira, siblings, parents, then Fox connections

## Findings

### Photo 291103717c75045f — 18-person group (table/dinner scene)
- **Sherry confirmed**: Person bb7d05ba-a3b5-4459-aaea-34299feeff15 is Sherry Ann Fader. User merging with confirmed Sherry identity (37611153-36d1-4f20-9535-d994e1893e13).
- **Ira Josowitz confirmed**: Person f1fa358b-f3c1-4347-83fb-71f9379abeff. First Josowitz identification in archive.
- This photo is a high-value anchor: 18 faces, likely a family gathering. Once Sherry and Ira are confirmed, other faces become identifiable via family context.

## Notes
- Interactive session — phases may shift based on user direction
- Session 147 deferred: browser verify evidence panel, rejected list UX
