---
**Auditor**: Codex CLI v0.121.0
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: session-153-corrective-analysis.md, session-153-gemini-prompt-audit.md, session-153-skip-ux-investigation.md, session-144-gemini-detroit-transcript.md
**Date**: 2026-04-18
---

# Session 153 Codex Audit — Findings

Audited the four Session 153 documents plus local code/data surfaces. No network or Supabase writes.

| Sev | Finding | Reason / fix |
|---|---|---|
| **P0** | Known-wrong production label remains | `date_labels` for the Detroit photo still says `"New York, New York"`. Cannot declare session done while user-facing data is false. Add a human-reviewed correction/superseding record with provenance (preserve the original Gemini output under a `*_original_gemini` key per the pattern established in `batch_gemini_for_person.py:841`). |
| **P0** | Belle Isle treated as "ground truth" from Gemini alone | Both the prompt audit and transcript lean on Gemini's own search/chat. Need an **independent archival citation** (Burton Historical Collection photo reference, Detroit Public Library, or similar) with image-comparison URL for the exact angle before calling it "ground truth/virtually certain." |
| **P0** | Seated-men identities still need source-level verification | Corrective analysis says Irving/Harry/Albert are confirmed, then flags Harry as suspicious (face looks ~25-30, not 36). Verify Harry/Irving assignments against other anchors + merge history before using Rose Scheckzner biography to identify 3009. The Harry flag is load-bearing for the 3009 hypothesis. |
| **P1** | Embedding methodology has rigor errors | Corrective analysis says `3,285 + 328 = 3,319` — arithmetic impossible. Thresholds mix same-person, sibling, spouse, and cross-family baselines; spouse min `1.089` (Albert↔Esther) is a **red flag** (likely co-photographed contamination), not calibration. Recompute with a reproducible script and stratified known pairs (siblings excluding co-photos, parent-child, strangers). |
| **P1** | Bessie conclusion overstates ML negative evidence | Old-Bessie-to-young-Bessie cross-age comparison cannot *disconfirm* 3007. The phrasing should be "not supported by current embeddings (no young-Bessie anchor exists)" — not "ML disconfirms (1.367)." Negative claims require testable evidence. |
| **P1** | Gemini prompt fix is overfit | Attempt 3 included candidate hints WITH the correct answer in the scaffold. One photo cannot justify permanent prompt changes or "0% → 100% accuracy" language. Before deploying: shadow-evaluate on ≥10 diverse known-location photos; guard reference portraits to human-confirmed same-subject anchors only. |
| **P1** | UX undo proposal incomplete | The proposed `data-undo-url` on the skip pill will NOT restore skips because the current Z-undo handler special-cases `type === "skip"` and only redirects. Also the restore endpoint explicitly blocks SKIPPED state. Fix BOTH sides (restore-endpoint allowlist + Z-handler case) and add tests. |
| **P2** | Missed biography angles | Candidate matrix should explicitly cover: other sisters-in-law (Tina, etc.), Delmar St. household/neighbors from 1917 Detroit city directory, Detroit synagogue/Maccabees lodge/workplace (Albert's employer), draft/naturalization date conflict, and **all next-generation children born 1925-1932** for the beach cohort (Levine/Newman/Burd descendants). |
| **P2** | Privacy/audit hygiene | The Gemini transcript stores `lh3.googleusercontent.com` user-upload URLs embedded from the chat. Remove or justify retention. Also: don't recommend deletion of experiment rows — mark superseded per the append-only audit pattern. |
| **P3** | Wording drift | "1918 photo," "1917-mid-1918," and "c.1916-1918" are used interchangeably across the four documents. Normalize date language and confidence expression. |

**Tokens used:** 205,965
**Status:** uncommitted; review before committing.
