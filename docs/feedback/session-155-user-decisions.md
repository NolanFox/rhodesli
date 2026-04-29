# Session 155 — User Decisions Required (Track 4)

**Status**: AWAITING YOUR INPUT
**Two decisions** are gated on your explicit authorization. Neither will execute without your verbatim response. Default for both = STOP.

---

## Decision 1 — Harry Fox anchor repair (HARRY-REPAIR-001)

### State after Session 154

The "Harry Fox" identity in the registry (`d74cb556-6d44-4288-ade3-1cc8fa2b45a6`) currently claims 7 anchors, including 2 face IDs that Track B (Session 154) confirmed are NOT Harshel Fox:

- `inbox_1fea75ce2caf` = face F (photo 01659 Belle Isle, center young man)
- `inbox_e507a54f204a` = face G (photo 02068 Detroit, center seated young man)

The 6-gate decision matrix from `docs/feedback/session-153b-harry-repair-decision.md`:

| Gate | Status |
|---|---|
| 1. Bessie hypothesis ≥ GOOD (~70%+) | PARTIAL — POSSIBLE-GOOD ~55% (Session 154 B2 strengthened from ~40%) |
| 2. Face-ID resolved | ✅ MET (Session 154 B1) |
| 3. Belle Isle archival citation | ✅ MET (Session 154 C1, LoC LC-DIG-det-4a17798) |
| 4. 1910s reference photo for Bessie | ❌ NOT MET (no Ancestry photo found yet) |
| 5. Third Belle Isle frame | ❌ NOT MET (no third frame surfaced) |
| 6. Bessie GOOD threshold met | ❌ NOT MET (still POSSIBLE) |

### Three options

**(a) Wait for stronger reference data.** Search Ancestry tree 162873127 for a 1910s Bessie photo, run embedding distance against face F/G's neighbor 3009. This is the strongest possible signal but requires user-side Ancestry browsing. ~1 hour of your time on Ancestry. Recommended if you want to AVOID the over-claim risk Session 153b retracted.

**(b) Search for a third Belle Isle frame.** PRD-061 (event clustering) is the home for this work. Search the Charlie Fox collection + Ancestry + Detroit Public Library digital collections for additional Belle Isle Conservatory photos that could triangulate. ~2-4 hours. Defer if you'd rather not invest the time on a single repair.

**(c) Ship the conservative replacement label** "Belle Isle Conservatory Young Man c.1917-1918". Reversible if better evidence later surfaces. Gates 4-6 are not met but the label avoids any positive identification claim — it just describes what we DO know (location + date range). The Belle Isle citation (Gate 3) and face-ID resolution (Gate 2) provide enough grounding for the descriptive label.

### If you authorize (c), the execution plan is:

1. Snapshot Harry Fox identity to `backups/session-155/harry-fox-before-{UTC}.json`
2. Draft an `audit_log` row for the move
3. Detach `inbox_1fea75ce2caf` + `inbox_e507a54f204a` from Harry Fox identity (anchors go from 7 → 5)
4. Create new INBOX identity "Belle Isle Conservatory Young Man c.1917-1918" with those 2 faces
5. Link the new identity to the GEDCOM Harry Isaackovitz record (`@I132506612777@`) as a *candidate*, NOT confirmed
6. Run structural tests (`tests/test_data_integrity.py`)
7. Browser-verify Harry Fox person page (now 5 anchors) + new identity page (READ-ONLY)
8. Commit + push

### Your input

Reply with **(a)**, **(b)**, **(c)**, or **defer**. If (c), copy-paste this verbatim authorization (or write your own, but it must explicitly authorize the (c) execution path):

> AUTHORIZE Track 4A option (c): ship "Belle Isle Conservatory Young Man c.1917-1918" replacement identity. Detach `inbox_1fea75ce2caf` + `inbox_e507a54f204a` from `d74cb556-6d44-4288-ade3-1cc8fa2b45a6`. Create new INBOX identity. Link to GEDCOM `@I132506612777@` as candidate (NOT confirmed). Snapshot to `backups/session-155/harry-fox-before-<UTC>.json` first.

---

## Decision 2 — Track E E2 Supabase prune execution (SUPABASE-PRUNE-EXEC-001)

### State after Session 154

Plan exists at commit `1e0b0fbc`: `docs/feedback/session-154-supabase-prune-plan.md`.

- Current Supabase DB size: **2.22 GB**
- Free-tier ceiling: **1.1 GB** (grace period ends **2026-05-29** — ~30 days)
- Plan reaches **~840 MB final state** (well under ceiling, with 260 MB headroom)

The plan has full per-step DELETE predicates, snapshot output paths, and VACUUM FULL list. Tripwire script: `scripts/session154_supabase_prune.py` (`--execute` requires `SESSION154_PRUNE_AUTH=approved-<plan-commit>` env var).

### Why this requires your verbatim authorization

Lessons 155, 156: data repair scripts must snapshot before EACH step, with PK + checksum + restore command embedded. The Codex P1 audit (Session 154 prep) added an additional protocol: **the user authorization message must explicitly name** every irreversible step, not just "approved":

1. The plan commit hash (`1e0b0fbc`)
2. Every table touched (verbatim list — read the plan)
3. Every DELETE predicate (verbatim from plan)
4. Every snapshot output path (`backups/session-155/<table>_pre-prune-<UTC>.jsonl.gz`)
5. The full VACUUM FULL list

"Approved" alone does NOT meet this protocol.

### Three options

**(execute)** Provide the verbatim authorization message. Track 4 will run the prune step-by-step, snapshot-then-mutate-then-verify per step. After each step, re-runs the size query and appends to `docs/feedback/session-155-supabase-size-progress.json`. Final state ≤ 1.1 GB mandatory, ≤ 900 MB target.

**(defer to PRD-063)** Wait for Track 1's PRD-063 redesign to land (it ships in this session). Then execute Session 156 with a single migration that prunes + redesigns at once. **Risk**: the 2026-05-29 grace period may lapse if 156 doesn't run before then. Supabase will start applying restrictions.

**(upgrade to Pro plan)** $25/mo bypasses the free-tier limit. Already considered + rejected per OD-013 (user prefers free-tier sustainability), but it's an option if you want to buy time.

### Your input

Reply with **(execute)**, **(defer)**, **(upgrade)**, or **defer-and-decide-later**. If (execute), copy-paste a full verbatim authorization following the 5-item protocol above. The plan is at `docs/feedback/session-154-supabase-prune-plan.md` (commit `1e0b0fbc`) — read it for the table list / predicates / snapshot paths.

---

## Default behavior if no response

Both decisions stay GATED. Track 4A surfacing only — Harry Fox identity unchanged. Track 4B surfacing only — Supabase prune not executed. Tracks 1, 2, 3 land independently regardless. Closeout proceeds.

The grace period reality is: if Decision 2 isn't resolved by ~2026-05-22 (1 week before deadline), Session 156+ should plan a contingency — even option (upgrade) takes a few days to take effect.
