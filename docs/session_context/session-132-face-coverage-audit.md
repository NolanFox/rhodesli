# Session 132 — Face-Identity Coverage Audit

**Generated:** 2026-03-22T11:24:27
**Type:** READ-ONLY audit (no data modified)

## Summary

| Metric | Count |
|--------|-------|
| Total identities | 3757 |
| Active (non-merged) | 1863 |
| CONFIRMED | 125 |
| PROPOSED | 0 |
| INBOX | 1529 |
| Merged | 1894 |
| photo_faces rows | 2984 |
| photos rows | 972 |
| Faces claimed by identities | 2984 |

## Audit 1: Ghost Faces

Face IDs referenced in identity anchor_ids/candidate_ids but missing from photo_faces.

- **CONFIRMED ghost faces: 0**
- Other ghost faces: 0

## Audit 2: Orphaned Faces

Face IDs in photo_faces not claimed by any active identity.

- **Orphaned faces: 0**
- Across 0 photos

## Audit 3: Broken Photo Mappings

Faces in photo_faces pointing to photo_ids that don't exist in photos table.

- **Broken mappings: 0**

## Audit 4: Multi-Claimed Faces

Faces claimed by 2+ active (non-merged) identities.

- **Multi-claimed faces: 0**

## Audit 5: CONFIRMED with Empty Anchors

- **CONFIRMED identities with 0 anchor_ids: 24**

| Identity | Name |
|----------|------|
| d85b2279 | Molly Benson |
| e955bef9 | Matilda Tillie Moussafer Louza |
| fa0152dd | Arlene Kessler Capeluto |
| 843aaa8e | Vida Capeluto |
| 9e5f05cf | Nace Capeluto |
| 1547d786 | Anita Capeluto Franco |
| b359fe11 | Leon Capeluto |
| be977acc | Sheila Surmani |
| fd43c9dd | Boulissa Pizanti Capeluto |
| 553cb710 | Morris Mazal |
| e26383e0 | Ray Franco |
| 5ad32dd1 | Regina Reina Israel Capeluto |
| bac7731a | Eleanore Cohen |
| 4a993942 | Albert Cohen |
| 58565113 | Esther Brenda Israel |
| 9dfc300a | Herman Benson |
| 5a72fba6 | Sol Sedikaro |
| 5d9ba7e2 | Joya Habib Pizanti |
| 35963375 | Abraham Moussafer |
| a0a845d7 | Solomon Solly Galante |
| 8b98cc1a | Isaac Louza |
| 35f38086 | Rosa Sedikaro |
| e1d3d662 | Stella Hasson Surmani |
| 1549d2b4 | Belle Franco |

## Severity Assessment

- **P0 (data loss risk):** 24 — ghost faces in CONFIRMED, empty CONFIRMED anchors, broken photo mappings
- **P1 (integrity):** 0 — multi-claimed faces
- **P2 (cleanup):** 0 — orphaned faces, ghost faces in non-CONFIRMED
