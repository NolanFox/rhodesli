# Fox Family Collection — Integration Prep

**Date:** 2026-03-07
**Session:** 92
**Status:** Planning

---

## Overview

The Fox family photo collection is the second collection to be onboarded to
Rhodesli, following the four founding collections (Vida Capeluto NYC, Betty
Capeluto Miami, Nace Capeluto Tampa, Newspapers.com).

This document covers the integration plan, expected challenges, and
infrastructure requirements for multi-collection support.

## Collection Profile

| Attribute | Details |
|-----------|---------|
| **Family** | Fox family |
| **Owner** | Nolan Fox |
| **Estimated photos** | 50-200 |
| **Date range** | ~1900s-1990s |
| **Geographic focus** | United States (various) |
| **Format** | Scanned prints, some digital |
| **GEDCOM available** | Yes — Fox family tree |

## Prerequisites

### Infrastructure (Must Be Complete First)

1. **Multi-collection architecture** (PRD-030, MULTI_TENANT.md)
   - Collection-scoped identity namespaces
   - Per-collection admin permissions
   - Cross-collection identity linking via GlobalPersonID

2. **GEDCOM import pipeline**
   - Fox family GEDCOM file prepared
   - Import script validated against existing pipeline
   - Relationship graph rendered correctly

3. **Storage capacity**
   - R2 bucket: unlimited (no concern)
   - Railway volume: check available space after current 296 photos
   - Embeddings array: will grow by ~100-500 faces

### Data Preparation

1. **Photo scanning**
   - Consistent DPI (300+ recommended)
   - File naming convention: `fox_NNN.jpg`
   - Metadata spreadsheet: filename, approximate date, people pictured, location

2. **GEDCOM preparation**
   - Export from family tree software
   - Validate format with `scripts/validate_gedcom.py` (if exists)
   - Identify overlap with existing Capeluto GEDCOM (marriage connections)

3. **Identity seeding**
   - Pre-populate key Fox family identities before ingestion
   - Link to GEDCOM records during creation
   - This prevents the "inbox flood" problem where all faces start unidentified

## Integration Steps

### Step 1: GEDCOM Import
```bash
python rhodesli_ml/importers/gedcom_import.py \
  --file data/gedcom/fox_family.ged \
  --collection "Fox Family"
```
- Validate relationship graph renders
- Check for name collisions with existing identities
- Verify GlobalPersonID links for cross-family connections

### Step 2: Photo Ingestion
```bash
# Copy photos to staging
cp fox_photos/*.jpg raw_photos/pending/

# Ingest each photo
for f in raw_photos/pending/fox_*.jpg; do
  python -m core.ingest_inbox \
    --file "$f" \
    --job-id "fox-$(date +%s)" \
    --source "Fox Family Archive" \
    --collection "Fox Family Collection"
done
```

### Step 3: Upload to R2
```bash
# Upload new photos and crops
python scripts/upload_to_r2.py --execute --filter "fox_*"
```

### Step 4: Clustering
```bash
# Find matches within Fox collection and across Capeluto
python scripts/cluster_new_faces.py --dry-run
```

### Step 5: Cross-Collection Linking
- Review auto-clustering results for cross-collection matches
- Any Fox faces matching Capeluto identities create GlobalPersonID links
- Admin reviews and confirms cross-collection identity merges

## Expected Challenges

### 1. Cross-Collection Identity Resolution
**Problem:** Same person may appear in both Fox and Capeluto collections.
**Solution:** GlobalPersonID system (Session 91). Auto-clustering will surface
cross-collection matches as Tier 2 suggestions for admin review.

### 2. Collection-Scoped Browsing
**Problem:** Users may want to browse only Fox photos or only Capeluto photos.
**Solution:** Collection filter on browse page (already exists for source field).
Extend to support collection-level filtering.

### 3. GEDCOM Overlap
**Problem:** Fox and Capeluto families may share GEDCOM individuals (marriages).
**Solution:** GEDCOM deduplication during import. Match on name + dates.
Link via GlobalPersonID rather than merging GEDCOM records.

### 4. Naming Conventions
**Problem:** Fox photos may use different naming than existing `Image NNN_compress.jpg`.
**Solution:** Standardize to `fox_NNN.jpg` format. Photo ID generation is
filename-based (SHA256), so format doesn't matter for lookups.

## Rollback Plan

If integration fails:
1. All Fox data is in a separate collection — can be filtered out
2. GEDCOM import is reversible (delete by collection)
3. Embeddings can be rebuilt from photos
4. No existing Capeluto data is modified during Fox ingestion

## Success Criteria

- [ ] Fox GEDCOM imported with correct relationships
- [ ] All Fox photos ingested with face detection
- [ ] Cross-collection matches surfaced in Discoveries
- [ ] Browse page filters by collection correctly
- [ ] No regression in existing Capeluto functionality
- [ ] Community member can find Fox family members by name
