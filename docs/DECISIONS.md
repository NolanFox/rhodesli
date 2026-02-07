# Rhodesli Decisions Log

**Last updated:** 2026-02-06

All major architectural decisions, finalized during the system design session on 2026-02-05.

---

## Deployment Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Hosting platform | **Railway** | Simple Python deployment, persistent disk, GitHub integration |
| URL | **rhodesli.nolanandrewfox.com** (subdomain) | Simpler DNS setup than subdirectory; CNAME via Cloudflare |
| DNS provider | **Cloudflare** | Already in use, free SSL, DDoS protection, R2 for photo storage |
| Photo storage | **Cloudflare R2** | Too large for Docker image (~255MB); R2 has no egress fees |
| Budget | **Railway hobby (~$5-20/mo) + Supabase free + R2 free** | Sufficient for expected scale |
| Deploy method | **Git push to main** | Railway auto-deploys from GitHub; `railway up` for manual deploys |

---

## Authentication Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Auth provider | **Supabase Auth** | Managed auth with OAuth + email/password; free tier sufficient |
| Auth model | **Invite-only for V1** | More controlled, less spam risk, appropriate for small community |
| OAuth providers | **Google only** | Facebook requires Business Verification (impractical for small project) |
| Browsing access | **Fully public** | No login required to browse/search; auth only for data modifications |
| Email service | **Supabase built-in** (custom SMTP planned) | Free, quick setup; Resend integration documented for upgrade |
| Session storage | **httpOnly cookies** | XSS protection; JWTs not stored in localStorage |
| HTMX auth pattern | **Return 401 (not 303)** | HTMX silently follows redirects; 401 intercepted by beforeSwap |
| Data modification default | **Admin-only** | All POST routes use `_check_admin`; loosen only when guardrails exist |

---

## Feature Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Canonical data format | **JSON files** (not Postgres) | Simple, version-controlled, sufficient for scale |
| Community data | **Postgres via Supabase** (planned) | Needed for multi-user annotations; free tier sufficient |
| Activity log migration | **Yes, migrate existing logs** (planned) | Preserves historical attribution |
| Backup strategy | **Cloudflare R2** | Already using Cloudflare; S3-compatible, no egress fees |
| ML processing | **Local only** | Never on server; `PROCESSING_ENABLED=false` in production |
| Face detection | **No generative AI** | Forensic matching only (AdaFace/InsightFace) |

---

## Technical Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Framework | **FastHTML** | Python-native, inline HTML, HTMX integration |
| Embeddings format | **NumPy .npy** (pickled dicts) | Simple, fast load, compact |
| Photo IDs | **SHA256(filename)[:16]** | Deterministic, collision-resistant at current scale |
| Face IDs | **filename:faceN** (legacy) or **inbox_hex** (new) | Both formats coexist |
| Atomic writes | **temp file + rename with portalocker** | Prevents corruption on concurrent access |
| Path resolution | **`Path(__file__).resolve().parent`** | Portable across environments |

---

## Remaining Open Items

- **Exact initial invite list:** Names of 5-10 community members for first wave (user to provide)
- **Custom SMTP setup:** Resend integration documented in `docs/SMTP_SETUP.md` but not yet configured
- **Backup automation:** R2 backup script planned but not yet implemented
- **Contributor role implementation:** Three-tier permission model designed but not built
