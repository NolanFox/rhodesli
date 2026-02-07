---
paths:
  - "data/identities.json"
  - "data/photo_index.json"
  - "data/embeddings.npy"
  - "data/golden_set.json"
  - "data/file_hashes.json"
---

# Data File Rules

1. **Never delete data** — all operations must be reversible
2. **Photo IDs must use a single consistent scheme** (Lesson #25)
3. **Back up before bulk modifications**: copy to data/backups/ with timestamp
4. **All photo paths must be normalized** to just the filename (no directory prefix)
5. **After modifying identities.json**, verify cross-references with photo_index.json and embeddings.npy are still valid
