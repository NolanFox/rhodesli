# Session 91 Planning Context

**Predecessor**: Session 90c (Gemini prompt fix, face alignment timestamp, flaky test cleanup)
**Prompt**: `docs/prompts/session-91-prompt.md`
**Date**: 2026-03-06 (updated)
**Origin**: PRD backlog audit — 4 PRDs written but not implemented. Nolan directed: ship all of them.

## Scope Expansion (2026-03-06)

Original session 91 plan focused on Postgres migration + platform foundation (GlobalPersonID, Sentry, PostHog). After PRD audit, Nolan directed: ship the PRD backlog AND the platform foundation — don't defer anything.

**Added to original scope:**
- PRD-028: Contributor Notifications (P0 — growth loop fix, Claude Benatar feedback)
- PRD-011: Life Events & Context Graph (flesh out stub + implement)
- PRD-029: Photo Backs completion (remaining work from Session 90b)

**Kept from original scope:**
- PRD-027 Phase A: R2 nightly backup (data safety)
- PRD-027 Phases B/C: Full Postgres migration + read flip
- GlobalPersonID / multi-tenant schema
- Sentry + PostHog + structlog observability

**Result**: 6 parallel worktree tracks covering all user-facing PRDs + platform foundation. ML service extraction remains future work (requires separate Railway service).

---

## Origin: Strategic Architecture Conversation

Nolan had a detailed conversation with Claude about the future of Rhodesli. Key takeaways:

### Why Railway (Not Vercel)
- Rhodesli runs InsightFace (native C/C++ extensions), background ML jobs, persistent server processes
- Vercel's serverless model (250MB limit, 10s timeout, no persistent processes) is wrong for ML inference
- Railway is correct until ML is extracted to its own service, at which point the web layer could move anywhere
- Personal site (nolanandrewfox.com) uses Vercel (lightweight FastHTML portfolio)

### Multi-Collection Vision
Nolan wants to support multiple photo collections (different families, communities) with cross-collection person linking. The progression:

1. **Now**: Single Railway app, single community (Rhodes)
2. **Next community**: Add multi-tenancy; community = config + scoped DB
3. **3+ communities**: Extract ML inference to standalone service; web layer could move to Vercel
4. **Real scale**: Evaluate managed K8s (Fly.io, Railway Machines, GCP Cloud Run)

### Seven Growth Areas (Nolan's Priorities)

1. **Standalone tooling** — Gemini geo/time/age estimation as separate product/API. Most differentiated offering.
2. **Chatbot research interface** — NL queries over the combined photo+GEDCOM graph. "Show me photos of women from Rhodes in their 30s around 1930."
3. **ML improvements** — Custom modeling, ML service extraction, reduce local ML dependency.
4. **UX/UI modernization** — Move from "developer tool" to "living archive." Narrative-first, not search-first.
5. **Infrastructure** — Analytics (PostHog), error tracking (Sentry), API logging, structured logging.
6. **Multi-collection support** — (a) Bring in Fox family photo collection, (b) link overlapping people (e.g., Roland Fox in both Rhodes and Fox collections).
7. **Platform vision** — Upload any photo, search all collections for matches. GlobalPersonID linking.

### GlobalPersonID Architecture (from conversation)

Within a collection: `person_id` links confirmed face embeddings to a named individual.
Across collections: `global_person_id` links the same individual across collections.

Three linking mechanisms:
1. **Genealogical linking** — GEDCOM data identifies same person across trees (highest confidence)
2. **ML similarity proposals** — Cross-collection embedding similarity surfaced for admin review (Gatekeeper)
3. **Human confirmation** — Admin explicitly confirms "person A in Collection X = person B in Collection Y"

**V1**: No cross-linking required. But schema should include nullable `global_person_id` FK now. Migration cost if added later is high.

### Recommended Sequencing (from conversation)

1. Fix P0 bugs (ongoing)
2. UX/emotional redesign
3. **Schema for GlobalPersonID** — low cost now, very high cost later
4. **Extract ML to standalone service** — architectural pivot unlocking everything
5. **Second collection onboarding** (Fox family) — validates multi-tenant
6. Cross-collection matching as proposal flow
7. Chatbot research interface
8. Standalone geo/time/age estimation tooling

---

## Research: Sentry Integration

### Setup for FastHTML/ASGI
```python
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

sentry_sdk.init(
    dsn="___PUBLIC_DSN___",
    send_default_pii=True,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)
app = SentryAsgiMiddleware(app)
```

### Pricing
- **Free tier**: 5K errors, 10K performance events, 50 replays/month
- **Team plan**: $26/month for more volume
- Railway: Set `SENTRY_DSN` environment variable, `SENTRY_ENVIRONMENT=production`
- Privacy: Set `send_default_pii=False` for heritage/genealogy app (faces, names are PII)

### Recommendation
Start with free tier. Add `sentry-sdk` to requirements.txt, wrap app in middleware, set DSN on Railway. ~30 min work.

---

