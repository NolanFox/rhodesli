# Session 153 — CORRECTIVE Analysis (replaces 1918 candidate matrix + 3007 investigation)

**Date:** 2026-04-18
**Subject photos:** 02068 (Detroit conservatory), 02166/02167/02119 (lakefront beach), 01654 (4 boys + dog), 02136 (Bessie+Esther beach)
**Reason for redo:** 6 errors in prior analyses. See user feedback in this session prompt.

---

## 1. Photo Date Bounds (corrected)

### 02068 — Detroit, Belle Isle Conservatory
| Source | Year evidence |
|---|---|
| Gemini Turn-3 transcript | "around 1917" — based on Albert's confirmed 1917 Detroit residence |
| Gemini fashion analysis (date_labels) | 1915-1922 (suits, sailor collars, slicked hair) |
| User correction | "Probably before Albert enlisted for World War I" |
| Albert's GEDCOM | RESI Detroit 1917 + 1917-1918 single; EVEN 7 Jun 1918 (likely draft induction); EVEN 5 Jul 1918 NY (likely Camp Devens reporting); arrival back from France 28 Apr 1919 |

**Corrected window: 1917 — early-to-mid 1918** (most likely summer/fall 1917, when Albert was new in Detroit and unmarried, before June 1918 induction). 1915-1916 is possible if Albert visited Detroit pre-residence, but no GEDCOM event supports it.

### 02136 (Bessie+Esther beach)
~1945-1950 (Esther ~45-50, Bessie ~60-65). Used here only as Bessie's identity anchor. **Bessie's only two anchors in our system are from age ~60+** — cross-age comparison to a ~33-year-old is extremely unreliable.

### 02166 / 02167 / 02119 (lakefront beach trio)
Roland Fox (b.1930) appears in 02119 looking ~5 → ~1935. Charles Fox (b.1931) in 02166 looking ~6 → ~1937. Leona (b.1921) in 02167 looking ~10-12 → ~1931-1933. **Window: ~1933-1937, same lakefront, recurring cohort.** Same-day vs different-day uncertain.

### 01654 (4 boys + dog)
Outdoor portrait. Looks ~1933-1940. Person 3079 (`inbox_5ebcb14b250b`) is the boy 3rd from left (in cap).

---

## 2. Re-Aged Candidate Table (1917-mid 1918 window)

**Apparent ages of the 02068 standees (Gemini estimate ~20-25; my visual: ~25-32 for both standing women, with 3007 looking slightly younger).**

| Candidate | b. | Age 1917 | Reachable Detroit 1917-18 | In photo plausibility |
|---|---|---|---|---|
| **Bessie Fox** | abt 1884 | **33-34** | **Dayton OH (1910 RESI)** — driving distance to Detroit | Possible by age, family geography |
| Sarah Fox Fader | abt 1884 | 33-34 | Brooklyn (1915-1920) | Possible (long trip), but no anchor to compare |
| Sadie Fox Levine | abt 1888 | 29-30 | NYC 1910 → Union/Miami OH 1920 (gap 1911-1919). 3 young children (b.1911,1913,1915) | **Less likely** — 3 small kids, hard to travel child-free; geography unclear |
| **Rachel Fox Newman** | 15 Oct 1891 | **26** | Brooklyn 1910s | Possible but distant |
| Rose Scheckzner (Harry's wife) | 1884 | 33 | Dayton OH (married Harry by ~1908; child David Louis b.~1909) | Possible by age + location; **no anchor** |
| **Esther Burd** | abt 1900 | **17-18** | Arcanum OH (1917 EVEN). Albert's future wife (m. 6 May 1920) — courtship not yet documented | Age slightly young for the photo. Travel reason weak (couples weren't yet established). |
| **Dora Burd** | abt 1895 | **22-23** | Arcanum OH 1917-1918 | Age fits. Travel reason: would need Esther/Burd-side connection — Esther+Albert weren't married yet. Weak. |
| Edith Rosenthal | b.1904 | **13** | Brooklyn | **ELIMINATED** — too young; Irving married her later (~1921) per 1946 25th-anniversary photo |

**Note on prior errors:**
- Session 153 said "Sadie wedding 21 Dec 1918 NY" — **WRONG**. Sadie's actual marriage to Jake Levine was 24 Dec **1910** (Manhattan). She was already married 7 years and had 3 kids by 1917.
- Session 153 said Bessie "too old" — wrong: at 33-34 she's age-plausible.
- Session 153 had Esther b.1900 noted but didn't flag the awkwardness of a 17yo unmarried Ohio teenager traveling to Detroit before her courtship with Albert was established.

