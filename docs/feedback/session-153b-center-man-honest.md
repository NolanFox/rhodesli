# Session 153b Phase 2 — Center-Man Honest Hypothesis Table

**Session:** 153b
**Date:** 2026-04-19
**Subject:** Center seated man in 02068 Detroit Belle Isle Conservatory photo (~1917), 3-man + 2-woman group
**Current Harry Fox identity contains this face:** `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (CONFIRMED) — with 2 anchors that are NOT Harshel Fox (the real Harry).

---

## The distinction Session 153 conflated

Session 153's breakthrough doc framed the conclusion as "Center man IS Harry Isaackovitz, user-confirmed via Ancestry."

That's wrong. Here's what was actually triangulated:

- **4 sources agree** on "Face F/G is NOT Harshel Fox (the real Harry)": local ML (d=1.36–1.43 to 5 Harshel anchors), Gemini 3.1 Pro (blond/blue Harshel vs dark/dark mystery man; protruding ears on mystery vs flat on Harshel), Codex independent run (confidence 0.88), and the 4th Codex audit confirming again.
- **0 sources can confirm** "Face F/G IS Harry Isaackovitz": nobody has a reference photo of Harry Isaackovitz. Ancestry has his vital records (tree 162873127, person 132506612777, b.1881, m. Bessie 3 Jan 1911) but no photo in that tree per user.

**"Not X" ≠ "Is Y".** The Ancestry lookup proved Harry Isaackovitz *existed* as a plausible candidate. It did **not** prove he is in this photo.

---

## Honest hypothesis table

| Candidate | Age in 1917 | Biographical fit | Reference photo available? | Can any model POSITIVELY identify? | Status |
|---|---:|---|---|---|---|
| **Harry Fox (Harshel)** | 35–36 | Brother of Albert; lived Dayton/Miami OH | ✅ YES — Harshel's naturalization ID card (blond, blue eyes) | **Triangulated: IS NOT him.** 4 independent sources. | ⛔ REJECTED |
| **Harry Isaackovitz** | 36 | Bessie Fox's 2nd husband (m. 3 Jan 1911); Ancestry vital records exist | ❌ NO | **No model can confirm.** Only "compatible with age + biography." | 🟡 POSSIBLE |
| **Rose Scheckzner's husband (hypothetical)** | n/a | — | — | n/a | (Rose Scheckzner IS Harry Fox / Harshel's wife per GEDCOM — so this candidate is identical to the rejected row above) |
| **Unrelated Fox-side friend / in-law** | ~30s | Albert had a documented Detroit residence 1917; could have had unrecorded social ties | ❌ NO | **No model can confirm.** | 🟡 POSSIBLE |
| **Unrelated Detroit Jewish community acquaintance** | ~30s | Belle Isle Sunday outings were common for young Jewish residents of Detroit | ❌ NO | **No model can confirm.** | 🟡 POSSIBLE (per Opus audit, this is the strongest non-Fox alternative) |
| **A Burd in-law** | — | Albert wasn't yet married to Esther (1920) in 1917 | Partial (Esther's father Solomon has photos, no others) | **No model can confirm.** Biographically weak — no Burd travel reason yet. | 🔵 WEAK |

## What we know for certain

1. ✅ The center man is NOT Harry Fox (Harshel). The "Harry Fox" identity's 2 anchors F and G are misassigned. This is triangulated across 4 sources.
2. ✅ The center man appears in at least 2 Belle Isle Conservatory frames (02068 + 91b6f6b296e93a60 + possibly 01659). Gemini confirmed same-event at 100%.
3. ✅ F and G (the 2 misassigned anchors) are the same person as each other (d=0.629, strong).
4. ✅ The photo is Detroit, Belle Isle Conservatory, ~1917 (pre-WWI-enlistment per Albert's GEDCOM).

## What we do NOT know

1. ❌ Who the center man IS.
2. ❌ Whether 3009 (back-right standing woman) is Bessie Fox (see `session-153b-bessie-validation.md` — POSSIBLE trending WEAK).
3. ❌ Whether 3007 (back-left standing woman) has any Fox-family connection (ML shows zero confirmed Fox in top-10 for her).
4. ❌ The face ID discrepancy: Codex audit says F = `inbox_1fea75...`; Session 153 breakthrough doc says `inbox_2bc31a40c34a`. This needs resolution before any repair.

## Recommended labeling if repair is executed

**Do NOT use "Harry Isaackovitz" as the new identity name.** We don't have evidence for that positive ID.

Per the Opus audit's recommendation, use a descriptive provisional name:
- **"Belle Isle Conservatory Young Man c.1917–1918"** (conservative, descriptive, leaves room for future evidence)

This:
- Preserves the information we DO have (location, approximate date)
- Doesn't bake in a speculative identification
- Allows future Ancestry finds (a Harry Isaackovitz photo, say) to promote the identity with proper evidence trail
- Won't mislead future admins or viewers

## Pre-conditions for the repair (Phase 7)

Per the Session 153b prompt, all must be true:

- [ ] 3009 = Bessie Fox validated at POSSIBLE+ confidence across 3 sources  
      **Status: PARTIAL.** Phase 1F says POSSIBLE trending WEAK. 2 of 4 sources say POSSIBLE (Claude multimodal subagent, Opus). 2 of 4 say WEAK (Phase 1A ML, Phase 1E direct visual). Phase 1C (Codex) pending.
- [ ] Face IDs F + G verified (resolve the `1fea75` vs `2bc31` discrepancy)  
      **Status: NOT DONE.** This is a hard blocker.
- [ ] Replacement identity label decided  
      **Status: SPECIFIED** above — "Belle Isle Conservatory Young Man c.1917–1918" (conservative option from Opus audit).
- [ ] Backup snapshot saved  
      **Status: NOT DONE.** Will be required in Phase 7.
- [ ] Audit_log metadata drafted  
      **Status: NOT DONE.** Will be required in Phase 7.
- [ ] Structural tests pass  
      **Status: NOT RUN.** Will be required in Phase 7.

**Gate decision for Phase 7: DO NOT EXECUTE.** See Phase 7 summary file.

## Breadcrumbs
- Session 153 breakthrough doc (to be annotated with "OVER-CLAIMED" header): `docs/feedback/session-153-harry-isaackovitz-breakthrough.md`
- Session 153 honest summary: `docs/feedback/session-153-what-weve-done.md`
- Corrective analysis: `docs/feedback/session-153-corrective-analysis.md`
- Codex Harry audit: `docs/feedback/session-153-codex-harry-audit.md`
- Gemini Harry validation: `docs/feedback/session-153-gemini-harry-validation.md`
- Opus 153b audit: `docs/feedback/session-153b-opus-audit.md`
- Phase 1 Bessie validation: `docs/feedback/session-153b-bessie-validation.md`
