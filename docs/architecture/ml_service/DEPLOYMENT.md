# ML Service Deployment Options

**Parent:** [ML_SERVICE.md](../ML_SERVICE.md)

## Option A: Railway Internal Service (Recommended Start)

Two Railway services in the same project. Internal networking (no public URL).

| Pro | Con |
|-----|-----|
| Simple deployment | Railway hobby plan limits |
| Internal networking | Shared resource pool |
| Same deploy workflow | Two services to manage |

**Cost:** ~$10-20/month additional (Railway Pro plan)

## Option B: Separate Cloud (GPU)

ML service on a GPU provider (RunPod, Lambda, Modal).

| Pro | Con |
|-----|-----|
| GPU available | Network latency |
| Independent scaling | More complex deployment |
| Cost-efficient for batches | Cold start issues |

**Cost:** ~$0.20-0.50/hour GPU, or ~$30-50/month reserved

## Option C: Serverless (Modal/Banana)

ML inference as serverless functions.

| Pro | Con |
|-----|-----|
| Scale to zero | Cold start (10-30s) |
| Pay per use | Complex deployment |
| No server management | Vendor lock-in |

**Cost:** ~$0.01-0.05 per inference call

## Recommendation

**Start with Option A** (Railway internal service). It is the simplest to
deploy and manage, uses the same workflow, and avoids network latency issues.
Migrate to Option B if GPU is needed for real-time inference or standalone
tool traffic exceeds Railway CPU capacity.

## Size Impact

| Component | Current (combined) | After (web only) | After (ML only) |
|-----------|-------------------|-------------------|------------------|
| Docker image | ~2.5 GB | ~500 MB | ~2.0 GB |
| RAM usage | ~600 MB | ~150 MB | ~500 MB |
| Startup time | ~15s | ~3s | ~12s |
| Deploy time | ~4 min | ~1 min | ~3 min |
