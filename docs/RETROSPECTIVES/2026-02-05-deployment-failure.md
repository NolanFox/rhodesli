# Retrospective: Railway Deployment Failure

**Date:** 2026-02-05
**Duration of debugging:** ~4 hours
**Root cause:** Architectural — photos bundled in Docker image exceeded platform limits

## What Happened

1. Built elaborate deployment infrastructure (Dockerfile, init scripts, volume management)
2. Discovered Railway couldn't handle 255MB photo uploads
3. Spent hours on symptoms: gitignore, railwayignore, init script markers
4. Eventually realized photos need external storage, not Docker bundling

## Why It Wasn't Caught Earlier

### 1. No Platform Constraint Research

We never asked: "What are Railway's upload/build limits?"

A 5-minute check of Railway docs would have revealed the constraint. The system design doc mentioned R2 as an option but didn't research when it would be necessary.

### 2. No Deployment Spike

We built the full deployment pipeline without testing a minimal "can I deploy 200MB of assets?" experiment. Spikes validate assumptions cheaply.

A 10-minute test deploying a dummy app with 250MB of static files would have revealed:
- Railway CLI has upload size limits
- Even if upload works, build times become problematic
- This architecture fundamentally doesn't scale

### 3. Feature-Focused Planning

The system design doc covered auth, annotations, roles in detail (1300+ lines). Deployment was treated as "we'll figure it out" — the hard problem was dismissed.

Specifically, Section 3.1 mentioned:
> **Option C: Bundle data into Docker image** — Only works for read-only data

But this wasn't validated. The docs showed we *considered* alternatives but didn't establish *when* to use them.

### 4. Local Dev Parity Fallacy

"It works locally" doesn't mean it works in production. Different environments have different constraints:

| Local | Railway |
|-------|---------|
| No upload limit | ~100MB upload limit |
| Fast builds | Network-bound builds |
| Filesystem always available | Volumes need configuration |
| No cost constraints | Storage costs scale |

We never explicitly listed these differences.

### 5. Symptom Chasing

Each "fix" felt like progress but addressed symptoms, not the root cause:

| Fix Attempted | Actual Effect |
|--------------|---------------|
| Update .gitignore | Moved the problem |
| Create .railwayignore | Moved the problem again |
| Add init script markers | Made failure more graceful |
| Add --no-gitignore flag | Worked briefly, then hit size limits |

After 30 minutes of symptom chasing, we should have stepped back to question the architecture.

## What We Should Have Done

1. **Research platform limits first** — Before writing any deployment code
2. **Run a deployment spike** — Deploy a dummy app with 200MB of assets
3. **Separate concerns explicitly** — Ask "where does each asset type live?"
4. **Document assumptions** — "We assume Railway can handle 255MB uploads"
5. **Validate assumptions before building** — Test the assumption, then build

## The Correct Architecture

```
Photos (255MB) → Cloudflare R2 (object storage)
JSON Data (5MB) → Railway Volume (persistent storage)
Code (~10MB)    → Docker Image (ephemeral)
```

Binary media assets don't belong in Docker images. This is a well-known pattern we should have recognized immediately.

## Lessons for Future

1. **When targeting a new platform, research its constraints FIRST**
2. **Do deployment spikes before building deployment infrastructure**
3. **Large binary assets (photos, videos, ML models) almost never belong in Docker**
4. **If debugging takes >30 minutes, step back and question the architecture**
5. **Document assumptions explicitly so they can be validated**
6. **The "obvious" path (bundle everything) is often wrong for production**

## Action Items

- [x] Create this retrospective
- [ ] Add deployment architecture rules to CLAUDE.md
- [ ] Add pre-deployment checklist to deployment guide
- [ ] Implement R2 storage for photos
- [ ] Document the correct architecture for future reference

## References

- System design doc: `docs/SYSTEM_DESIGN_WEB.md` (Section 3.1 mentions R2)
- Railway pricing: https://railway.app/pricing
- Cloudflare R2 docs: https://developers.cloudflare.com/r2/