---

## 3. Honest Bessie Fox Assessment

**Pros:**
- Age 33-34 in 1917 fits a woman who could look 25-32 in a candid photo.
- Was in **Dayton, OH** in 1910 RESI — closest Fox-family base to Detroit (290 mi).
- 3009's BEST Fox-distance is to Bessie at d=1.275 (top3 1.317). Above same-person threshold (~1.10-1.20 sibling baseline) but better than other Fox women for 3009.

**Cons:**
- **Both Bessie anchors are from age ~60-65** (`inbox_fad6b0654cc7` from FB photo, `inbox_0ae416754174` from beach photo 02136 ~1945-50). Their internal consistency is good (d=1.08), so the embeddings represent old-Bessie reliably — but extrapolating to her 33-yr-old face is unreliable.
- 3007 vs Bessie d=1.367 — **far above** Fox-sibling baseline (1.09-1.13). 3009 vs Bessie d=1.275 — also outside same-person range.
- Bessie was already a mother by 1905 (Elizabeth Asnes) and remarried 3 Jan 1911 (Harry Isaackovitz). By 1917-18 she was a thrice-married woman with kids — possible to travel but not freewheeling.

**Verdict:** Bessie is **plausible by age and geography** for either standing woman, but ML cannot confirm because we have no young anchor. **Best-supported Fox candidate for 3009** by raw ML proximity (1.275), but distance is in "weak Fox neighborhood" territory, not "same person" territory.

---

## 4. Rose Scheckzner Assessment

- b. 1884, age **33** in 1917. Same age as Bessie.
- Married to Harry Fox before 1909 (oldest child David Louis b. ~1909; 5 children total, last in 1923).
- Lived in **Dayton OH** (Dayton Ward 9 RESI; child Frances b. Jan 1, 1918 in Dayton) — closest geographic candidate to Detroit.
- **No identity record in our system.** No anchors. ML cannot assess.
- Plausibility: HIGH on age+geography. If Harry was visiting Albert in Detroit, Rose might have come too. But Rose had a newborn (Frances) in Jan 1918, which makes Detroit travel in early 1918 unlikely. Photo more likely 1917 if Rose is in it.

**Verdict:** Plausible by biography. Cannot be ML-tested. Worth pursuing in Ancestry for a 1910s Rose photo to anchor.

---

## 5. ACTUAL Top-10 Similar Identities for 3007 (`inbox_d4a2ab25ed8e`)

Per local embedding distances over 3,319 indexed faces (anchors only):

| Rank | d | Identity | State | Source file |
|---|---|---|---|---|
| 1 | 1.119 | Unidentified Person 82863625 | INBOX | F6718DAE… (Fader collection) |
| 2 | 1.199 | Unidentified Person 2340 | INBOX | 01962 (Fox-charlie) |
| 3 | 1.206 | Unidentified Person 82863692 | INBOX | D5165DF0… (Fader) |
| 4 | 1.207 | **Unidentified Person 3009** | INBOX | 02068 (same photo) |
| 5 | 1.215 | Unidentified Person 3410 | INBOX | 02137 (Fox-charlie) |
| 6 | 1.239 | **Rachel Alhadeff Capeluto** | CONFIRMED | (Rhodes / different family) |
| 7 | 1.241 | Unidentified Person 2746 | INBOX | 02135 (Fox-charlie) |
| 8 | 1.242 | Unidentified Person 82863788 | INBOX | (Fader) |
| 9 | 1.250 | Unidentified Person 12 | INBOX | (Sephardic upload) |
| 10 | 1.258 | Unidentified Person 577 | INBOX | rhodes_jewish_historical_foundation |

**Findings:**
- **NO confirmed Fox family member** appears in the top 10 for 3007.
- Closest CONFIRMED is **Rachel Alhadeff Capeluto** (Rhodes Sephardic, unrelated to Fox) at d=1.239 — same ballpark as Esther (1.215), Albert (1.232), Dora (1.236), Irving (1.271). **All these are at the cross-family baseline** — not meaningful identity matches.
- 3007 sits in a neighborhood of OTHER unidentified Fox-charlie inbox faces and Fader-collection faces. The Fader proximity is interesting but those are random-UUID Ancestry downloads, not identified people.
- User was correct: **Esther/Dora are NOT top matches**. ML evidence for 3007 = Esther/Dora was an artifact of cherry-picking the Fox-only candidate slice.

