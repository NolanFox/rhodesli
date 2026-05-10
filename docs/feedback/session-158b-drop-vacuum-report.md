# Session 158b Phase 158-6 — DROP + VACUUM FULL Report

**Date**: 2026-05-10T04:29:15.320626Z
**Mode**: EXECUTE (irreversible)
**Status**: PARTIAL FAILURE — VACUUM FULL halted on error

## Pre-DROP DB size
```
2564 MB (2,688,363,667 bytes)
```

## Post-VACUUM DB size
```
1309 MB (1,372,572,819 bytes)
```

## Delta
```
1,315,790,848 bytes (48.9%)
```

## DROPped tables
```
[
  "_dropped_gedcom_individuals_session158",
  "_dropped_gedcom_families_session158",
  "_dropped_gedcom_change_log_session158"
]
```

## VACUUM FULL timings
```json
{}
```

## Pre-DROP top 25 tables
```json
[
  {
    "name": "_dropped_gedcom_individuals_session158",
    "size": "783 MB",
    "raw_bytes": 821256192
  },
  {
    "name": "gedcom_relationships",
    "size": "406 MB",
    "raw_bytes": 425771008
  },
  {
    "name": "_dropped_gedcom_change_log_session158",
    "size": "397 MB",
    "raw_bytes": 416284672
  },
  {
    "name": "gedcom_events",
    "size": "273 MB",
    "raw_bytes": 286449664
  },
  {
    "name": "gedcom_records",
    "size": "272 MB",
    "raw_bytes": 284917760
  },
  {
    "name": "gedcom_individuals_v2",
    "size": "267 MB",
    "raw_bytes": 279773184
  },
  {
    "name": "_dropped_gedcom_families_session158",
    "size": "75 MB",
    "raw_bytes": 78258176
  },
  {
    "name": "gedcom_families_v2",
    "size": "27 MB",
    "raw_bytes": 27975680
  },
  {
    "name": "gemini_api_calls",
    "size": "12 MB",
    "raw_bytes": 12443648
  },
  {
    "name": "gedcom_media_objects",
    "size": "8872 kB",
    "raw_bytes": 9084928
  },
  {
    "name": "gedcom_sources",
    "size": "6880 kB",
    "raw_bytes": 7045120
  },
  {
    "name": "relationships",
    "size": "6640 kB",
    "raw_bytes": 6799360
  },
  {
    "name": "date_labels",
    "size": "3928 kB",
    "raw_bytes": 4022272
  },
  {
    "name": "identities",
    "size": "2168 kB",
    "raw_bytes": 2220032
  },
  {
    "name": "comparison_results",
    "size": "1280 kB",
    "raw_bytes": 1310720
  },
  {
    "name": "photo_locations",
    "size": "1200 kB",
    "raw_bytes": 1228800
  },
  {
    "name": "photo_faces",
    "size": "1040 kB",
    "raw_bytes": 1064960
  },
  {
    "name": "audit_log",
    "size": "888 kB",
    "raw_bytes": 909312
  },
  {
    "name": "discovery_log",
    "size": "800 kB",
    "raw_bytes": 819200
  },
  {
    "name": "photos",
    "size": "664 kB",
    "raw_bytes": 679936
  },
  {
    "name": "face_gemini_alignments",
    "size": "616 kB",
    "raw_bytes": 630784
  },
  {
    "name": "identity_overrides",
    "size": "584 kB",
    "raw_bytes": 598016
  },
  {
    "name": "photo_communities",
    "size": "344 kB",
    "raw_bytes": 352256
  },
  {
    "name": "ml_proposals",
    "size": "296 kB",
    "raw_bytes": 303104
  },
  {
    "name": "gedcom_change_manifest",
    "size": "280 kB",
    "raw_bytes": 286720
  }
]
```

## Post-VACUUM top 25 tables
```json
[
  {
    "name": "gedcom_relationships",
    "size": "406 MB",
    "raw_bytes": 425771008
  },
  {
    "name": "gedcom_events",
    "size": "273 MB",
    "raw_bytes": 286449664
  },
  {
    "name": "gedcom_records",
    "size": "272 MB",
    "raw_bytes": 284917760
  },
  {
    "name": "gedcom_individuals_v2",
    "size": "267 MB",
    "raw_bytes": 279773184
  },
  {
    "name": "gedcom_families_v2",
    "size": "27 MB",
    "raw_bytes": 27975680
  },
  {
    "name": "gemini_api_calls",
    "size": "12 MB",
    "raw_bytes": 12443648
  },
  {
    "name": "gedcom_media_objects",
    "size": "8872 kB",
    "raw_bytes": 9084928
  },
  {
    "name": "gedcom_sources",
    "size": "6880 kB",
    "raw_bytes": 7045120
  },
  {
    "name": "relationships",
    "size": "6640 kB",
    "raw_bytes": 6799360
  },
  {
    "name": "date_labels",
    "size": "3928 kB",
    "raw_bytes": 4022272
  },
  {
    "name": "identities",
    "size": "2168 kB",
    "raw_bytes": 2220032
  },
  {
    "name": "comparison_results",
    "size": "1280 kB",
    "raw_bytes": 1310720
  },
  {
    "name": "photo_locations",
    "size": "1200 kB",
    "raw_bytes": 1228800
  },
  {
    "name": "photo_faces",
    "size": "1040 kB",
    "raw_bytes": 1064960
  },
  {
    "name": "audit_log",
    "size": "888 kB",
    "raw_bytes": 909312
  },
  {
    "name": "discovery_log",
    "size": "800 kB",
    "raw_bytes": 819200
  },
  {
    "name": "photos",
    "size": "664 kB",
    "raw_bytes": 679936
  },
  {
    "name": "face_gemini_alignments",
    "size": "616 kB",
    "raw_bytes": 630784
  },
  {
    "name": "identity_overrides",
    "size": "584 kB",
    "raw_bytes": 598016
  },
  {
    "name": "photo_communities",
    "size": "344 kB",
    "raw_bytes": 352256
  },
  {
    "name": "ml_proposals",
    "size": "296 kB",
    "raw_bytes": 303104
  },
  {
    "name": "gedcom_change_manifest",
    "size": "280 kB",
    "raw_bytes": 286720
  },
  {
    "name": "gedcom_versions",
    "size": "280 kB",
    "raw_bytes": 286720
  },
  {
    "name": "identity_communities",
    "size": "232 kB",
    "raw_bytes": 237568
  },
  {
    "name": "calibration_pairs",
    "size": "192 kB",
    "raw_bytes": 196608
  }
]
```
