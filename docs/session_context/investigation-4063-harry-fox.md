# Investigation: Person 4063, Harry Fox, and Albert Fox

**Date:** 2026-03-17 (between Sessions 112 and 113)
**Investigator:** Nolan + Claude Code (ad-hoc, non-session)
**Trigger:** User suspected potential mismatch in Person 4063's cluster

---

## Summary

Person 4063 is an unidentified Fox family member with 3 beach photos from the Charles Fox Dayton Ohio Collection. The investigation confirmed Person 4063 is neither Albert Fox nor Harry Fox, and revealed that Harry Fox's own cluster has quality concerns (3 of 4 Dayton faces are closer to Albert than to Harry's ground truth). Several platform gaps were uncovered, most critically the absence of audit logging for identity mutations.

---

## Person 4063 Cluster

- **Identity ID:** f1fa51b2-323c-493c-8bdd-f3f99254eb72
- **State:** SKIPPED, version_id=5
- **Negative:** Albert Fox (explicitly rejected)
- **Faces:** 3, all from Charles Fox Dayton Ohio Collection (beach photos)

| Face | Photo | Description |
|------|-------|-------------|
| d9c2bb8d5fa6 | 01843 | Beach group with Albert Fox, Esther Burd Fox, unidentified woman |
| d8dabd3ca5e5 | 01612 | Close-up, Person 4063 arm-in-arm with woman (likely Esther Burd Fox), different day |
| fb4b65ccecfe | 01775 | Three men on beach: Roland Fox, Albert Fox (white shirt), Person 4063 (shirtless older man) |

**Internal distances:**
- P1-P2 = 0.89 (strong match)
- P1-P3 = 1.24 (weak)
- P2-P3 = 1.25 (weak but consistent)

---

## Cluster Provenance (GAP FOUND)

- Created March 10 during fox-charlie-001 batch ingest as 3 separate single-face identities
- Person 2480 merged into 4063 on March 17 at 05:00:00 UTC
- Person 2680 merged into 4063 on March 17 at 05:00:02 UTC
- **ZERO audit_log entries** for these merges
- **ZERO ml_proposals** linking these identities
- Cannot determine who initiated the merges (user or system)
- **Root cause:** `registry.merge_identities()` does not write audit_log entries

---

## Is Person 4063 Albert Fox?

**NO.** Photo 2 face is 0.89 from Photo 1 (same cluster) vs 1.24 from closest Albert face. The man arm-in-arm with Esther in Photo 2 is Person 4063, not Albert. 93rd percentile of Albert's intra-cluster distances.

## Is Person 4063 Harry Fox?

**NO.** From naturalization form (ground truth anchor):
- Nat form to 4063 faces: 1.35-1.40 (very far)
- Nat form to Harry cluster faces: 0.96-1.12 (much closer)

## Reciprocal Ranking Analysis

Person 4063's top 10 similar identities are all Fox family (Albert, Charles, Roland, Harry, Esther, Betty Capeluto, etc.). Albert Fox ranks higher than Person 4063 for 9/10 of these neighbors. Albert is 4063's #1 match at distance 0.806. This is family resemblance, not identity.

---

## Harry Fox Cluster Analysis (CRITICAL FINDING)

- **Identity ID:** d74cb556-6d44-4288-ade3-1cc8fa2b45a6
- **Faces:** 5

| Face | Photo | Notes |
|------|-------|-------|
| inbox_c6abb86ff55b | IMG_2570.jpeg | Naturalization form (GROUND TRUTH) |
| inbox_5168f0722ca8 | 01811 | Dayton |
| inbox_16430d6022c1 | 01632 | Dayton |
| inbox_94bbb9408f42 | 01810 | Dayton |
| inbox_c66961c76a6a | 02071 | Dayton |

The naturalization form photo was uploaded by nolanfox@gmail.com via web UI on March 17 at 04:24 UTC. The embedding was extracted on Railway and saved to production embeddings.npy, but **never synced back to local embeddings.npy**.

Local embeddings.npy: 2872 entries. Production: 2957 (85 more). This is Lesson 147 (local-production data divergence, 7th occurrence).

### Harry Fox Cluster Quality

Using production embeddings (downloaded via /api/sync/embeddings):

| Face | Dist to Nat Form | Dist to Albert | Closer to |
|------|-------------------|----------------|-----------|
| H1 (01811) | 0.960 | 0.977 | HARRY (barely, margin 0.017) |
| H2 (01632) | 0.996 | 0.981 | ALBERT |
| H3 (01810) | 1.118 | 1.000 | ALBERT |
| H4 (02071) | 1.103 | 1.042 | ALBERT |

**3 out of 4 Harry Dayton faces are closer to Albert Fox than to the naturalization form.** Only H1 is closer to Harry. The Harry Fox cluster needs human visual review.

---

## Platform Gaps Identified

| ID | Gap | Severity | Notes |
|----|-----|----------|-------|
| FB-AUDIT | No audit logging for merges, confirms, rejects, skips, renames, detaches | P0 | `registry.merge_identities()` is the root cause. Cannot trace who did what. |
| FB-EMBED-SYNC | Web upload embeddings exist only on production embeddings.npy | P1 | Local analysis is incomplete. PRD-051 Phase 3 not yet done. |
| FB-HOOK | Stop hook blocks non-session conversations | P2 | Needs escape hatch for ad-hoc investigations. |
| FB-CLUSTER-PROVENANCE | Cross-batch merges have no logged provenance | P1 | Need: who, why, distance for every merge. |

User explicitly said: *"With so many actions on the app we need good logging so I know what I did vs what was done automatically."*

---

## Decisions and Next Steps

1. **AUDIT-001 is now P0** -- every identity mutation needs an audit_log row with: action, entity_id, user_email (or "system"), old_value, new_value, metadata (route, distance, session)
2. **Session 113** should address PRD-051 Phases 2-3 (embeddings in Supabase)
3. **Harry Fox cluster** needs human visual review of H2, H3, H4 against naturalization form
4. **Person 4063** remains unidentified -- likely a Fox family member but not Harry and not Albert

---

## Breadcrumbs

- AUDIT-001: `ROADMAP.md` (Near-Term -- Infrastructure)
- Lesson 147: `tasks/lessons.md` (local-production data divergence)
- PRD-051: `docs/prds/` (embeddings in Supabase)
- Harry Fox identity: d74cb556-6d44-4288-ade3-1cc8fa2b45a6
- Person 4063 identity: f1fa51b2-323c-493c-8bdd-f3f99254eb72
