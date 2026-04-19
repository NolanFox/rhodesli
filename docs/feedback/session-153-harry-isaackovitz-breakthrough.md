# Session 153 — Harry Isaackovitz Breakthrough (User-Confirmed via Ancestry)

**Date:** 2026-04-18
**Source:** User's Ancestry lookup, Ancestry person ID 132506612777
**Status:** GEDCOM-confirmed; visual ML verification pending

## The finding

The user confirmed via the Ancestry tree (Fox/Capeluto/Fogel/Waldorf, tree 162873127) that the center man in the 1918 Belle Isle Conservatory photos is **Harry Isaackovich / Isaackovitz** (`gedcom_id @I132506612777@`), Bessie Fox's husband — NOT Harry Fox.

### Verified facts
| Field | Value |
|---|---|
| Ancestry ID | 132506612777 |
| GEDCOM ID | @I132506612777@ (in our `gedcom_individuals` table, `is_current=True`) |
| Name | Harry Isaackovich (Isaackovitz) |
| Birth | 1881 |
| Death | Unknown |
| Spouse | Bessie (Basya Minya) Fox (Fuks) b.1877 |
| Marriage 1 | 3 Jan 1911, New York City |
| Marriage 2 | 7 Jan 1911, Manhattan (likely civil + religious) |
| Relationship to Nolan | Husband of great-grandaunt |

### Age reconciliation for the 1917-1918 photo
- Harry Isaackovitz: age **36-37** (b.1881)
- Bessie Fox: age **40-41** (b.1877 per Ancestry; GEDCOM elsewhere had "abt 1884" — Ancestry is the authoritative source)
- Gemini's visual estimate was ~22-28 for the central figures — **off by ~14 years**, consistent with Lesson 172's warning that age estimates on older B&W photos are unreliable.

## What this changes

### Session 153 identification hypothesis (updated)
| Position | Prior guess | New guess | Evidence |
|---|---|---|---|
| Seated left | Irving Fox (b.1898) | Irving Fox — still plausible but NOT verified | TBD visual re-check |
| Seated center | "Harry Fox" (MISASSIGNED) | **Harry Isaackovitz** | User Ancestry research |
| Seated right | Albert Fox (b.1892) | Albert Fox | Confirmed anchor d=0.63 to Detroit face |
| Back-left (3007) | Unknown | Unknown — likely still a social acquaintance | ML shows zero Fox kin in top 10 |
| Back-right (3009) | Possibly Bessie Fox | **Bessie Fox** | Husband Harry Isaackovitz is the center man → strong biographical pairing |
| Far-right partial (3010) | Background stranger | SKIPPED | Already applied |

### Downstream corrections
- **The Harry Fox identity repair is now urgently needed.** 2 of Harry's 7 anchors (F=01659 young-man, G=02068-Detroit-center) are actually Harry Isaackovitz.
- **Rose Scheckzner goes back OFF the 3009 candidate list** — she would only be there if Harry Fox were in the photo, which he isn't.
- **Bessie Fox back ON the 3009 list** — matches biographically (her husband is confirmed present) and her age 40 fits a fuller-faced woman behind her husband.
- The "Sanity flag: center man looks 25-30 not 36" from the corrective analysis was wrong — the face just photographs young. Harry Isaackovitz was 36, same age as Harry Fox would have been.

## Recommended repair (awaiting user greenlight)

1. **Snapshot** `identities` row for Harry Fox (`d74cb556-6d44-4288-ade3-1cc8fa2b45a6`) to `backups/session-153/harry-fox-before-split-<ts>.json`.
2. **Create new identity** for Harry Isaackovitz:
   - State: CONFIRMED (user has confirmed the identification)
   - Name: "Harry Isaackovich" (matching GEDCOM canonical form)
   - Anchors: F (`inbox_2bc31a40c34a` — 01659 face) + G (`inbox_e507a54f204a` — 02068-Detroit face). Full face IDs to be verified against `docs/feedback/session-153-harry-verification.md`.
   - Link to `gedcom_individuals.@I132506612777@` via the existing gedcom_match flow.
3. **Detach** anchors F and G from Harry Fox.
4. **Hold anchor E** (1968-74 banquet) for user visual review — the Harry verification agent flagged it as an outlier.
5. **Audit log** both mutations with `metadata={"route": "session_153_harry_repair", "evidence": "Ancestry 132506612777"}`.
6. **Re-run Session 153 corrective analysis** for Person 3009 now that Bessie is the leading candidate (re-check embedding distance, visually compare Bessie's old-age anchor to 3009).

## Also to verify
- **3007 is still unidentified.** If Harry Isaackovitz and Bessie traveled to Detroit, who came with them? Bessie's kids? Bessie + Harry Isaack's kids (Elizabeth Asnes b.1905 would be 12 in 1917 — maybe visible in other photos but too young for a ~22yo standing woman)?
- **Any of Harry Isaackovitz's siblings**: Nathan Isaackovich (b.1876), Isaac S Isaackovich, and several children (Hyman b.1906, Sam b.1908, Katie b.1909) — all too old or too young for 3007.
- **Open question:** why did Bessie + Harry Isaackovitz travel from Brooklyn (Bessie's 1915 residence) to Detroit to visit Albert in 1917? Need Ancestry-side residence check for Harry Isaackovitz 1917.

## Gemini prompt implication
The Detroit photo should route through the 3-round scaffold with **Harry Isaackovitz** and **Bessie Fox** as identified subjects (not just Albert), so Gemini knows they are the married couple present and weights the location search accordingly. Add to the Gemini shadow-eval test set once the repair lands.

## Harness gap
The system should have prompted the user to consider sibling-in-laws (husband/wife of siblings) earlier in the identification flow. Current GEDCOM search only enumerates direct kin. Proposed BACKLOG item: extend candidate enumeration to include in-laws (spouses of all Fox siblings) by default, not only when explicitly asked. See `tasks/lessons.md` note for Session 153.