For 3009 (`inbox_ed3f214545b9`), top match is also unidentified (d=1.196). Closest CONFIRMED Fox is Bessie at d=1.275 (very weak).

---

## 6. Person 2510 vs Person 3079 — Merge Analysis

| | 2510 | 3079 |
|---|---|---|
| Anchors | 3 (in 02166, 02167, 02119) | 1 (in 01654) |
| Internal consistency (2510 only) | d ≈ 0.80 across all 3 anchors — very tight, same person | n/a |
| Visual: 2510 | **Girl**, ~5-7yo, dark short hair, full cheeks, smile (in beach photos) | n/a |
| Visual: 3079 | n/a | **Boy**, ~5-7yo, with cap, lighter hair, serious expression |
| 2510 ↔ 3079 distance | — | min 1.203, mean 1.249 — borderline different-person |

**Verdict: NOT the same person.** Visual evidence is decisive: 2510 is a girl in beach attire; 3079 is a boy with a cap. Embedding distance (~1.2) is the typical cross-person threshold for kids of similar age. Recommend NOT merging.

(2510 is highly likely a Levine/Fader/Newman cousin to Charles/Roland/Leona based on 3-photo co-occurrence at the same lake.)

---

## 7. Children Inventory Across Beach Photos (02166, 02167, 02119)

| Identity | 02166 | 02167 | 02119 | Visible age | Apparent gender | Notes |
|---|---|---|---|---|---|---|
| Charles Fox (CONF, b.1931) | YES (~6) | YES (~6) | — | 5-7 | M | Albert+Esther's son |
| Roland Fox (CONF, b.1930) | — | — | YES (~5) | 5 | M | Albert+Esther's son |
| Leona Fox Smilg (CONF, b.1921) | YES (~12) | YES (~12) | — | 10-12 | F (older child) | Albert+Esther's daughter |
| Esther Burd Fox (CONF) | — | YES | — | adult ~30 | F | mother |
| **2510** | YES | YES | YES | **5-7** | **F (girl, dark hair)** | RECURRING child cohort. Identity unknown. |
| **2514** | YES | YES | YES | 5-8 | F (older girl) | RECURRING |
| **2516** | YES | YES | YES | 8-10 | F (older girl) | RECURRING |
| **3101** | YES | YES | YES | adult ~30-40 | F (bobbed hair, thin) | RECURRING adult |
| **3106** | YES | YES | YES | adult ~30-40 | F | RECURRING adult |
| **3107** | YES | YES | YES | child/teen | F? | RECURRING |
| **3103** | YES | — | — | adult ~35-45 | F (curly hair, round face) | only 02166 |
| **3108** | YES | YES | — | child | F? | |
| **3109** | YES | — | YES | child | F? | |
| **671** | — | YES | — | toddler in arms | ?? | Held by woman in 02167 |
| **3861** | — | — | YES | child (small bbox) | ? | Distant figure |

**Cross-photo repeat children with unknown identity:**
- **2510, 2514, 2516**: appear in ALL 3 beach photos as children. Most likely Albert+Esther's nieces/cousins — candidates: Sadie's daughters (Sophie 1911, Matilda 1913, Eva 1915 — too old by 1933-37, would be teens/20s) or Rachel Newman's children (Sandy 1929+, Natalie 1928+ per Session 153 matrix), or Bessie's grandkids, or Burd-side cousins.
- **3107, 3108, 3109**: also recurring across photos.
- Given ages 5-10 in 1933-1937, candidates are children born 1925-1932. Need GEDCOM cross-check of all Fox/Burd grandnieces/nephews born in that window living in Dayton.

---

## 8. Revised Top Hypotheses

