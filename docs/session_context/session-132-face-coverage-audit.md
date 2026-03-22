# Session 132 — Face-Identity Coverage Audit

**Generated:** 2026-03-22T09:51:29
**Type:** READ-ONLY audit (no data modified)

## Summary

| Metric | Count |
|--------|-------|
| Total identities | 3545 |
| Active (non-merged) | 1649 |
| CONFIRMED | 125 |
| PROPOSED | 0 |
| INBOX | 1314 |
| Merged | 1896 |
| photo_faces rows | 2984 |
| photos rows | 972 |
| Faces claimed by identities | 2774 |

## Audit 1: Ghost Faces

Face IDs referenced in identity anchor_ids/candidate_ids but missing from photo_faces.

- **CONFIRMED ghost faces: 2**
- Other ghost faces: 0

### CONFIRMED Ghost Faces (P0)

| Identity | Name | Face ID | List |
|----------|------|---------|------|
| 64096284 | Netanel Menashe | `inbox_22a58175dbc2` | anchor |
| 64096284 | Netanel Menashe | `inbox_b13a0d1781cc` | anchor |

## Audit 2: Orphaned Faces

Face IDs in photo_faces not claimed by any active identity.

- **Orphaned faces: 212**
- Across 36 photos

### Top Photos with Orphaned Faces

| Photo ID | Orphaned Faces | Sample Face ID |
|----------|---------------|----------------|
| inbox_b5e8a89e_7 | 42 | `inbox_6d0fd0c5861e` |
| inbox_b5e8a89e_1 | 26 | `inbox_c9fc6a726883` |
| inbox_b5e8a89e_4 | 16 | `inbox_499b142ed41b` |
| inbox_b5e8a89e_9 | 16 | `inbox_1c97825f18f6` |
| inbox_b5e8a89e_1 | 16 | `inbox_77dd3639c416` |
| inbox_b5e8a89e_3 | 16 | `inbox_dc5d5d377a2c` |
| inbox_b5e8a89e_5 | 12 | `inbox_4e560fa616a7` |
| inbox_b5e8a89e_0 | 10 | `inbox_81b7dc7a1952` |
| inbox_ancestry-2 | 10 | `inbox_a193e8ee9a5a` |
| inbox_b5e8a89e_1 | 6 | `inbox_383c29f0bc21` |
| inbox_b5e8a89e_8 | 6 | `inbox_b4fa91024370` |
| inbox_b5e8a89e_6 | 4 | `inbox_5f534e5ed2aa` |
| inbox_b5e8a89e_2 | 4 | `inbox_3b78ed80a5c8` |
| inbox_facebook-2 | 3 | `inbox_c284f6dd1210` |
| inbox_ancestry-2 | 2 | `inbox_0a262d75ae34` |
| inbox_ancestry-2 | 2 | `inbox_69d3b18048a6` |
| inbox_e74c8c88_2 | 2 | `howie_frano_collection_59639822_10216844893127554_6438337993123037184_n:face17` |
| inbox_1ab1700e_0 | 1 | `claude_benatar_purim_1922_646723611_10174283698525346_748045227922631717_n:face7` |
| inbox_findagrave | 1 | `inbox_fcd80012924c` |
| inbox_8bf20e54_2 | 1 | `newspaper_Morris_Capouano_Western_Market_Formal_Opening:face3` |
| inbox_ancestry-2 | 1 | `inbox_d33933ab9ea5` |
| inbox_ancestry-2 | 1 | `inbox_27b97282c522` |
| inbox_ancestry-2 | 1 | `inbox_badc0d0c32bb` |
| inbox_facebook-2 | 1 | `inbox_260804120906` |
| inbox_e74c8c88_1 | 1 | `howie_frano_collection_59579666_10216844892927549_1817759077405556736_n:face11` |
| inbox_ancestry-2 | 1 | `inbox_e9fcdc450ee8` |
| inbox_e74c8c88_7 | 1 | `howie_frano_collection_84564242_10218989687306068_827247835496841216_n:face15` |
| inbox_ancestry-2 | 1 | `inbox_3052196cf611` |
| inbox_facebook-2 | 1 | `inbox_934427af2bde` |
| inbox_ancestry-2 | 1 | `inbox_9086de96c277` |

## Audit 3: Broken Photo Mappings

Faces in photo_faces pointing to photo_ids that don't exist in photos table.

- **Broken mappings: 0**

## Audit 4: Multi-Claimed Faces

Faces claimed by 2+ active (non-merged) identities.

- **Multi-claimed faces: 3**

| Face ID | Owners |
|---------|--------|
| `inbox_fb4b65ccecfe` | Albert Fox (85546ebf, anchor); Unidentified Person 4063 (f1fa51b2, anchor) |
| `inbox_eaf34885039f` | Unidentified Person 2820 (434f4f8a, anchor); Unidentified Person 1e91425f (1e91425f, anchor) |
| `Image 026_compress:face2` | Contested Identity (224495e8, anchor); Selma Capeluto (cca5f7ff, anchor) |

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

- **P0 (data loss risk):** 26 — ghost faces in CONFIRMED, empty CONFIRMED anchors, broken photo mappings
- **P1 (integrity):** 3 — multi-claimed faces
- **P2 (cleanup):** 212 — orphaned faces, ghost faces in non-CONFIRMED
