# Run 002: The Leon Standard

> **WARNING: HISTORICAL RECORD. DO NOT EDIT.**

## Summary

This document captures the state of the matching system as validated during Run 2 calibration.

## Algorithm

**Best-Linkage (Single Linkage / Min-Min Distance)**

- Strategy: Find the minimum Euclidean distance between any face pair across two identities
- Implementation: `core/neighbors.py:find_nearest_neighbors()`
- Math: `min_dist = float(np.min(cdist(target_embs, cand_embs, metric='euclidean')))`

## Calibration Thresholds

**"The Leon Standard"** - Calibrated against vintage photo data.

| Tier | Threshold | Description |
|------|-----------|-------------|
| High | `distance < 1.0` | Core matches (e.g., 0.94-0.98 range) |
| Medium | `distance < 1.15` | Fringe matches (e.g., 1.04-1.09 range, different angles/ages) |
| Low | `distance >= 1.15` | Weak similarity |

Reference values from calibration:
- 0.94 - 0.98 = Core "Leon" cluster (same person, vintage quality)
- 1.04 - 1.09 = Fringe "Leon" matches (different angles/ages)

## Implementation Location

- **UI Thresholds:** `app/main.py:788-798` (`neighbor_card` function)
- **Distance Calculation:** `core/neighbors.py:74-75`

## Status

Validated on vintage photograph dataset. Thresholds tuned for sepia-toned historical photos with variable quality.

## Commit Reference

Baseline established at commit `e63c860` ("fix: relax similarity thresholds for vintage photos").
