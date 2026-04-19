# Session 153 — What We've Done (plain-English trail)

**Purpose:** A single readable summary of Session 153 work, to replace the 14-file doc trail. Updated 2026-04-18 after user feedback on over-claiming.

---

## The original ask (your first big prompt in this session)

You asked us to continue Session 152's 1918 Detroit Fox photo identification, focusing on 3 unknown faces (3007, 3009, 3010). Over the session you added layers:

1. **Date correction:** photo is pre-WWI-enlistment (~1915-1917), not 1918
2. **3010 is background** — mark as skipped
3. **3007 theory:** user assumed 3007 = Sadie Fox; later: 3007 looks most like Person 3103 (1930s beach photo)
4. **3009 theory:** user has **always assumed 3009 = Bessie Fox** ("I think comparing against the two known Bessie photos there is a strong case for a young Bessie there")
5. **IF 3009 = Bessie THEN center man MIGHT be Harry Isaackovitz** (Bessie's 2nd husband) — presented AS A HYPOTHESIS
6. Validate Harry Fox vs NOT-Harry-Fox in 3 models (Codex, Gemini, Claude Chrome multimodal)
7. Build photo-event-clustering feature research
8. Fix UX bug where you mis-clicked the skip button on Person 2510
9. Run the rate-limit-blocked scripts (shadow-eval + embedding baselines)

---

## What's CONFIRMED (multi-source triangulated)

### CONFIRMED-1: Photo location is Detroit / Belle Isle Conservatory
- User established this in Session 144 via Gemini chat (retrieved transcript from gemini.google.com/app/eec3d67bd7d228ff)
- Our production Gemini auto-run got it wrong — said NYC
- **Why**: our 33K-char shotgun prompt dumped raw GEDCOM without biographical narrative, no reference portrait, no subject-weighted geography
- Fix designed (3-round scaffold), not deployed — needs shadow-eval on ≥10 photos first

### CONFIRMED-2: The Harry Fox identity has 2 anchors that are NOT Harry Fox (Harshel)
Evidence strength per source:
- Local embeddings: F↔G = 0.629 (same person as each other); F/G → Harshel anchors A-E = 1.36-1.43 (different person)
- Gemini 3.1 Pro: bone structure rejects Harshel — protruding ears on mystery man, flat on Harshel. Harshel's naturalization records him as **blond/blue eyed**; mystery man is **dark hair, dark eyes**
- Codex CLI: reproduced the matrix independently, confidence 0.88
- User: has not contradicted any of this

**This conclusion is solid: the center man in the Detroit photo is NOT Harry Fox (Harshel).**

### CONFIRMED-3: The two conservatory photos (02068 + 01659 + 91b6f6b296e93a60) are the SAME event
- F↔G embedding distance 0.629 (same person across frames)
- Gemini 3.1 Pro: "100% confidence, different frames of same event, identical outfits"
- Same three seated men, same two standing women, same conservatory

### CONFIRMED-4: Albert Fox IS seated right in the Detroit photo
- Embedding distance right-man → Albert min = 0.876 (strong)
- Existing merge history attaches the face to Albert's identity
- Gemini independently identified far-right seated man as Albert Fox
- Not disputed

### CONFIRMED-5: Person 3010 is a background passerby
- Partial face, bbox has negative y1 (crops off frame)
- User confirmed "clearly in the background and not a part of the group"
- Marked SKIPPED with backup snapshot (reversible)

---

## What's HYPOTHESIS (NOT confirmed, Claude over-claimed earlier)

### HYPOTHESIS-A: Center man IS Harry Isaackovitz
- **Ancestry only tells us Harry Isaackovitz existed** (b.1881, Bessie's husband, married 1911, tree 162873127 person 132506612777)
- **NO reference photo of Harry Isaackovitz exists** in our system or (per user) the Ancestry tree
- **Therefore NO model can POSITIVELY identify him** — they can only confirm "not Harshel"
- Claude's earlier "triangulated" claim conflated absence-of-contradiction with positive-confirmation. That was wrong.
- **What's actually true:** the center man is someone matching Harry Isaackovitz's age/biography, but could also be other candidates

### HYPOTHESIS-B: 3009 IS Bessie Fox
- This is YOUR theory from the start; we haven't systematically validated it yet
- Bessie's 2 anchors are age-60+ (cross-age comparison unreliable)
- Embedding distance 3009 → Bessie = 1.275 — weak, the BEST Fox match but not conclusive
- We have NOT yet run the same 3-model rigor on this that we did for Harry Fox
- **This is a TODO for the next round, not a conclusion**

### HYPOTHESIS-C: Seated left IS Irving Fox
- Claude and agents have been treating this as given
- Codex flagged: "no confirmed Irving anchor was available in local cache" — means we haven't actually verified
- Left-man paired across frames at 0.671 (same person across both conservatory photos)
- **TODO: verify independently against Irving's 8 known anchors**

### HYPOTHESIS-D: 3007 is Sadie / Bessie / aged-up 3103
- Your own evolving theories across the session
- ML shows ZERO Fox family in top-10 neighbors for 3007
- Corrective analysis concluded "unknown, likely Detroit social acquaintance — WEAK"
- **This remains open**

---

## What's DONE (commits + artifacts, 15 commits total)

Listed commits (newest first, all in `main` not yet pushed):
1. `4cb2ed98` Codex Harry audit (4th independent confirmation of not-Harshel)
2. `b8076009` Session 153 close — final artifacts + Session 154 prompt
3. `3cd841d1` Harry Isaackovitz breakthrough doc (**over-claimed — fixing**)
4. `352aeef8` Scripts: shadow-eval + embedding baselines (not yet run)
5. `3ba5dbff` UX fix: accidental-skip undo path (server + client + render + 15 tests, 0 regressions)
6. `7e43d858` Harry Fox anchor verification (2-cluster misassignment found)
7. `27da87d5` Codex audit of session 153 findings (3 P0, 4 P1, 2 P2, 1 P3)
8. `83c203f7` Corrective analysis (replaces earlier Esther/Dora hypothesis)
9. `3108450b` Gemini prompt audit (3 replication attempts, Detroit reproduced)
10. `22fa64a6` Skip UX investigation + mark 3010 background
11. `05782fa9` Person 2510 snapshot before reversing your accidental skip
12. `b4537ace` 1918 photo candidate matrix (early work, Esther/Dora hypothesis since retracted)
13. `4430f1ad` Interim: Gemini Detroit transcript + 3007 investigation
14. Earlier commits same pattern

---

## What's NOT DONE (TODO for this session or next)

| Item | Status | Why |
|---|---|---|
| Systematic Bessie validation (3 models + ML similarity) | **NOT DONE** — you just called this out | I skipped this and went straight to Harry. Running now. |
| Confirm Irving Fox is seated-left | **NOT DONE** — Codex flagged this gap | No Irving anchor in local cache per Codex |
| Harry Fox anchor repair execution | **NOT EXECUTED** — awaiting user greenlight | Destructive-ish; also the face ID discrepancy (1fea75 vs 2bc31) must be resolved first |
| Opus 4.6 1M context independent audit | **NOT DONE** — you just requested | Launching now. Note: Agent tool enum is `opus` only, I can't guarantee 4.6 vs 4.7 selection; will document what we get |
| Gemini shadow-eval execution | **NOT RUN** — rate-limit blocked earlier | Script committed; resume when quotas reset |
| Embedding baselines execution | **FAILED** — Supabase statement timeout | Needs smaller page size or filter |
| Production `date_labels` Detroit correction | **SKIPPED** — you said "ignore B" | Deliberate |
| Photo event-clustering PRD | **RESEARCH ONLY** | Research doc written; no PRD |
| Belle Isle archival citation (Codex P0) | **NOT DONE** | Need Burton Historical Collection ref |
| Children inventory for beach photos | **NOT DONE** | 6 recurring kids unknown, flagged |
| Event grouping built-in feature | **RESEARCH ONLY** | Tier-1 approach recommended by agent af0449b5 |

---

## What Claude should have done differently

1. **Not conflated "not Harshel" with "is Harry Isaackovitz"** — 4 sources confirmed the former, 0 can confirm the latter (no reference photo)
2. **Run the same systematic rigor on 3009 = Bessie as on the center man** — your first-prompt theory deserved that up front, not late in the session
3. **Proactively recommended session wrap** at 60% context / 5+ commits (new rule now exists: `.claude/rules/proactive-context-management.md`)
4. **Kept fewer, better docs** — 14 feedback files is too many; this summary should have existed from the start

---

## Going forward (three parallel tracks being launched now)

1. **Bessie Fox systematic validation** — same 3-model rigor as Harry Fox
2. **Independent audit by different model** — Opus 4.6/4.7 1M context, fresh session
3. **Coverage audit** — go through your original prompts and verify nothing important was skipped

When all three return I'll synthesize with honest confidence levels (not conflated).
