# What Rhodesli Is Becoming

Rhodesli started as a photo archive for the Jewish community of Rhodes. It is becoming a continuously learning heritage intelligence system that combines:

- **ML-powered photo analysis** — date estimation, face recognition, quality scoring
- **Genealogical data** — GEDCOM import, family relationships, birth/death dates
- **Historical context** — community events, migration patterns, era filtering
- **Social graph** — who appears together in photos, co-occurrence edges
- **Geographic intelligence** — where people lived, migrated, and resettled

## The Compounding Data Flywheel

Every user interaction improves the system:

- Upload a photo → new embeddings → better matching
- Confirm an identity → training signal → improved thresholds
- Import a GEDCOM → birth dates → better age estimation
- Correct a date → CORAL model improves
- Tag a life event → richer timeline narratives

The more data enters the system, the smarter every feature becomes.

## Novel Technical Contributions

1. **Probabilistic date estimation** with uncertainty visualization (CORAL ordinal regression + confidence intervals)
2. **Kinship calibration** from real confirmed genealogical data (AD-067)
3. **Birth year inference** from photo appearances + estimated ages
4. **Combined genealogical + photo co-occurrence social graph** — edges from both family trees and shared photos
5. **"Six degrees" connection finder** through family AND shared photo appearances
6. **Community migration pattern analysis** from photo metadata and location estimates
7. **Heritage-aware historical context layer** — 15 verified Rhodes events inline with personal timelines

## Multi-Community Vision

The system is designed to generalize beyond Rhodes:

- Any diaspora community with historical photos
- Any family with a photo collection + GEDCOM
- Any archive wanting ML-powered discovery
- GEDCOM import is the key enabler for this expansion

The architecture (JSON data + R2 storage + FastHTML) keeps infrastructure costs near zero while supporting thousands of photos and hundreds of identities.

## Key Architectural Principles

- **Git-backed archive as published truth** — reproducible, auditable, version-controlled
- **Local-first ML pipeline** — full control over models, portfolio-visible work
- **R2 as cloud staging layer** — persistence without database migration
- **SDD methodology** — PRD → acceptance tests → implementation → verification
- **Every algorithmic decision documented** in AD-NNN format (ALGORITHMIC_DECISIONS.md)
- **JSON + NumPy sufficient for now** — Postgres migration deferred until >500 photos
