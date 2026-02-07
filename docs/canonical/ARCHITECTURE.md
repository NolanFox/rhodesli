# Rhodesli Architecture (Legacy)

> **Note:** This file is superseded by `docs/architecture/OVERVIEW.md` and the other files in `docs/architecture/`. It is kept for historical reference only.

## Core Entities
- **Photo**: Raw image file, immutable
- **Face**: Detected face with embedding, bbox, detection score
- **Identity**: Cluster of faces believed to be same person
- **Centroid**: Mean embedding of identity's anchor faces

## Key Invariants
1. Photos are never modified after ingestion
2. Every identity with >1 anchor has a centroid
3. All face lists passed to templates have identical schema
4. MLS uses scalar sigma formula (single log term)

## Data Flow
1. Ingest: raw_photos -> face detection -> embeddings.npy
2. Cluster: embeddings -> identities.json (with centroids)
3. Serve: identities.json -> API -> UI

## Known Limitations
- Sigma values are heuristic (derived from detection score + face area)
- Date estimation not yet implemented
