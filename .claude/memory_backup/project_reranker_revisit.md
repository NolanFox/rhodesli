---
name: Reranker revisit threshold
description: Session 103 reranker showed zero improvement — revisit after 50+ confirmed Fox identities or 200+ total confirmed
type: project
originSessionId: 27dd84b2-b7c4-4c48-8614-cb15d02f538c
---
Session 103 reranker (PRD-038 shadow mode): zero improvement over baseline. Not activated.

**Why:** Insufficient confirmed labels to train on. ~8 Fox family confirmed isn't enough signal.
**How to apply:** Don't invest in reranker work until: (1) 50+ confirmed Fox family identities, or (2) 200+ total confirmed across all communities. At that point, re-run the shadow comparison and check if the reranker adds value.
