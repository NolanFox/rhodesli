# Feature Matrix: Backend + ML + Annotations + Infrastructure

For navigation see [docs/BACKLOG.md](../BACKLOG.md). For bugs/frontend see FEATURE_MATRIX_FRONTEND.md.

---

## 3. BACKEND / DATA ARCHITECTURE

### 3.1 Merge System Redesign (CRITICAL)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-001 | Direction-aware merge | DONE | `resolve_merge_direction()` + 18 direction tests (2026-02-08) |
| BE-002 | Non-destructive merge history | DONE | Reversible record with full audit trail (2026-02-10) |
| BE-003 | Detach with full restoration | DONE | Undo restores pre-merge state (2026-02-10) |
| BE-004 | Named conflict resolution | DONE | Auto-correction for named->named (2026-02-10) |
| BE-005 | Merge audit log | DONE | source_snapshot + target_snapshot_before (2026-02-10) |
| BE-006 | Extensible merge architecture | DONE | _merge_annotations() retargets on merge (2026-02-10) |

### 3.2 Data Model Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-010 | Structured identity names | DONE | Auto-parse first/last from display name (2026-02-10) |
| BE-011 | Identity metadata | DONE | set_metadata() with allowlisted keys + API (2026-02-10) |
| BE-012 | Photo metadata | DONE | set_metadata/get_metadata + display + admin endpoint (2026-02-10) |
| BE-013 | EXIF extraction | DONE | core/exif.py for date, camera, GPS (2026-02-10) |
| BE-014 | Canonical name registry | DONE | surname_variants.json with 13 variant groups (2026-02-11) |
| BE-015 | Geographic data model | OPEN | Structured locations with fuzzy matching. |
| BE-016 | Temporal data handling | OPEN | Support "circa 1945", "1950s", "between 1948-1952". |
| BE-023 | Photo provenance model | DONE | Separate source/collection/source_url, 22 tests (2026-02-10) |
| FE-064 | Upload UX overhaul | DONE | Collection/source/URL fields, autocomplete (2026-02-10) |

### 3.3 Data Sync & Export (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-020 | Admin data export endpoint | DONE | Token-authenticated /api/sync/* (2026-02-10) |
| BE-021 | Production -> Local sync script | DONE | scripts/sync_from_production.py (2026-02-10) |
| BE-022 | Staged upload download pipeline | DONE | GET/POST staged API + scripts (2026-02-10) |
| BE-023 | Backup automation | DONE | scripts/backup_production.sh (2026-02-10) |

### 3.4 Photo Upload Pipeline (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-030 | Upload currently admin-only | DONE | Locked down. TODO: revert when moderation queue exists. |
| BE-031 | Upload moderation queue | OPEN | Admin approval, file size limits, rate limiting. |
| BE-032 | Web-based ML processing | OPEN | Upload -> background queue -> processing -> notification. |
| BE-033 | Batch upload | OPEN | Multiple photos with shared collection assignment. |
| BE-034 | Duplicate detection | OPEN | Hash-based detection. |

### 3.5 Database Migration (LONG-TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| BE-040 | PostgreSQL migration | PLANNED | JSON won't scale past ~500 photos. Supabase Postgres. |
| BE-041 | Schema design | OPEN | identities, faces, photos, collections, merge_history, annotations tables. |
| BE-042 | Migration script | OPEN | Zero-downtime JSON to Postgres with validation. |

---

## 4. ML / DATA SCIENCE

### 4.1 ML Feedback Loop (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-001 | User actions -> predictions | DONE | Signal harvester: 959 confirmed, 510 rejected, 500 hard negatives (2026-02-13) |
| ML-002 | Rejection memory (AD-004) | VERIFIED | "Not Same" pairs excluded from future suggestions |
| ML-003 | Confirmed matches -> golden set | PARTIAL | Exists but needs automated rebuild |
| ML-004 | Dynamic threshold calibration | DONE | AD-013: four-tier system (2026-02-09) |
| ML-005 | Post-merge re-evaluation | DONE | Nearby HIGH+ faces shown inline (2026-02-10) |
| ML-006 | Ambiguity detection | DONE | Margin-based flagging within 15% (2026-02-10) |

### 4.2 Golden Set & Evaluation (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-010 | Golden set rebuild | DONE | 90 mappings, 23 identities (2026-02-09) |
| ML-011 | Golden set diversity | DONE | Analysis script + dashboard section (2026-02-10) |
| ML-012 | Golden set evaluation | DONE | 4005 pairwise comparisons (2026-02-09) |
| ML-013 | Evaluation metrics dashboard | DONE | /admin/ml-dashboard (2026-02-10) |

### 4.3 Clustering & Matching (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-020 | AD-001 violation fixed | DONE | Multi-anchor in cluster_new_faces.py |
| ML-021 | Confidence labeling | DONE | Four-tier: VERY_HIGH/HIGH/MODERATE/LOW (2026-02-09) |
| ML-022 | Temporal priors | EXISTS | Code has temporal priors, needs AD entry + validation |
| ML-023 | Age-aware matching | OPEN | Child vs adult matching — consider age-estimation preprocessing |
| ML-024 | Photo quality weighting | EXISTS | PFE sigma (AD-010), needs verification on damaged photos |

### 4.4 Model Evaluation (LONG-TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-030 | ArcFace comparison | OPEN | Evaluate using golden set. May improve on old/damaged photos. |
| ML-031 | Ensemble approach | OPEN | Multiple models combined. Only if single-model accuracy plateaus. |
| ML-032 | Fine-tuning feasibility | OPEN | Possible with ~100+ confirmed identities. |

