# Session 108 UX Brief: "Find This Person" Workflow

**Predecessor:** Session 107b assessment, COMPARE-001
**Date:** 2026-03-16

## The Story

David Fox (Nolan's dad's cousin) recognized "Jimmy Fields" (James Henry Fields) in an existing Fox Family archive photo. Nolan wanted to verify by uploading known James Fields photos and seeing if the ML could match him against existing faces.

The compare tool has been unreliable, so Nolan uploaded directly to the Fox Family archive — intending the "find this person" workflow. But the upload pipeline failed to create identities for the detected faces, and local clustering couldn't run because embeddings weren't synced.

## Ideal "Find This Person" Flow

1. User navigates to community archive (e.g., Fox Family)
2. Clicks "Find Someone" or uses community-scoped Compare
3. Uploads a reference photo of the person they're looking for
4. System runs face detection → matches against ALL faces in that community
5. Shows: "We found X possible matches" with confidence scores
6. If found: links to the identity/photo where they appear
7. If not found: "No matches found. Add this photo to the archive?" → upload flow

This is essentially Compare but **community-scoped** with an **archive-add fallback**.

## Current State

- Compare tool exists at `/tools/compare` but is not community-scoped
- Upload works but has reliability issues (6+ failures documented)
- ML matching works but requires local pipeline or on-device models
- No "find someone" entry point from the community page

## Dependencies

- **TOOLS-002** (ML Service): For real-time embedding generation on Railway
- **COMPARE-001**: Full compare UX rebuild
- OR: Could work with existing on-device ML if server has InsightFace loaded

## BACKLOG Reference

- **COMPARE-002**: Community-scoped compare with archive-add fallback
- **TOOLS-003**: Face Compare Real-Time (depends on TOOLS-002)
