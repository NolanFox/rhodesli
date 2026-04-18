# Session 153 — Person 3007 Deep Investigation

**Date:** 2026-04-18
**Subject photo:** `raw_photos/02068_p_13akf5twbc3600.jpg` — 1918, New York (per Gemini), Fox siblings group
**Question:** Who are Person 3007 (standing left) and Person 3009 (standing right)?

## 1. Fox Sibling Family (GEDCOM, Meyer Fox × Reva Heft)

| Sibling | Birth | Age in 1918 | Status 1918 | Status ~1931 |
|---|---|---|---|---|
| Harry (Hyman) Fox | 13 Jan 1882 | 36 | M, seated in 02068 | 49 |
| Sarah (Sora Dvoura) Fox | ~1884 | 34 | — | 47 |
| **Bessie (Basya Minya) Fox** | ~1884 | **34** | — | 47 |
| **Sadie (Shima) Fox Fuchs** | ~1888 (Dec 10 1887 per her Dec. of Intent.) | **30–31** | marries Jake Levine **Dec 21 1918 NYC** | 43 |
| Rachel (Ray/Ronya) Fox | 15 Oct 1891 | 27 | — | 40 |
| Albert (Elia) Fox | ~1896 | 22 | seated center | 35 |
| **Irving (Israel) Fox** | 10 Jan 1898 | 20 | seated (probably left) | 33 |
| Jack Fox | ~1901 | 17 | — | 30 |

Deceased by 1918: Yudel, Malka, Leyba. Four sisters alive: **Bessie, Sarah, Sadie, Rachel.**

## 2. Target Photos (Gemini dates/places, local inspection)

| Photo | Gemini year | Place | Composition |
|---|---|---|---|
| 02068 (1918 Detroit hypothesis) | **1918** (fashion 1915–22) | NY, NY | 3 men seated (Albert, Harry, Irving), 2 women standing (3007 L, 3009 R), 3010 partial right |
| 02166 (3101a + 3103, 11 faces) | (no label, fashion ~1935–1940 from overall look) | beach | Adult women back row + kids front; Leona + Charles Fox present (as older children/teens) |
| 02167 (3101b, 10 faces) | **1931** | Dayton, Ohio | beach umbrella; Esther + Charles + Leona (as child) present |
| 02119 (3101c, 9 faces) | (no label) | Great Lakes beach | Roland Fox (as young boy b.1930) present → dates this ~1935–1937 |
| 02136 (Bessie beach) | **1945–50** | coastal US | Bessie + Esther, 2 older women |
| 69835310 (Sadie family portrait) | **1925–1935** | — | Studio portrait, Sadie w/ family |

## 3. Who else is in the 3101/3103 beach photos (anchored identities)

**02166** (3101a + 3103): 11 faces — **Charles Fox** (CONF, as ~6yo boy), **Leona Fox Smilg** (CONF, as ~10yo), plus 3101, 3103, 3106, 3107, 3108, 3109, 2510, 2514, 2516.

**02167** (3101b): 10 faces — **Esther Burd Fox** (CONF), **Charles Fox** (CONF), **Leona Fox Smilg** (CONF), plus 3101, 3106, 3107, 3108, 2510, 2514, 2516.

**02119** (3101c): 9 faces — **Roland Fox** (CONF, ~b.1930, ~5yo), plus 3101, 3106, 3107, 3109, 2510, 2514, 2516, 3861.

