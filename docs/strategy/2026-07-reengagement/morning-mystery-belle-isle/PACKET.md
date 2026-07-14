# Evidence Packet — Belle Isle Conservatory Young Man

**Case ID:** `belle-isle-young-man` · **Identity:** `ef39908e-283a-4cec-8f72-3ec83bc8d84f`
**State:** INBOX (2 anchor faces) · **Assembled:** 2026-07-13 (Session 171, by hand)
**Input manifest hash:** see `manifest.json` (immutable — do not edit this packet after sealing)

This is the immutable evidence packet an investigator sees. Every atomic claim in a verdict
MUST cite one or more of these evidence IDs (E1…E13). **Abstention is a valid, valued verdict** —
"no defensible identification; the decisive missing evidence is X" is a good morning.

---

## The subject
A young man appears in **two** photographs from the Charles Fox (Dayton, Ohio) collection. He is
currently one unconfirmed identity, "Belle Isle Conservatory Young Man c.1917-1918."

- **E1 — Same man in both photos (STRONG).** Face `inbox_1fea75ce2caf` (photo `01659`) and face
  `inbox_e507a54f204a` (photo `02068`) have pairwise matcher distance **L2 = 0.629** (calibrated
  similarity 0.914). That is deep in same-person territory (the matcher's confident-match band is
  L2 < 0.85). The two anchors are the same individual.

## What the face matcher says about *who* he is
- **E2 — No confident external match anywhere in the corpus (ABSTENTION SIGNAL).** Searching both
  anchor faces against all ~3,285 faces, the nearest *non-self* candidate is **L2 = 1.208**
  (calibrated 0.40); every one of the top-20 candidates sits at **L2 ≥ 1.20** — different-person
  territory (calibration AUC 0.9577). The closest *confirmed* people are Fox/Burd family members
  (Esther Burd Fox L2≈1.26, Charles Fox L2≈1.28, Susan Burd L2≈1.22) but all at weak, non-committal
  distances. **The matcher cannot name him.** It can only say "family-adjacent, nobody specific."

## Who he stands next to (co-occurrence — the strongest available signal)
- **E3 — Photo `01659`:** the young man + **Albert Fox (CONFIRMED)** + **Irving Israel Fox
  (CONFIRMED)**. Three men, outdoor.
- **E4 — Photo `02068`:** the young man + **Albert Fox** + **Irving Fox** + three still-unidentified
  people (`Unidentified 3007`, `Unidentified 3009`, `Unidentified 3010`) + others. A group outing.
- He appears in **both** frames beside the same two Fox brothers. He belongs to that outing/group.

## The Fox brothers he stands with (GEDCOM)
- **E5 — Albert Fox** `@I132123840707@`: b. **abt 1896**, d. 7 Feb 1990; child of family `@F5091@`.
- **E6 — Irving Israel Fox** `@I132128488728@`: b. **10 Jan 1898**, d. 16 Jun 1985; child of family
  `@F5091@`. → Albert and Irving share parents (`@F5091@` = Meyer Fox + Reva Heft): **they are
  brothers.** In 1917-18 Albert is ~21 and Irving ~19-20. A "young man" beside them reads as a peer
  of that generation (~18-22).

## The GEDCOM candidate currently on file
- **E7 — Harry Isaackovitz** `@I132506612777@`: b. **1881** (source: NYC Municipal Archives,
  Manhattan). Linked to this identity as a **candidate at confidence 0.30 (NOT confirmed)**.
  **Age tension:** b.1881 → he would be ~36-37 in 1917-18, not a peer of two ~20-year-olds.
  No reference photograph of Harry Isaackovitz is known to exist (E12).

## When and where
- **E8 — Date (Gemini date-estimate, both photos):** late 1910s, WWI-era, ~**1915-1922**; outdoor
  park setting. For `01659` the model noted "a conservatory in the background suggests a public park
  or botanical garden." High stiff collars, bow ties, three-piece suits; women's loose wide-collar
  blouses — all consistent 1915-1922.
- **E9 — Location (DB, current — CONTRADICTS the research):** `date_labels`/`photo_locations` in
  production currently say `01659` = "United States" (low confidence) and `02068` = "New York City"
  (medium confidence). **These are stale/uncorrected estimates.** They disagree with E10-E11.
- **E10 — Belle Isle Conservatory identification (research):** the conservatory structure matches
  **Library of Congress LC-DIG-det-4a17798** (Detroit Publishing Co., Belle Isle Conservatory,
  Detroit, 1905) + 6 corroborating sources (recorded in the identity note).
- **E11 — Detroit 1917-18 anchor (leads-to-reverify, cited from Session 154/156 notes):** date range
  c.1917-1918 derived from Albert Fox's GEDCOM residence "Detroit 1917" + his draft induction
  7 Jun 1918. *Treat as a lead to re-verify, not settled fact.*

## Prior conclusions on file (leads to re-verify — do not treat as ground truth)
- **E12 — "NOT Harry/Harshel Fox" (triangulated, Sessions 153/153b/154):** these two faces were
  originally mislabeled "Harry Fox" and were detached after four independent sources agreed they are
  NOT Harshel Iosha Fox: local ML pairwise 1.36-1.43 vs 5 Harshel anchors; Gemini 3.1 Pro morphology
  (blond/blue-eyed Harshel from a naturalization photo vs. this dark-featured man); two independent
  Codex audits (0.88 "NOT Harshel"). Separately, no reference photo of the GEDCOM candidate Harry
  Isaackovitz exists, so no positive face match to him is possible.
- **E13 — Provenance:** both photos are from the "Charles Fox Dayton Ohio Collection," source
  "Personal Photos." Charles Fox is himself a Fox sibling (a confirmed identity exists for him).

---

## Requested decisions (≤3 — answer these, each citing evidence)
1. **Who is he, to the extent the evidence supports it?** Is the young man best described as a Fox
   sibling / close relative of Albert & Irving in the Detroit ~1917-18 outing (E3-E6, E13), someone
   outside the family, or is the honest answer *abstain*? State a confidence tier.
2. **Keep or drop the Harry Isaackovitz GEDCOM candidate?** Given the age mismatch (E7 vs E5-E6) and
   the absence of any reference photo (E12), should confidence-0.30 candidate `@I132506612777@` be
   retained or removed?
3. **Name the single cheapest piece of decisive missing evidence** that would resolve #1.

## Hard rules for the verdict
- Cite evidence IDs for every claim. Do not introduce facts not in this packet.
- Abstention with a named missing-evidence item scores as a *good* verdict, not a failure.
- Do not assert a positive face identification to any person for whom no reference face exists (E12).
