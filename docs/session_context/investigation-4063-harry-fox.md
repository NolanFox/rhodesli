# Investigation: Person 4063, Harry Fox, and Albert Fox

**Date:** 2026-03-17 (between Sessions 112 and 113)
**Investigator:** Nolan + Claude Code (ad-hoc, non-session)
**Trigger:** User suspected potential mismatch in Person 4063's cluster

---

## Summary

Person 4063 is an unidentified Fox family member with 3 beach photos from the Charles Fox Dayton Ohio Collection. Initial investigation (Session 113) concluded 4063 was neither Albert nor Harry. **Revised analysis (post-Session 114):** Person 4063's cluster is likely contaminated — the beach close-up with Esther (P2) is probably Albert Fox (same Florida trip as definitive Albert+Esther bench photo), while the other two faces (P1, P3) appearing alongside Albert are likely Harry Fox. Confidence is moderate — the Fox siblings genuinely looked very similar. Harry Fox cluster quality concern (CLUSTER-QUALITY-001) resolved: Dayton photos ARE Harry, ML distances misleading due to sibling resemblance.

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

## Decisions and Next Steps (Original, Session 113)

1. **AUDIT-001 is now P0** -- every identity mutation needs an audit_log row — DONE (Session 113)
2. **Session 113** should address PRD-051 Phases 2-3 — Phase 2 DONE (Session 114)
3. ~~**Harry Fox cluster** needs human visual review~~ — RESOLVED (see post-Session 114 update)
4. ~~**Person 4063** remains unidentified~~ — RESOLVED (see post-Session 114 update)

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

The Session 113 finding (3/4 Harry Dayton faces closer to Albert) is **resolved as an expected biological limitation**, not a cluster quality issue. The Dayton photos ARE Harry — Nolan can tell by dating the photos via Charlie's age and comparing against known Albert photos from the same era. The ML distances are misleading because Harry and Albert genuinely looked nearly identical at certain life stages. The cluster is correct; the distance metric simply lacks discriminative power for this sibling pair.

### Disambiguation Methods Used (Human vs ML)

| Method | Source | What it resolved |
|--------|--------|-----------------|
| Couple body language | David Fox + Nolan | Beach photo with Esther = Albert (couple, not brother-in-law) |
| Same-trip inference | Nolan | Beach photo same Florida trip as Hialeah bench photo (definitive Albert+Esther) |
| Age-dating via Charlie | Nolan | Dayton photos datable by Charlie's age → compare against Albert at that era → doesn't match → Harry |
| Process of elimination | Nolan | If Albert is the other man in the white t-shirt, the shirtless man can't also be Albert |
| Family testimony | David Fox | "Resembles Poppy" confirms the siblings looked alike; "those are my grandparents" for bench photo |

**None of these methods are available to the embedding model.** The ML is measuring geometric face similarity, which genuinely cannot distinguish these siblings. This is not a bug to fix but a boundary to design around.

### ML Lessons

