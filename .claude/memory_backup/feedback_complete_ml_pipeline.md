---
name: Complete ML pipeline execution — don't stop at dry-run
description: When running ML clustering/pipelines, execute the full pipeline end-to-end including pushing results to production and verifying in browser. Dry-run is not sufficient.
type: feedback
---

When asked to run ML clustering or any data pipeline, execute the FULL pipeline:
1. Sync production data locally
2. Run the pipeline (not just --dry-run)
3. Push results to production
4. Verify results appear in the production UI

**Why:** Session 108 — I ran `cluster_new_faces.py --dry-run`, checked distances, and declared "no matches found" without actually pushing proposals or verifying in the UI. The user then showed me screenshots proving the Similar Identities feature WAS finding James Fields matches. I also failed to re-run the grouping pipeline which would cluster the James Fields INBOX faces together.

**How to apply:** When the prompt says "run clustering" or "run ML pipeline", that means the full end-to-end flow with production verification. A dry-run is a diagnostic step, not the deliverable.
