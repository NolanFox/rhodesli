# Rhodesli Architecture Overview

**Last updated:** 2026-02-06

Rhodesli is a family photo archive with ML-powered face detection. It runs as a FastHTML web application deployed on Railway, with photos served from Cloudflare R2.

**Live site:** `rhodesli.nolanandrewfox.com`

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase A: Deployment | COMPLETE |
| Phase B: Authentication | COMPLETE (Google OAuth + email/password) |
| Phase C: Annotations | NOT STARTED |
| Phase D: Photo Upload Queue | NOT STARTED |
| Phase E: Admin Dashboard | NOT STARTED |
| Phase F: Polish & Security | NOT STARTED |

**Data at a glance:**
- 124 photos across 4 collections
- 292 identities (23 confirmed, 181 proposed, 88 inbox)
- ~550 face embeddings (512-dim PFE vectors)
- Collections: Vida Capeluto NYC, Betty Capeluto Miami, Nace Capeluto Tampa, Newspapers.com

---

## Architecture Diagram

```
                    rhodesli.nolanandrewfox.com
                              |
                    +-------------------+
                    |   Cloudflare DNS  |
                    |   (proxied CNAME) |
                    +-------------------+
                              |
                    +-------------------+
                    |   Railway         |
                    |   Docker + Volume |
                    +-------------------+
                      |             |
            +---------+       +----------+
            |                 |
   +------------------+   +------------------+
   | Layer 1:         |   | Layer 3:         |
   | Canonical Data   |   | Users            |
   | (Railway volume) |   | (Supabase Auth)  |
   |                  |   |                  |
   | identities.json  |   | Google OAuth     |
   | photo_index.json |   | Email/password   |
   | embeddings.npy   |   | Session cookies  |
   +------------------+   +------------------+
            |
   +------------------+
   | Cloudflare R2    |
   | (photo storage)  |
   |                  |
   | raw_photos/      |
   | crops/           |
   +------------------+
```

Layer 2 (Community Annotations via Postgres) is planned but not yet implemented. See `docs/design/FUTURE_COMMUNITY.md`.

---

## Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Framework | FastHTML (Python) | Inline HTML generation, no templates |
| Styling | Tailwind CSS (CDN) | JIT compilation |
| Interactivity | HTMX + Hyperscript | Declarative DOM updates |
| Server | Uvicorn | ASGI server |
| Data I/O | JSON + NumPy | Atomic writes with portalocker |
| Auth | Supabase Auth | Google OAuth + email/password |
| Hosting | Railway | Docker, persistent volume |
| Photos | Cloudflare R2 | Public bucket, no egress fees |
| DNS/SSL | Cloudflare | Proxied CNAME, free SSL |

The entire UI lives in `app/main.py` (~6000 lines) as Python functions that return FastHTML elements. There are no separate template files.

---

## Memory Footprint

| Component | Current Size | At 10,000 faces |
|-----------|-------------|-----------------|
| Embeddings (RAM) | ~2.3 MB (547 faces) | ~42 MB |
| JSON registry (RAM) | ~500 KB | ~2 MB |
| Total startup | < 10 MB | < 50 MB |

Railway hobby plan includes 512 MB RAM. Well within limits at current and projected scale.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastHTML web app (routes, UI, data loading) |
| `app/auth.py` | Supabase auth integration, User model, permission helpers |
| `core/storage.py` | Photo/crop URL generation (local vs R2 mode) |
| `data/identities.json` | Identity metadata, face assignments, states |
| `data/photo_index.json` | Photo metadata, face-to-photo mapping |
| `data/embeddings.npy` | Face embeddings (NumPy array of dicts) |
| `Dockerfile` | Production container build |
| `scripts/init_railway_volume.py` | First-run data seeding for Railway |
