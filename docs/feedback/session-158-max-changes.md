# Session 158 Phase 158-1b — Maximum-Change Person

Find the gedcom_id with the most distinct payload_hash states in v1, to
show user the worst-case data loss if v1 is DROPed without backfill.

## Top 20 individuals by distinct payload_hash count

| gedcom_id | name | distinct hashes | null rows | total rows |
|---|---|---|---|---|
| `@I132123770537@` | 'Leon Eric Fox' | 2 | 1 | 9 |
| `@I132123770916@` | 'Jill Tracy Fogel' | 2 | 1 | 9 |
| `@I132123770992@` | 'Roland Fox' | 2 | 1 | 9 |
| `@I132123771036@` | 'Betty Susan Capeluto' | 2 | 1 | 9 |
| `@I132123771063@` | 'Norman Allen Fogel' | 2 | 1 | 9 |
| `@I132123771081@` | 'Lois Joan Waldorf' | 2 | 1 | 9 |
| `@I132123840707@` | 'Albert ( Elia Ellis ) Fox' | 2 | 1 | 9 |
| `@I132126986995@` | 'Esther Burd' | 2 | 1 | 9 |
| `@I132126987005@` | 'Leon Capeluto' | 2 | 1 | 9 |
| `@I132126987020@` | 'Victoria Capuano' | 2 | 1 | 9 |
| `@I132126987064@` | 'Morris Waldorf' | 2 | 1 | 9 |
| `@I132126987090@` | 'Fay Arkless' | 2 | 1 | 9 |
| `@I132126987287@` | 'Lewis J Fogel' | 2 | 1 | 9 |
| `@I132126987317@` | 'Mitchell ( Mitch ) Craig Fogel' | 2 | 1 | 9 |
| `@I132126987339@` | 'Jarrod Michael Fox' | 2 | 1 | 9 |
| `@I132126987783@` | 'Celia ( Sylvia ) Silver' | 2 | 1 | 9 |
| `@I132127274578@` | 'Israel ( Itzik ) ( Ike ) Arkless' | 2 | 1 | 9 |
| `@I132127274579@` | 'Sarah ( Sura Rivka Sophie ) Noble' | 2 | 1 | 9 |
| `@I132127274580@` | 'Irene Rose (Ronny) Arkless' | 2 | 1 | 9 |
| `@I132123770510@` | 'Nolan Andrew Fox' | 2 | 1 | 9 |

## Top 10 families by distinct payload_hash count

| family_gedcom_id | distinct hashes | null rows | total rows |
|---|---|---|---|
| `@F1007@` | 2 | 0 | 5 |
| `@F1008@` | 2 | 0 | 5 |
| `@F1000@` | 2 | 0 | 5 |
| `@F1001@` | 2 | 0 | 5 |
| `@F1002@` | 2 | 0 | 5 |
| `@F1003@` | 2 | 0 | 5 |
| `@F1004@` | 2 | 0 | 5 |
| `@F1005@` | 2 | 0 | 5 |
| `@F1006@` | 2 | 0 | 5 |
| `@F1009@` | 2 | 0 | 5 |

## Aggregate stats — INDIVIDUALS (excl. NULL payload_hash)

- Total distinct gedcom_ids: 21,998
- Individuals with >1 distinct payload_hash state: 21,174 (96.3%)
- Individuals with >=3 distinct states: 0
- Total distinct (gedcom_id, payload_hash) pairs (= post-backfill v2 row estimate): **43,172**

## Aggregate stats — FAMILIES (excl. NULL payload_hash)

- Total distinct family_gedcom_ids: 6,741
- Families with >1 distinct payload_hash state: 6,417 (95.2%)
- Total distinct (family_gedcom_id, payload_hash) pairs (= post-backfill v2 row estimate): **13,158**

## NULL payload_hash rows (legacy pre-hash data)

- gedcom_individuals: 21,809 of 196,645 (11.1%)
- gedcom_families: 0 of 33,324 (0.0%)

## Implication for cutover strategy

If Option A (full historical backfill) is chosen:
- v2 individuals: ~43,172 rows (vs current 21,998 — adds ~21,174)
- v2 families: ~13,158 rows (vs current 6,741 — adds ~6,417)
- Plus need to handle 21,809 NULL-hash individual rows (compute canonical hash)
- Total v2 rows: ~56,330 vs v1's 196,645+33,324 = 229,969 → still **~4.1x reduction**

If Option B (keep v1 individuals + families):
- Save only what change_log saves (~30 MB compressed in R2 — 1.65M rows)
- v1 individuals + families stay (~150 MB on disk after VACUUM)
- Still need to keep dual-read helper or re-point app reads back to v1