### Person 3007 (back-left standing woman)
**Best hypothesis: UNKNOWN — likely a Detroit social acquaintance, NOT a Fox sibling**
- Confidence: **WEAK**
- Reasoning: zero confirmed Fox identity in top 10; closest Fox candidates (Esther 1.215, Dora 1.236) are at cross-family baseline. Burd sisters had no documented reason to be in Detroit in 1917. Bessie age-fits but ML disconfirms (1.367).
- Runner-up by ML neighborhood: **Same person as the Fader-collection Person 82863625** (d=1.119) — but those Fader faces are unidentified themselves; this could be a coincidence in the embedding manifold.
- Runner-up by biography (no ML support): **Rose Scheckzner** (Harry's wife, 33 in 1917, lived in Dayton) — would need a 1910s Rose anchor.

### Person 3009 (back-right standing woman)
**Best hypothesis: UNKNOWN — possibly Bessie Fox (weak)**
- Confidence: **WEAK**
- Reasoning: 3009's best Fox-anchor distance is to Bessie at 1.275 (top3 1.317). Above same-person threshold but the best Fox candidate. Bessie is age-plausible (33-34) and geography-plausible (Dayton).
- The 3007 ↔ 3009 distance is 1.207 — they are in adjacent regions but not the same person.
- Alternative: a Detroit friend / Irving's 1917-18 girlfriend / Harry's wife (Rose Scheckzner).

### Three seated men (registry-confirmed)
- Left thin man = Irving Israel Fox (CONF, b.1898 → age 19-20)
- Center laughing man = Harry Fox (CONF, b.1882 → age 35-36) — **NB: Harry looks much younger than 36 here. Either the assignment is wrong, or Harry simply photographed young.** Worth a sanity check.
- Right with bow tie = Albert Fox (CONF, b.1892 → age 25-26)

### Person 3010 (partial face top-right edge)
SKIPPED state. Bbox has negative y1 (face crops out of frame). Cannot identify.

---

## 9. Open Questions (need Ancestry / user input)

1. **Albert's actual Detroit social network 1917-1918** — fraternal lodge, synagogue, workplace. The two standing women may have no Fox-family connection at all. Belle Isle was a popular Sunday outing spot for young singles in Detroit.
2. **Rose Scheckzner 1910s photo** — would let us ML-test the "Harry+Rose visit Albert" hypothesis. With Frances b. Jan 1918 in Dayton, Rose unlikely to travel late 1917 or early 1918, but possible spring/summer 1917.
3. **Who are the 6 recurring beach children (2510, 2514, 2516, 3101, 3106, 3107)?** — Need GEDCOM enumeration of all Fox/Burd descendants born ~1925-1932 living in Dayton. Likely Levine cousins (Sadie's daughters' kids) or Newman cousins.
4. **Date estimate refinement on 02068** — Need Gemini or fashion-expert pass with the corrected "before WWI enlistment" prompt to narrow to 1917 vs 1918 vs earlier.
5. **Did Albert visit Dayton in 1917-18 and bring a Detroit photo back?** — Photo provenance (Charlie Fox album?) might tell us if 02068 was already in family hands or surfaced later from a Detroit source.
6. **Harry Fox identity sanity check** — face `inbox_e507a54f204a` looks ~25-30 not ~36. Is this assignment correct? Worth visual cross-check vs Harry's other 6 anchors.

---

## Methodology

- Local embeddings.npy (3,285 entries + 328 Fader = 3,319 indexed faces with face_id).
- All identities pulled from Supabase (4,111 rows, paginated, merge-resolved).
- Distances are L2 on unit-normalized PFE μ vectors (consistent with prior session-153).
- Same-person internal baseline: median 0.9-1.0, max 1.19-1.22 (Albert internal n=190; Esther internal n=190).
- Sibling baseline: Albert↔Harry min 1.126, Albert↔Irving min 1.095, Esther↔Dora min 1.138, Albert↔Esther min 1.089 (spouses — co-photographed contamination).
- Cross-family non-relative baseline: 1.20-1.30.
- Visual face inspection via `app/static/crops/` and ad-hoc PIL crops in `/tmp/k/` and `/tmp/beach_kids/`.
- All Supabase queries READ-ONLY.

## Errors corrected from prior analyses
| Prior claim | Reality |
|---|---|
| Photo is 1918 New York | Photo is 1917-mid-1918, Detroit (Belle Isle Conservatory confirmed by Gemini) |
| 3007 = Esther Burd (STRONG) | 3007 has NO strong Fox match; top 10 has zero confirmed Fox |
| 3009 = Dora Burd (STRONG) | 3009's only Fox proximity is to Bessie at d=1.275 (weak) |
| Sadie wedding 21 Dec 1918 NY | Sadie m. Jake Levine **24 Dec 1910** Manhattan; had 3 kids by 1917 |
| Edith Rosenthal age 14 → too young | Edith b.1904, married Irving ~1921 (m+25=1946 anniversary photo) |
| Bessie "too old" | Bessie b.1884 → age 33-34 in 1917, well within candidate range |
| 2510 ↔ 3079 might be same person | Different people — 2510 is a girl, 3079 is a boy (visual + d=1.20 borderline) |
