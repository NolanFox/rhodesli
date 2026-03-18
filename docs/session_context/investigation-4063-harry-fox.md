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

The naturalization form photo was uploaded by nolanfox@gmail.com via web UI on March 17 at 04:24 UTC. The embedding was extracted on Railway and saved to production embeddings.npy. **Synced to local in Session 113 Phase 0** (2957 entries, previously 2872).

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

## Verified Analysis with Production Embeddings

**Date:** 2026-03-17 (Session 113, Phase 2)
**Embeddings:** 2957 entries (synced from production), all 8 target faces found.
**Albert Fox centroid:** computed from 160 confirmed anchor embeddings.

### Naturalization Form to Harry Dayton Faces

| Face | Dist to Nat Form | Dist to Albert Centroid | Closer to | Margin |
|------|-------------------|------------------------|-----------|--------|
| H1 (01811) | 0.960 | 0.977 | HARRY | 0.017 |
| H2 (01632) | 0.996 | 0.981 | ALBERT | 0.015 |
| H3 (01810) | 1.118 | 1.000 | ALBERT | 0.118 |
| H4 (02071) | 1.103 | 1.042 | ALBERT | 0.061 |

**Result: 3 of 4 Harry Dayton faces are closer to Albert Fox than to the naturalization form.** Only H1 is closer to Harry, and by a margin of just 0.017. This confirms the pre-sync finding exactly.

### Naturalization Form to Person 4063 Faces

| Face | Dist to Nat Form | Dist to Albert Centroid |
|------|-------------------|------------------------|
| P1 (01843) | 1.395 | 1.106 |
| P2 (01612) | 1.346 | 1.145 |
| P3 (01775) | 1.382 | 0.844 |

Person 4063 is far from Harry (1.35-1.40) and moderately far from Albert (0.84-1.15). P3 (01775) is notably close to Albert at 0.844 but was explicitly rejected during triage. This confirms Person 4063 is neither Harry nor Albert.

### Full 8x8 Distance Matrix

```
                 Nat Form  H1(01811)  H2(01632)  H3(01810)  H4(02071)  P1(01843)  P2(01612)  P3(01775)
Nat Form            0.000      0.960      0.996      1.118      1.103      1.395      1.346      1.382
H1 (01811)          0.960      0.000      0.693      0.715      1.047      1.318      1.362      1.236
H2 (01632)          0.996      0.693      0.000      0.901      1.108      1.341      1.393      1.275
H3 (01810)          1.118      0.715      0.901      0.000      1.097      1.269      1.303      1.213
H4 (02071)          1.103      1.047      1.108      1.097      0.000      1.261      1.370      1.318
P1 (01843)          1.395      1.318      1.341      1.269      1.261      0.000      0.889      1.241
P2 (01612)          1.346      1.362      1.393      1.303      1.370      0.889      0.000      1.252
P3 (01775)          1.382      1.236      1.275      1.213      1.318      1.241      1.252      0.000
```

### Key Observations

1. **Harry cluster internal cohesion is good**: H1-H2 (0.693), H1-H3 (0.715) are tight. H4 is the outlier at 1.05-1.11 from H1-H3.
2. **Person 4063 internal cohesion**: P1-P2 (0.889) is tight, but P1-P3 (1.241) and P2-P3 (1.252) are weak — this is a marginal cluster.
3. **Harry and 4063 are distinct clusters**: minimum cross-cluster distance is 1.213 (H3-P3), well above same-person thresholds.
4. **Harry cluster quality concern confirmed**: 3/4 faces closer to Albert than to ground truth anchor. H2 margin is razor-thin (0.015), but H3 (0.118) and H4 (0.061) are clearly more Albert-like.

### Conclusion

The pre-sync analysis is **confirmed exactly** with the full production embedding set. The Harry Fox cluster warrants human visual review of H2, H3, and H4 against the naturalization form. These three Dayton photos may depict Albert Fox, not Harry. This is logged as a data quality concern in BACKLOG.md (CLUSTER-QUALITY-001).

