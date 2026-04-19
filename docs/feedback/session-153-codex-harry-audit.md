---
**Auditor**: Codex CLI v0.121.0
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: Harry Fox anchor misassignment thesis + Isaackovitz hypothesis + left/right men verification
**Date**: 2026-04-18
**Constraint hit**: Supabase read failed with DNS resolution error; verified against `data/embeddings.npy` + local identity cache instead.
---

# Codex Harry Audit — Triangulation Point #4

## P0 — Repair Harry Fox anchors F/G

**Verdict:** Evidence is strong enough to detach F/G from Harry Fox.

**Reproduced matrix:**
- F↔G = `0.629` → same-event / same-person
- F/G → Harry (Harshel) anchors A-E = `1.356-1.432` → different-person territory
- The age argument is weak alone; the embedding split + same-clothing/same-event pairing is strong

**Confidence:**
- **0.88** for detaching from Harry Fox (embedding evidence alone)
- **0.95** if the user's GEDCOM/Ancestry claim that center = Harry Isaackovitz is accepted

**Banquet anchor E:** Do NOT resolve yet — hold for user visual review.

---

## P1 — Test 3009 = Bessie Fox, center = Harry Isaackovitz

**Status:** Plausible, not ML-confirmed.

- 3009 → Bessie distances: `1.275` to 02136 beach face, `1.359` to FB face (both OLD-Bessie anchors)
- The two Bessie anchors are internally coherent at `1.081` but are age-60+
- The spouse-pair context (Harry Isaackovitz = Bessie's husband) makes 3009=Bessie much stronger than embeddings alone

**Testing protocol:**
1. Re-query `gedcom_individuals` for `@I132506612777@` (spouse/marriage/residence)
2. Find a 1910s Bessie/Harry portrait (Ancestry)
3. Link Harry Isaackovitz only after source evidence
4. Re-run visual comparison with exact face boxes

---

## P1 — Verify left/right men independently

**Pair-across-frames first:** All three seated men recur across 01659/02068:
- Center: 0.629
- Left: 0.671
- Right: 0.627

**Right man: strong Albert support**
- right-02068 → Albert min `0.876`
- Local merge chain to Albert supports this
- Verdict: Albert Fox CONFIRMED

**Left man: NOT verified**
- No confirmed Irving Fox anchor was available in local cache
- Need Supabase/Ancestry Irving anchors or labeled photos
- Compare the paired left faces to known anchors without assuming center identity

---

## P2 — Other hypotheses

- **3009** could be: Detroit social acquaintance, Isaackovitz-side relative, Bessie/Fox sister or sister-in-law, or Albert/Irving social contact
- **3007** remains more likely non-Fox/unknown; her top neighborhood is not confirmed Fox
- **Rose Scheckzner** only revives if center is Harry Fox (current evidence argues against)

---

## P3 — Hygiene for Session 154 repair

1. Snapshot Harry Fox identity row before mutation
2. **Verify exact F face ID:** Codex found `1fea75...` but Session 153 breakthrough note said `2bc31...` — discrepancy must be resolved before mutation
3. Attach repair evidence to audit_log entries

---

## Triangulation summary (all 4 sources now agree)

| Source | H2 (misassignment) | H3 (Harry Isaackovitz) |
|---|---|---|
| Local ML (Agent a72bfa1b + Codex) | **CONFIRMED** (d=1.431 cross-cluster) | Age fits, embeddings neutral |
| User Ancestry research | — | **CONFIRMED** (tree 162873127 person 132506612777) |
| Gemini 3.1 Pro vision | **CONFIRMED** high confidence (bone structure + Harshel's blond/blue vs dark/dark) | Profile-consistent, needs reference |
| Codex independent audit | **CONFIRMED** 0.88 | Plausible, 0.95 with Ancestry |

Zero contradictions. Session 154 Phase 1 repair is justified.

**Tokens used:** 155,774
