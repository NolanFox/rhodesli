# Collection Data Misassignment (114 Photos)

Date: 2026-02-17
Severity: Critical

## What Happened

114 community-submitted photos were assigned to a generic "Community Submissions" collection instead of their proper collection ("Jews of Rhodes: Family Memories & Heritage"). This made the photos appear disorganized and broke collection-based browsing and filtering.

## Root Cause

The Session 26 batch ingest of 116 community photos used a generic default collection name without per-source differentiation. All community photos were lumped into "Community Submissions" regardless of their actual origin (Facebook group contributions).

## Which Session Introduced It

Session 26 (ML Phase 2: Scale-Up Labeling + Tooling), which processed 116 community photos in bulk.

## Why Tests Didn't Catch It

No test existed to validate collection assignment correctness during batch ingestion. Tests verified that photos were ingested successfully (face detection, embedding generation) but did not assert the collection field matched the photo source.

## Fix Applied

Manually reassigned 114 photos from "Community Submissions" to "Jews of Rhodes: Family Memories & Heritage" collection with source set to "Facebook". The reassignment was done via a data correction script.

## Prevention Added

Batch ingest rules now require an explicit collection per photo rather than relying on a generic default. `scripts/verify_data_integrity.py` includes checks for collection counts and flags unexpected collection names. The data integrity checker runs as part of the post-session verification workflow.