## Research: PostHog Analytics

### Free Tier
- 1M events/month, 5K session recordings, 1M feature flag requests, 100K error events, 1.5K survey responses
- More than enough for Rhodesli's traffic (~100-500 users/month)

### Integration for HTMX/SSR App
- **Client-side**: Add PostHog JS snippet to base HTML template (single `<script>` tag)
- **Server-side**: `posthog-python` SDK for tracking events from Python backend
- No React required — works with any HTML page

### Self-Hosted vs Cloud
- Self-hosting costs $5,000-15,000/month (ClickHouse, Kafka, Postgres maintenance)
- Cloud free tier is more than sufficient for Rhodesli
- **Decision: Use PostHog Cloud** (free tier)

### Privacy Considerations for Heritage App
- Disable session recordings initially (faces in photos = PII)
- Use PostHog's respect_dnt flag
- Only track navigation events, not content
- Consider adding consent banner before enabling analytics

---

## Research: Structured Logging

### Current State
- App uses stdlib `logging` module throughout
- `app/supabase_data.py` uses `logger = logging.getLogger(__name__)`
- Gemini API calls already logged to Supabase `gemini_api_calls` table

### Options
| Library | Pros | Cons |
|---------|------|------|
| **structlog** | Native JSON output, processor chains, integrates with stdlib | More config needed |
| **loguru** | Easiest setup, good DX | Doesn't integrate as cleanly with existing stdlib loggers |
| **stdlib** | Already in use, no new dependency | No structured JSON without third-party formatter |

### Recommendation
**structlog** — integrates with existing stdlib logging, adds JSON output for production (human-readable for dev). Can be adopted incrementally (wrap existing loggers). Enables shipping logs to external services later.

---

## Research: Multi-Tenant Architecture

### Postgres Row-Level Security (RLS)
- Add `community_id` column to every table
- Supabase natively supports RLS policies
- `SET app.current_community = 'rhodes'` per session
- Policies: `USING (community_id = current_setting('app.current_community'))`
- Performance: Complex RLS can slow queries — keep policies simple

### R2 Organization
- Option A: Per-community prefix (`rhodes/raw_photos/`, `fox/raw_photos/`)
- Option B: Separate R2 buckets per community
- **Recommendation**: Per-community prefix in same bucket (simpler, cheaper)

### Schema Proposal: GlobalPersonID
```sql
-- Communities table
CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,  -- 'rhodes', 'fox-family'
    name TEXT NOT NULL,
    description TEXT,
    admin_emails TEXT[],
    r2_prefix TEXT NOT NULL,  -- 'rhodes/', 'fox/'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Community-scoped persons (extends existing identities)
ALTER TABLE identities ADD COLUMN community_id UUID REFERENCES communities(id);
ALTER TABLE photos ADD COLUMN community_id UUID REFERENCES communities(id);

-- Global person links (cross-community)
CREATE TABLE global_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_person_id UUID NOT NULL,  -- groups same person across communities
    community_id UUID NOT NULL REFERENCES communities(id),
    identity_id UUID NOT NULL,  -- community-local identity
    link_type TEXT NOT NULL,  -- 'gedcom', 'ml_proposal', 'human_confirmed'
    confidence NUMERIC(5,4),
    linked_by TEXT,  -- admin email or 'system'
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(community_id, identity_id)
);

CREATE INDEX idx_gpl_global ON global_person_links(global_person_id);
CREATE INDEX idx_gpl_identity ON global_person_links(identity_id);
```

### ML Embedding Space
- **Single shared embedding space** across all communities
- More ground truth data = better models
- Cross-community matches become possible via vector similarity
- pgvector extension enables in-database similarity search

---

## Research: ML Service Extraction

### InsightFace-REST (Reference Implementation)
- GitHub: SthPhoenix/InsightFace-REST — production-ready FastAPI service
- TensorRT optimizations provide 3x performance over MXNet
- Endpoints: `/extract` (detect + embed), `/draw` (visualize), `/aliveness`
- ONNX Runtime backend (insightface>=0.2)
- Msgpack serializer reduces embedding network traffic by ~2x

### vision-fr (Alternative)
- GitHub: ruhyadi/vision-fr — ONNX + pgvector + FastAPI
- YOLOx detection + InsightFace recognition
- PostgreSQL with pgvector for vector search

### Proposed API Design for Rhodesli ML Service
```
POST /api/v1/embed     — Upload photo, return face embeddings + bboxes
POST /api/v1/compare   — Compare two faces (embedding vectors or photo uploads)
POST /api/v1/search    — Find nearest neighbors in embedding index
POST /api/v1/cluster   — Run clustering on a set of embeddings
GET  /api/v1/health    — Health check + model version
```

### Deployment
- Separate Railway service (or Fly.io for GPU)
- ONNX Runtime CPU for inference (no GPU needed at current scale)
- Share embedding space via pgvector in Supabase
- Web app calls ML service via HTTP (replaces in-process InsightFace)

---