1. **Family resemblance is a real ML boundary.** Sibling pairs can be indistinguishable by embedding distance alone. This is a known limitation of face recognition, not a bug.
2. **Temporal context is the primary human disambiguation tool.** Dating a photo via the age of other people in it (Charlie's age → era → what Albert looked like then) is a reasoning chain ML cannot replicate with embeddings alone.
3. **Co-occurrence is high-signal.** If person A is confirmed in a photo, the other person cannot also be A. The system should make co-occurrence data more prominent during triage.
4. **Community knowledge provides irreplaceable ground truth.** David Fox's gut reaction ("Resembles Poppy") is high-signal even when ML distances are ambiguous. But note: David wouldn't know his uncle Harry well — his value was specifically about identifying Albert (his grandfather).
5. **"Close family" should be a distinct ML signal.** When embedding distance is ambiguous between confirmed relatives, surface this as "close family match" rather than forcing a binary same/different decision.

### Action Items
- [ ] Split Person 4063: P2 (beach close-up with Esther, photo `dbc16e6d973cc900`) → merge into Albert Fox; P1+P3 → keep as separate cluster (likely Harry Fox, pending further research)
- [x] CLUSTER-QUALITY-001: resolved — Dayton photos ARE Harry. ML distances misleading due to sibling resemblance, not cluster contamination.
- [ ] Tag Hialeah bench photo (`21e2734bdd25dc53`) faces as Albert Fox + Esther Burd Fox
- [ ] Consider: "close family match" indicator in the UI when embedding distance is ambiguous between confirmed relatives
- [ ] Consider: age-estimation context in triage UI — show estimated era for each photo alongside face crops to help disambiguation
- [ ] **CRITICAL UX GAP**: No way to split clusters in the app. Need PRD for cluster-splitting workflow. See memory: `feedback_cluster_splitting_ux.md`

---

## Gemini Face Comparison: Person 2491 vs Harry Fox (2026-03-18)

**Purpose:** Independent AI assessment of whether Person 2491 (b38fef24) is Harry Fox.
**Model:** gemini-2.5-pro | **Cost:** $0.0053 | **Tokens:** 2,335 | **Latency:** 27s
**Logged:** gemini_api_calls table, call_type="face_comparison"

### Photos Compared
- Photo A: Harry Fox naturalization form (IMG_2570.jpeg) — ground truth
- Photo B: Person 2491 photo 1 (01659) — standing with Albert Fox and Irving Fox
- Photo C: Person 2491 photo 2 (02068)

### Gemini Verdict: **VERY LIKELY SAME — HIGH CONFIDENCE**

### Key Findings

**Skeletal markers (all consistent):**
- Orbital shape: deep-set eyes, similar spacing, similarly prominent brow ridge
- Nasal bridge: broad and straight in all photos, nose tip shape consistent
- Jaw/chin: strong square jaw, prominent chin, differences attributable to age
- Cranial proportions: consistent head shape, high forehead
- **Ears: HIGHLY CONSISTENT — key matching feature.** Detached lobe and prominent antihelix fold visible in both Photo A and Photo B. Called out as strongest evidence.

**Age estimates:** Photo A ~45yo, Photos B/C ~35yo, ~10 year gap

**Sibling confusion assessment:** "The risk of confusion with brother Albert Fox is mitigated by powerful contextual evidence. Photo B shows Person 2491 standing next to Albert Fox. Since an individual cannot be in two places in a single photograph, Person 2491 cannot be Albert."

**Synthesis:** "The conclusion is based on two pillars of evidence: consistent unique morphology and definitive photo context. The skeletal markers, especially the highly distinctive left ear structure, are a strong match between Photo A and Photo B. Critically, the contextual evidence of Person 2491 being photographed with his lookalike brother Albert effectively rules out the possibility that he is Albert, making it almost certain that he is Harry Fox."

### ML vs Gemini Comparison

| Signal | ML (InsightFace) | Gemini |
|--------|-----------------|--------|
| 2491 → Harry nat form | 1.42 (far) | very_likely_same |
| 2491 → Albert centroid | 1.15 (closer to Albert) | "cannot be Albert — appears in same photo" |
| Method | Geometric embedding distance | Skeletal feature analysis + contextual reasoning |
| Key insight | Cannot distinguish siblings | Ear morphology + co-occurrence logic |

This is a compelling case for multi-signal fusion: InsightFace alone would reject this match, but Gemini's contextual reasoning + skeletal analysis correctly identifies it.

---

## Nolan's Final Decisions (2026-03-18)

### Person 4063 (f1fa51b2) — SPLIT REQUIRED
- **P2 (face inbox_d8dabd3ca5e5, beach close-up with Esther, photo dbc16e6d973cc900):** → Detach from 4063, merge into Albert Fox. Same Florida beach trip as definitive Albert+Esther Hialeah bench photo.
- **P1 (inbox_d9c2bb8d5fa6, photo 01843) + P3 (inbox_fb4b65ccecfe, photo 01775):** → Keep as separate cluster. Likely Harry Fox (appears alongside Albert in both photos), but needs further research before confirming.
- **Rationale:** 2/3 photos show 4063 alongside Albert (co-occurrence = not Albert). The 3rd photo (Esther close-up) is from the same Florida trip where Albert+Esther are definitively identified.
- **Confidence:** Moderate. The Fox siblings genuinely looked very similar; Nolan's identification is based on dating photos via Charlie's age + comparing against Albert photos from the same era.

### Person 2491 (b38fef24) — LIKELY HARRY FOX
- Family relative identified as Harry in photo with Albert and Irving
- Gemini confirms: very_likely_same, high confidence (ear morphology + co-occurrence)
- ML distance (1.42) is far, but Harry's within-person variation is already 0.96-1.12
- **Action:** Nolan to confirm in app, then merge into Harry Fox identity
- If confirmed, this gives Harry Fox a second anchor face (currently only naturalization form)

### Hialeah Photos
- Bench photo (`21e2734bdd25dc53`): Tag as Albert Fox + Esther Burd Fox (David Fox confirms)
- Beach photo (`dbc16e6d973cc900`): Part of same Florida trip

### UX Gap Discovered
- **No cluster-splitting UI exists.** Cannot break up a contaminated cluster (e.g., Person 4063 with faces of both Albert and Harry). Must use detach + manual reassignment. This was a core Google Photos pain point that motivated building Rhodesli. Needs PRD.

## Breadcrumbs

- AUDIT-001: `ROADMAP.md` (Near-Term -- Infrastructure) — DONE (Session 113)
- PRD-051: `docs/prds/` — Phases 1+2+4 DONE (Sessions 112-114)
- CLUSTER-QUALITY-001: `docs/BACKLOG.md` — RESOLVED
- Harry Fox identity: d74cb556-6d44-4288-ade3-1cc8fa2b45a6
- Person 4063 identity: f1fa51b2-323c-493c-8bdd-f3f99254eb72
- Person 2491 identity: b38fef24-858d-4b5f-95c0-c52c09a111f0
- Albert Fox identity: 85546ebf-75b9-4971-a9d4-b2ce2271bc19
- David Fox conversation: 2026-03-17, iMessage
- Gemini API call: gemini_api_calls table, 2026-03-18, call_type="face_comparison"
- Hialeah bench photo: `21e2734bdd25dc53`
- Beach photo (same trip): `dbc16e6d973cc900`
- Person 2491 photo with Albert+Irving: `91b6f6b296e93a60`
- Cluster splitting UX gap: memory `feedback_cluster_splitting_ux.md`
- Comparison workflow feedback: memory `feedback_comparison_workflow.md`
