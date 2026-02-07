---
paths:
  - "core/neighbors.py"
  - "core/pfe.py"
  - "core/clustering.py"
  - "core/build_clusters.py"
  - "core/fusion.py"
  - "core/grouping.py"
  - "core/temporal.py"
  - "core/embeddings_io.py"
  - "core/crop_faces.py"
  - "core/ingest.py"
  - "core/ingest_inbox.py"
  - "scripts/cluster_new_faces.py"
  - "scripts/evaluate_golden_set.py"
  - "scripts/evaluate_recognition.py"
  - "scripts/build_golden_set.py"
  - "scripts/diagnose_clustering.py"
  - "scripts/ingest_bulk.py"
  - "data/embeddings.npy"
---

# ML Pipeline Rules

Before modifying any face recognition, embedding, or clustering code:

1. **READ docs/ml/ALGORITHMIC_DECISIONS.md** — contains critical decisions about multi-anchor matching, embedding strategy, and rejected alternatives. Violating these decisions will break the system.

2. **READ docs/ml/MODEL_INVENTORY.md** — understand the current model stack before changing anything.

3. **Never average embeddings across identities** — use multi-anchor (AD-001). This is the most common mistake.

4. **core/neighbors.py is FROZEN** — its algorithmic logic must not be changed without explicit user approval. This is a Forensic Invariant from CLAUDE.md.

5. **Run golden set evaluation** after any ML change: `python scripts/evaluate_golden_set.py`

6. **If you're considering an approach not documented in ALGORITHMIC_DECISIONS.md**, STOP and flag it to the user before implementing. Describe the approach, why you think it's better, and what the risks are.

7. **Any new algorithmic decision** must be added to docs/ml/ALGORITHMIC_DECISIONS.md with the AD-XXX format before the code is committed.