**2510, 2514, 2516, 3106, 3107 all appear in ALL THREE beach photos** → This is a recurring **Charles Borris + Leona + Roland Fox cohort at a lake beach in the 1930s** (Albert + Esther's kids + cousins/playmates). 3101 appears in all three — she is a recurring adult woman in this cohort. **3103 appears only in 02166.**

## 4. Embedding distance analysis (L2, normalized, 512-d PFE mu)

Distances are L2 on unit-normalized vectors. For Fox-family sibling comparisons, min distance typically 1.08–1.20. Cross-family distances often 1.30+.

**3007 (1 anchor, Detroit 1918) vs candidates:**
| Candidate | min | top5-mean | mean | n |
|---|---|---|---|---|
| Bessie | 1.367 | 1.386 | 1.386 | 2 |
| Sadie | 1.306 | 1.347 | 1.347 | 4 |
| **3103** | **1.161** | 1.161 | 1.161 | 1 |
| **3101** | **1.163** | 1.187 | 1.187 | 3 |
| Leona | 1.213 | 1.241 | 1.332 | 31 |
| Esther | 1.215 | 1.235 | 1.341 | 143 |

**3009 vs candidates:**
| Candidate | min | top5-mean | mean | n |
|---|---|---|---|---|
| Bessie | **1.275** | 1.317 | 1.317 | 2 |
| Sadie | 1.358 | 1.381 | 1.381 | 4 |
| 3101 | 1.324 | 1.373 | 1.373 | 3 |
| 3103 | 1.324 | 1.324 | 1.324 | 1 |
| Leona | 1.239 | 1.284 | 1.342 | 31 |
| Esther | 1.263 | 1.269 | 1.372 | 143 |

**3101 vs 3103:** 1.294 (top5 1.336) — these are different people (distances consistent with two distinct individuals; Fox sisters are ~1.10–1.20 apart, 3101 vs 3103 is 1.29).

**Sibling sanity:** Albert vs Harry min=1.126; Leona vs Sadie min=1.195; Bessie vs Sadie min=1.302 (Bessie and Sadie embeddings are far; both are poor-quality old-photo / old-age anchors).

## 5. Top-20 nearest neighbors (instructive)

**3007's nearest faces** (d=1.119–1.22): #1 is another unidentified (inbox_c2285181c7eb). Hits #2, #3, #6 are all **3103 and 3101 anchors** (d=1.161, 1.163, 1.192). **Charles Fox** anchors show up at d=1.183 (#4). **Leona** and **Esther** appear in the top 20. 3007 clearly lives in the Fox-family neighborhood and specifically close to 3101/3103 clusters.

**3009's nearest faces:** Top 10 are all unidentified INBOX faces (d=1.148–1.22). First tagged hit is **Leona** at d=1.239 (weak). 3009 does NOT resemble any confirmed Fox woman strongly — it sits in a neighborhood of other unidentified faces, many from the same Charlie Fox upload batch.

## 6. Visual face comparison (local crops, `/tmp/face_crops/`)

- **3007** (Detroit 1918): Young woman, full rounded face, wavy dark hair, small smile, looks ~20–25.
- **3009** (Detroit 1918): Similar age, more angular jaw, serious gaze, looks ~22–28.
- **3103** (02166, ~1935): Curly/wavy hair woman, round face, smiling, looks ~35–45. **Face shape is compatible with 3007 aged 17 years** (3007 Dec 1918 → 3103 ~1935 = +17y).
- **3101** (all three beach photos): Bobbed hair, thinner face, ~30–40. Visually reasonable but less striking a match than 3103.
- **Bessie (02136)**: Middle-aged woman ~55–60, wavy dark hair (not curly). Does not look like a grown-up 3007; face shape different.
- **Bessie (15036201)**: Elderly woman 80+. Cannot compare young features meaningfully.
- **Sadie (01550, with glasses)**: Round face, glasses, wavy hair, ~40. Less resemblance to 3007's softer jawline.
- **Sadie (IMG_2571, ~1941 passport photo age ~54)**: Rounder face with prominent cheeks — similar face shape to **3103** than to 3007.

## 7. Apparent age vs GEDCOM fit

Gemini age-guessed 02068 subjects as [25, 20, 28, 22, 20, 30]. Mapping to faces: the two standing women (3007, 3009) were estimated ~20. Gemini tends to underestimate by 5–10 years on sepia photos.

- If 3007 is ~25 in 1918 → born ~1893 → **no sibling exactly fits** (Rachel b.1891 closest at 27).
- If 3007 is ~30 in 1918 → born ~1888 → **matches Sadie (b.1887/1888)**.
- If 3009 is ~34 in 1918 → born ~1884 → matches **Bessie or Sarah**.
- Sadie's Dec 21 1918 wedding in NY is powerful circumstantial evidence: if the photo is a pre-wedding family gathering, Sadie is the most likely one standing.

## 8. Verdict

### 3007 — Best hypothesis: **Sadie Fox Levine** (possible) OR **3103/3101 = same person as 3007** (possible)

Confidence tier: **POSSIBLE (not STRONG)**. Rationale:
- **Strongly supports Sadie**: her Dec 1918 NY wedding matches photo date+place; she is age-plausible (30–31 in 1918 could look 25 in a candid).
- **Against Sadie**: embedding distance 3007↔Sadie min=1.306 is in "not same person" territory (Fox siblings typically 1.10–1.20 when truly same person). But Sadie has only 4 anchors, all ~1940s-era glasses photos with heavy age gap.
- **Against Bessie**: 3007↔Bessie min=1.367 is far; Bessie's anchors are 55+ yrs old and low quality; she was 34 in 1918 (older than 3007 appears); facial features in later Bessie photos do not match 3007's wavy hair and softer face.
- **3103 as 3007-aged-17 years**: embedding distance 1.161 is the strongest signal. If 3103 is 3007 grown up, and 3103 is in a 1935 beach photo with Albert's children, then she is plausibly Albert's SISTER at age ~47 — which fits Bessie, Sarah, or Rachel. Most likely: **3103 = Sadie** (she was unmarried from the family's perspective until 1918, then lived in LA by 1941). Or a sister visiting for a reunion.

### 3009 — Best hypothesis: **Sarah Fox** or **Rachel Fox** (unsupported by ML; geneology-only)

Confidence tier: **WEAK**. Rationale:
- Zero close embedding neighbors among confirmed Fox women. 3009↔Bessie=1.275 (weak), 3009↔Sadie=1.358 (far).
- If 3007 is Sadie, then 3009 must be a different sister. Gemini ages the two women within 2 years of each other; Sadie (30) + Rachel (27) is the closest age pair.
- **Alternative**: 3009 could be a NON-SIBLING — the photo is 1918 NY and Sadie married Jake Levine; 3009 could be Jake's sister / new sister-in-law. This would explain zero Fox family embedding signal.

### 3101 vs 3103 — are they the same person?

**No.** 3101↔3103 distance = 1.294 (top5=1.336). They co-appear in 02166 → must be distinct individuals. 3101 is bobbed-hair, thinner; 3103 is curly-hair, rounder. Their embeddings place them in different clusters of the unidentified Fox-adjacent neighborhood.

## 9. Recommendation

1. **Do NOT confirm 3007=Bessie.** Distance is far; Bessie in 02136 (1945+) looks different from 3007.
2. **Consider 3007=Sadie** but do not confirm without more evidence. Strongest support = Dec 1918 NY wedding. Weakness = embedding distance.
3. **Investigate 3103 and Sadie together.** If 3103 appears in Fox family beach ~1935 Dayton/Ohio, and Sadie-Levine lived in LA by then, she'd have to be visiting. This is plausible (family reunions).
4. **Get another anchor for Sadie from ~1918**. If any 1910s-1920s Sadie photo can be added (family albums?), the embedding comparison to 3007 becomes meaningful.
5. **Run 02068 through Gemini identification preset** with GEDCOM context (Albert's siblings, Sadie's Dec 1918 wedding) — Gemini may propose Sadie explicitly.
6. **For 3009**: pursue NON-Fox hypothesis. In-law (Jake Levine's sister/cousin) or friend. Current ML has nothing to anchor her to the Fox family tree.
