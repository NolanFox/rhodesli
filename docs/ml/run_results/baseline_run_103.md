# Baseline Clustering Run — Session 103

**Date:** 2026-03-15
**Run ID:** local (Supabase not configured locally)
**Pipeline:** cluster_new_faces
**Scorer:** baseline
**Threshold:** 1.05 (MATCH_THRESHOLD_HIGH)
**Mode:** dry-run

## Results

| Metric | Value |
|--------|-------|
| Total proposals | 470 |
| Zero-distance (pre-grouped) | 42 |
| Real proposals | 428 |
| Identities loaded | 3413 |
| Embeddings loaded | 2852 |
| Confirmed identities | 99 |

## Tier Breakdown

| Tier | Count | Threshold |
|------|-------|-----------|
| VERY HIGH (< 0.80) | 86 | Best matches |
| HIGH (0.80-1.05) | 384 | Good matches |
| MODERATE | 0 | (threshold capped at 1.05) |
| LOW | 0 | (threshold capped at 1.05) |

## Top 10 Proposals by Confidence (excluding zero-distance)

| Source | Target | Distance | Confidence |
|--------|--------|----------|------------|
| Unidentified Person 4ffef472 | Charles Fox | 0.3434 | VERY HIGH |
| Unidentified Person de4a51c0 | Esther Burd Fox | 0.5680 | VERY HIGH |
| Unidentified Person a7e4dc49 | Esther Burd Fox | 0.5815 | VERY HIGH |
| Unidentified Person c0e30ef7 | Charles Fox | 0.6411 | VERY HIGH |
| Unidentified Person d768a992 | Charles Fox | 0.6531 | VERY HIGH |
| Unidentified Person 23d942f6 | Charles Fox | 0.6734 | VERY HIGH |
| Unidentified Person 380d3419 | Charles Fox | 0.6803 | VERY HIGH |
| Unidentified Person 62fa6290 | Charles Fox | 0.6884 | VERY HIGH |
| Unidentified Person bc792418 | Charles Fox | 0.6961 | VERY HIGH |
| Unidentified Person cb08e23d | Esther Burd Fox | 0.7045 | VERY HIGH |

## Target Distribution (Top 10)

| Target Identity | Proposals |
|-----------------|-----------|
| Charles Fox | 165 |
| Esther Burd Fox | 101 |
| Albert Fox | 95 |
| Roland Fox | 66 |
| Rose | 14 |
| Unidentified Person 3131 | 5 |
| Betty Capeluto Fox | 4 |
| Isaac Franco | 3 |
| Morris Franco | 2 |
| Belle Franco | 2 |

## Cross-Community Matches

None detected (all proposals within same community).

## Notes

- 42 zero-distance proposals are already-grouped faces (exact embedding matches from prior clustering)
- Fox family dominates proposals (427/470) — expected given recent Charlie Fox collection ingest
- Rhodes identities (Isaac Franco, Morris Franco, Belle Franco, etc.) appear in Fox Family proposals — these are cross-community family connections surfaced by the face matcher
- No cross-community flag because both source and target lack explicit community_id fields in some cases
