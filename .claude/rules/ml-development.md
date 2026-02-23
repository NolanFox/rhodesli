# ML Development Rules
- ALWAYS read ALGORITHMIC_DECISIONS.md before modifying ML code
- ALWAYS update AD after ML changes with full provenance
- Gatekeeper pattern: ML outputs are proposals, admin accepts/rejects
- Confirmed data = ground truth anchors for training
- Cost per API call must be logged
- Model version must be logged per API call