## Research: Comparable Platforms

### Civil War Photo Sleuth (CWPS)
- 50,000+ images, largest digitized Civil War portrait archive
- Face recognition maps 27 facial landmarks
- **Key lesson**: Human-AI collaboration is central — face recognition narrows possibilities, humans make final decisions (matches Rhodesli Gatekeeper pattern)
- Profile views and B&W/sepia photos challenge modern face recognition systems
- NSF-funded, launched 2018 at National Archives

### Historypin
- 60,000+ individuals/groups, 2,500+ institutions, projects in 75+ countries
- Historical photos pinned to maps with Google Street View overlays
- **Key lesson**: Strongest when working with local organizations, not individual users. Organizations do outreach and training; platform supports them.
- Open collections model (anyone can contribute to anyone's collection)
- Noted difference between institutional voice (neutral, objective) and personal voice (subjective) in descriptions

### Implications for Rhodesli
- CWPS validates the Gatekeeper pattern (ML proposes, humans decide)
- Historypin suggests partnering with organizations (Rhodes community groups, synagogues) rather than targeting individuals
- Both platforms emphasize that context > raw recognition accuracy

---

## Current Supabase State (What's Already Migrated)

### In Supabase (source of truth)
| Table | Records | Since |
|-------|---------|-------|
| `identity_overrides` | ~100+ user-modified identities | Session 59C |
| `annotations` | ~50+ community annotations | Session 59C |
| `relationships` | ~1,019 person-to-person | Session 59C |
| `gedcom_matches` | ~56 GEDCOM match decisions | Session 65b |
| `gedcom_individuals` | ~21,809 family tree people | Session 63 |
| `gedcom_relationships` | ~145,574 GEDCOM family rels | Session 63 |
| `gedcom_events` | ~40,140 life events | Session 63 |
| `gedcom_versions` | ~2 file versions | Session 65d |
| `gedcom_enrichment_queue` | variable | Session 65d |
| `gedcom_face_links` | ~61 identity-GEDCOM links | Session 63 |
| `face_gemini_alignments` | ~270 Gemini alignment results | Session 64 |
| `gemini_api_calls` | ~500+ API call audit log | Session 64 |

### NOT in Supabase (still JSON on Railway volume)
| File | Records | Risk |
|------|---------|------|
| `identities.json` | ~777 identities | HIGH — admin changes lost between deploys |
| `photo_index.json` | ~296 photos, ~982 faces | HIGH — new uploads lost |
| `embeddings.npy` | ~1,182 embeddings | HIGH — re-detection produces different face IDs |
| `date_labels.json` | ~100+ labels | MEDIUM — regenerable at cost |
| `photo_locations.json` | ~270 entries | MEDIUM — regenerable at cost |
| `birth_year_estimates.json` | ~200+ entries | LOW — ML output, regenerable |

### Migration Path (building on PRD-027)
Session 90b starts shadow writes (Option B from PRD-027). Session 91 completes the full migration:

1. **Session 90b**: Create Supabase tables + shadow write functions + backfill script
2. **Session 91**: Flip read path to Postgres, add `community_id` column, add GlobalPersonID schema
3. **Session 92+**: Second collection onboarding, ML service extraction

---

## Key Files to Read at Session Start

| File | Purpose |
|------|---------|
| `docs/prds/027_data_migration.md` | Migration options + recommendation |
| `app/supabase_data.py` | Existing Supabase integration (580 lines) |
| `core/registry.py` | IdentityRegistry (load/save from JSON) |
| `core/photo_registry.py` | PhotoRegistry (load/save from JSON) |
| `scripts/sql/create_face_gemini_alignments.sql` | Existing SQL table schema |
| `scripts/sql/create_gemini_api_calls.sql` | Existing SQL table schema |
| `scripts/migrate_to_supabase.py` | Existing migration script |
| `scripts/supabase_migration_001.sql` | First Supabase migration |

---

## Existing Codebase References

### Multi-tenant / hardcoding
- `ARCH-001` in BACKLOG: 171 references to "Rhodes/Jewish/Ladino/Sephardic" in app/main.py
- `GEN-001+` in ROADMAP: Multi-tenant architecture (if traction)

### Data migration items
- `DATA-005` through `DATA-007` in BACKLOG cover the migration phases
- `BE-040-042` in FEATURE_STATUS: PostgreSQL migration

### ML service
- `AD-007/AD-110`: No ML deps in production / serving path contract
- `COMPARE-002`: Real-time compare blocked by no ML in production
- `PRODUCT-002`: Face Compare Tier 2 shared backend architecture

---

## Breadcrumbs

- **Predecessor context**: `docs/session_context/session-90b-context.md`
- **Data migration PRD**: `docs/prds/027_data_migration.md`
- **BACKLOG**: `docs/BACKLOG.md` — DATA-005/006/007, GEN-001, ARCH-001
- **ROADMAP**: Phase F (Scale & Generalize)
- **Architecture conversation**: Preserved in this context file (Origin section)