### 4.5 Date Estimation Pipeline

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ML-040 | Date estimation training pipeline | DONE | CORAL + EfficientNet-B0 + heritage augmentations (2026-02-13) |
| ML-041 | Gemini evidence-first date labeling | DONE | Structured prompt with cultural lag (2026-02-13) |
| ML-042 | Regression gate for date model | DONE | Adjacent accuracy >=0.70, MAE <=1.5 (2026-02-13) |
| ML-043 | MLflow experiment tracking | DONE | Local file-based at rhodesli_ml/mlruns/ (2026-02-13) |
| ML-044 | Scale-up Gemini labeling | DONE | 250 photos, 81.2% high confidence (2026-02-14) |
| ML-045 | Temporal consistency auditor | DONE | Birth/death/age cross-checks (2026-02-14) |
| ML-046 | Search metadata export | DONE | 250 docs in photo_search_index.json (2026-02-14) |
| ML-047 | CORAL model retrain | DONE | +59% training data, MLflow tracked (2026-02-14) |
| ML-050 | Date UX integration | DONE | Estimated decade + confidence on photo viewer (2026-02-14) |
| ML-051 | Date label pipeline integration | OPEN | Integrate into upload orchestrator |
| ML-052 | New upload auto-dating | OPEN | Run date estimation on new uploads |
| ML-053 | Multi-pass Gemini strategy | OPEN | Low-confidence re-labeling with Flash model |

---

## 5. ANNOTATION ENGINE

### 5.1 Photo-Level Annotations (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-001 | Annotation system core | DONE | Submit/review/approve/reject workflow (2026-02-10) |
| AN-002 | Date metadata | DONE | Photo annotation type "date" (2026-02-10) |
| AN-003 | Location metadata | DONE | Photo annotation type "location" (2026-02-10) |
| AN-004 | Event/occasion | DONE | Photo metadata "occasion" field (2026-02-10) |
| AN-005 | Source/donor attribution | DONE | "source" annotation + "donor" field (2026-02-10) |
| AN-006 | Story/narrative | DONE | "story" annotation with textarea (2026-02-10) |
| AN-007 | Photo notes (admin) | IMPLEMENTED | Notes field exists, needs expansion |

### 5.2 Identity-Level Annotations (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-010 | Structured name fields | DONE | See BE-010 (2026-02-10) |
| AN-011 | Birth/death dates and places | DONE | See BE-011 (2026-02-10) |
| AN-012 | Biographical notes | DONE | Bio, birth/death, birthplace on identity cards (2026-02-10) |
| AN-013 | Relationships | DONE | Relationship annotation type + display (2026-02-10) |
| AN-014 | Generation tracking | DONE | Via relationship_notes (2026-02-10) |

### 5.2b Suggestion Lifecycle (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-030 | Suggestion state visibility | DONE | Inline "You suggested" confirmation (2026-02-13) |
| AN-031 | Admin approval UX | DONE | Face thumbnails, skip/undo, audit log (2026-02-13) |
| AN-032 | Annotation dedup + community confirmation | DONE | "I Agree" buttons, confirmation counting (2026-02-13) |

### 5.3 Genealogical Data

| ID | Item | Status | Notes |
|----|------|--------|-------|
| AN-020 | Family tree integration | DONE | /tree with D3 hierarchical tree (2026-02-17) |
| AN-021 | GEDCOM import/export | DONE | GEDCOM 5.5.1 parser + matcher (2026-02-15) |
| AN-022 | Cross-reference genealogy databases | OPEN | Ancestry, FamilySearch, JewishGen links |
| AN-023 | Timeline view | DONE | /timeline (2026-02-15) |
| FE-100 | Timeline Story Engine | DONE | Vertical chronological view (2026-02-15) |
| FE-103 | Timeline collection filter | DONE | Dropdown filter (2026-02-15) |
| FE-104 | Timeline multi-person filter | DONE | ?people= param (2026-02-15) |
| FE-106 | Timeline era filtering | DONE | Person-specific event range (2026-02-15) |
| FE-110 | Face Comparison Tool | DONE | /compare with upload (2026-02-15) |
| ML-065 | Kinship calibration | DONE | Empirical thresholds (2026-02-15) |
| FE-112 | Tiered compare results | DONE | CDF confidence tiers (2026-02-15) |
| FE-113 | Upload persistence | DONE | Multi-face detection (2026-02-15) |

---

## 6. INFRASTRUCTURE & OPS

### 6.1 Deployment & DevOps (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| OPS-001 | Custom SMTP for email | OPEN | Branded "Rhodesli" sender via Resend/SendGrid |
| OPS-002 | CI/CD pipeline | OPEN | Automated tests, staging, deploy previews |
| OPS-003 | Health monitoring | PARTIAL | /health exists, need uptime monitoring |
| OPS-004 | Error tracking | OPEN | Sentry or similar |
| OPS-005 | Railway volume backups | OPEN | Automated backup of data/ |

### 6.2 Performance (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| OPS-010 | Page load speed audit | OPEN | Measure TTFB, LCP, CLS |
| OPS-011 | Image optimization | OPEN | Serve appropriately sized thumbnails |
| OPS-012 | HTMX swap performance | OPEN | Measure swap latency |
| OPS-013 | Caching strategy | OPEN | Static assets, photo metadata, identity data |