---

## Update: Revised Analysis (2026-03-17, post-Session 114)

**New evidence:** David Fox conversation + contextual photo analysis by Nolan.

### David Fox's Input (Albert's grandson)
- Shown Harry Fox's naturalization form: "Resembles Poppy [Albert]"
- Shown beach photo with 4063 + Esther: "Those are my grandparents, Albert and Esther"
- Rationale: "They look like a couple, not a brother and sister in law"
- Confirmed: the Fox siblings genuinely looked nearly identical — "enough that it confuses ML models"

### Nolan's Revised Reasoning
1. **Photo `21e2734bdd25dc53`** (Hialeah bench): definitively Albert + Esther. David confirms. Couple body language. Hialeah, FL location.
2. **Photo `dbc16e6d973cc900`** (beach): same Florida beach trip as the Hialeah bench photo. Same era, consistent clothing/age.
3. **Therefore:** Person 4063 in the beach photo with Esther = **Albert** (he's with his wife on the same trip).
4. **The other two 4063 photos** (01843, 01775) show a man in a white t-shirt alongside Albert — that man **cannot** be Albert. Given Fox family context and resemblance, likely **Harry**.

### Revised Conclusion: Person 4063 Is Likely TWO People

The 4063 cluster is a **contaminated cluster** containing faces of both Albert and Harry:
- **P2 (01612, beach close-up with Esther)** = Albert Fox (same trip as definitive Albert+Esther bench photo)
- **P1 (01843) and P3 (01775)** = likely Harry Fox (appears alongside Albert in white t-shirt)

This explains the weak internal distances: P1-P3 is 1.24 and P2-P3 is 1.25 — these are cross-person distances, not same-person variation.

### What This Means for CLUSTER-QUALITY-001

The Session 113 finding (3/4 Harry Dayton faces closer to Albert) now has a plausible explanation: **some of those faces may actually BE Albert, not Harry.** The ML was arguably correct — the cluster was contaminated with both brothers. The biological resemblance between Albert and Harry Fox at similar ages is genuine and confirmed by David Fox. This is not an ML failure but a fundamental limitation of appearance-only face matching for closely related people.

### ML Lessons

1. **Family resemblance is a real ML boundary.** Father/son and sibling pairs can be indistinguishable by embedding distance alone. This is a known limitation of face recognition (not a bug).
2. **Contextual reasoning breaks ties that ML cannot.** The identification here required: same-trip inference, couple vs sibling body language, clothing matching across photos, process of elimination (if A is in the photo, the other person isn't A).
3. **Contaminated clusters are expected for close relatives.** The system should surface "close family" as a distinct ML signal, not just "same person."
4. **David Fox's confirmation method:** gut reaction ("Resembles Poppy") = high-signal even when ML distances are ambiguous. Community knowledge is irreplaceable ground truth.

### Action Items
- [ ] Split Person 4063: P2 → merge into Albert Fox; P1+P3 → new identity (likely Harry Fox, pending further confirmation)
- [ ] Update CLUSTER-QUALITY-001: resolved — contaminated cluster, not ML quality issue
- [ ] Consider: "close family match" indicator in the UI when embedding distance is ambiguous between confirmed relatives

## Breadcrumbs

- AUDIT-001: `ROADMAP.md` (Near-Term -- Infrastructure)
- Lesson 147: `tasks/lessons.md` (local-production data divergence)
- PRD-051: `docs/prds/` (embeddings in Supabase)
- Harry Fox identity: d74cb556-6d44-4288-ade3-1cc8fa2b45a6
- Person 4063 identity: f1fa51b2-323c-493c-8bdd-f3f99254eb72
- David Fox conversation: 2026-03-17, iMessage (screenshots in session context)
- Hialeah bench photo: `21e2734bdd25dc53`
- Beach photo (same trip): `dbc16e6d973cc900`
