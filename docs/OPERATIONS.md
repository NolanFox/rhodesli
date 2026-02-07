# Rhodesli Operations Runbook

Day-to-day operational guide for managing the deployed Rhodesli application.

**Related docs:**
- `docs/DEPLOYMENT_GUIDE.md` — Initial Railway setup
- `docs/architecture/OVERVIEW.md` — Architecture overview
- `docs/DECISIONS.md` — Architecture decisions
- `CLAUDE.md` — Project conventions

---

## 1. Data Architecture

### 1.1 Where Data Lives

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOCAL MACHINE (Mac)                              │
│   Your computer — where ML processing happens                            │
│                                                                          │
│   rhodesli/                                                              │
│   ├── data/                    ← CANONICAL DATA (source of truth)        │
│   │   ├── identities.json      Face-identity assignments, states         │
│   │   ├── photo_index.json     Photo metadata, sources                   │
│   │   ├── embeddings.npy       Face vectors (547 faces × 512-dim)        │
│   │   ├── file_hashes.json     SHA256 hashes for deduplication           │
│   │   ├── backups/             Automatic JSON backups                    │
│   │   ├── uploads/             Processed inbox uploads                   │
│   │   └── staging/             [Empty locally — production only]         │
│   │                                                                      │
│   └── raw_photos/              ← SOURCE PHOTOGRAPHS (112 files, 255MB)   │
│       ├── Image_001.jpg                                                  │
│       ├── Family_Photo_1952.jpg                                          │
│       └── ...                                                            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │  git push (code only)
                    │  railway CLI (data sync)
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      RAILWAY (Production)                                │
│   rhodesli.nolanandrewfox.com                                            │
│                                                                          │
│   Docker Container                                                       │
│   ├── /app/data/              ← RAILWAY VOLUME (persistent)              │
│   │   ├── identities.json      [Synced from local]                       │
│   │   ├── photo_index.json     [Synced from local]                       │
│   │   ├── embeddings.npy       [Synced from local]                       │
│   │   ├── staging/             ← CONTRIBUTOR UPLOADS LAND HERE           │
│   │   │   └── {job_id}/                                                  │
│   │   │       ├── photo1.jpg                                             │
│   │   │       └── _metadata.json                                         │
│   │   └── ...                                                            │
│   │                                                                      │
│   └── /app/raw_photos/        ← RAILWAY VOLUME (persistent)              │
│       └── [synced from local]                                            │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │  [FUTURE: Phase F]
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CLOUDFLARE R2 (Backup)                              │
│   Daily automated backups of JSON + embeddings                           │
│   [NOT YET IMPLEMENTED — Phase F]                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data File Reference

| File | Size | Purpose | Changes When |
|------|------|---------|--------------|
| `identities.json` | 434 KB | Identity metadata, face assignments, states (INBOX/CONFIRMED/REJECTED) | Admin confirms/rejects, faces merge/detach, names change |
| `photo_index.json` | 51 KB | Photo metadata: paths, face_ids, sources | New photos ingested, sources updated |
| `embeddings.npy` | 2.3 MB | 547 face vectors (512-dim PFE embeddings) | New photos ingested (append-only) |
| `file_hashes.json` | 5 KB | SHA256 hashes for deduplication | New photos ingested |
| `identities.lock` | 0 B | Write lock for concurrent access | Created/deleted during writes |
| `embeddings.lock` | 0 B | Write lock for embeddings | Created/deleted during writes |

### 1.3 What's Where: JSON vs Postgres

| Data Type | Current (Phase A) | Future (Phase B+) |
|-----------|-------------------|-------------------|
| **Identities** | `identities.json` | `identities.json` (canonical) |
| **Photos** | `photo_index.json` | `photo_index.json` (canonical) |
| **Face vectors** | `embeddings.npy` | `embeddings.npy` (canonical) |
| **User accounts** | N/A | Supabase Auth |
| **Annotations** | N/A | Supabase Postgres |
| **Activity log** | N/A | Supabase Postgres |
| **Invites** | N/A | Supabase Postgres |

**Key principle:** JSON files = canonical truth (admin-controlled). Postgres = community layer (user contributions awaiting moderation).

---

## 2. Processing New Photos

### 2.1 Prerequisites

Ensure ML dependencies are installed locally:
```bash
source venv/bin/activate
pip install -r requirements-local.txt  # torch, insightface, opencv
```

### 2.2 Step-by-Step: Add Photos Locally

**Step 1: Add photos to raw_photos/**
```bash
# Copy photos to the source directory
cp ~/Downloads/new_family_photo.jpg raw_photos/

# Or for multiple photos
cp ~/Downloads/batch/*.jpg raw_photos/
```

**Step 2: Run ingestion pipeline**
```bash
# Activate venv
source venv/bin/activate

# Process a single photo
python -m core.ingest_inbox --file raw_photos/new_family_photo.jpg --source "Smith Family Collection"

# Process a directory
python -m core.ingest_inbox --directory raw_photos/batch/ --source "Reunion 2025"
```

**Step 3: Verify results**
```bash
# Check the web UI
python app/main.py
# Visit http://localhost:5001
# New faces should appear in Inbox section

# Or check data directly
python -c "
import json
with open('data/identities.json') as f:
    data = json.load(f)
inbox = [i for i in data['identities'].values() if i['state'] == 'INBOX']
print(f'Inbox identities: {len(inbox)}')
"
```

**Step 4: Review and triage**
- Open http://localhost:5001
- Review new faces in Inbox
- Confirm, skip, or reject as appropriate
- Use "Find Similar" to merge duplicates

### 2.3 What Changes After Ingestion

| File | Change |
|------|--------|
| `identities.json` | New identity entries added (state=INBOX) |
| `photo_index.json` | New photo entry with face_ids |
| `embeddings.npy` | New face vectors appended |
| `file_hashes.json` | New SHA256 hash entry |
| `app/static/crops/` | New face thumbnail images |

---

## 3. Syncing Local ↔ Production

### 3.1 Push Local Changes to Production

**When:** You've processed new photos locally and want them live.

```bash
# 1. Verify local state is good
python app/main.py  # Check UI works
curl http://localhost:5001/health

# 2. Connect to Railway
railway link  # If not already linked

# 3. Copy data files to Railway volume
# Option A: Use railway shell
railway shell
# Then inside the shell:
# exit

# Option B: Use rsync via Railway's deploy (redeploy with new data)
# This reseeds from the Docker image bundle
git add data/identities.json data/photo_index.json data/embeddings.npy
git commit -m "data: sync updated identities and photos"
git push origin main
# Railway auto-redeploys, init script copies bundled data

# Option C: Railway CLI file copy (if available)
railway run -- cat - > /app/data/identities.json < data/identities.json
```

**Note:** Option B (redeploy) is the simplest but requires committing data to git temporarily. For frequent syncs, consider setting up a dedicated sync script.

### 3.2 Pull Production Changes to Local

**When:** Admin actions were taken on web UI, or you need the latest state.

```bash
# Pull data from Railway
railway run -- cat /app/data/identities.json > data/identities.json
railway run -- cat /app/data/photo_index.json > data/photo_index.json

# Embeddings are binary, use base64
railway run -- base64 /app/data/embeddings.npy > /tmp/embeddings.b64
base64 -d /tmp/embeddings.b64 > data/embeddings.npy
```

### 3.3 Pull Staged Contributor Uploads

**When:** Contributors have uploaded photos via web UI (Phase C+).

```bash
# List staged uploads
railway run -- ls -la /app/data/staging/

# For each job directory, download files
railway run -- tar -cz /app/data/staging/{job_id} > staging_{job_id}.tar.gz
tar -xzf staging_{job_id}.tar.gz

# Process locally
python -m core.ingest_inbox --directory staging/{job_id}/ --source "Contributor Upload"

# Clean up staging on Railway after processing
railway run -- rm -rf /app/data/staging/{job_id}
```

### 3.4 Nuclear Option: Full Reseed

**When:** Production data is corrupt or you want to start fresh from local.

```bash
# 1. Delete the .initialized marker
railway run -- rm /app/data/.initialized

# 2. Redeploy (init script will recopy from Docker bundle)
railway up

# Or if you've updated the bundle:
git add data/
git commit -m "data: full reseed"
git push origin main
```

---

## 4. Handling Contributor Uploads (Phase C+)

**Status: NOT YET IMPLEMENTED**

When the community contribution workflow is built (Phase C), here's how it will work:

### 4.1 Upload Flow

1. Contributor visits `/upload` page
2. Selects photos and enters source/collection info
3. Files uploaded to Railway → stored in `/app/data/staging/{job_id}/`
4. UI shows "Pending admin review and processing"
5. Admin receives notification (Phase C: email or dashboard)

### 4.2 Admin Processing Workflow

```bash
# 1. Check for pending uploads
railway run -- ls /app/data/staging/

# 2. Download to local
railway run -- tar -cz /app/data/staging/ > all_staged.tar.gz
tar -xzf all_staged.tar.gz

# 3. Review metadata
cat staging/*/metadata.json

# 4. Process approved uploads
for dir in staging/*/; do
    python -m core.ingest_inbox --directory "$dir" --source "$(jq -r .source $dir/_metadata.json)"
done

# 5. Push updated data to production
# [See section 3.1]

# 6. Clean up staging
railway run -- rm -rf /app/data/staging/*
```

---

## 5. Backup & Recovery

### 5.1 Current Backup Strategy (Phase A)

**Automatic:** None yet. Manual backups only.

**Manual backup procedure:**
```bash
# Create timestamped backup
mkdir -p backups/$(date +%Y%m%d)
cp data/identities.json backups/$(date +%Y%m%d)/
cp data/photo_index.json backups/$(date +%Y%m%d)/
cp data/embeddings.npy backups/$(date +%Y%m%d)/

# Or tar everything
tar -czvf backups/rhodesli-$(date +%Y%m%d).tar.gz data/ raw_photos/
```

### 5.2 Future: R2 Automated Backups (Phase F)

**Status: NOT YET IMPLEMENTED**

Plan:
- Daily cron job uploads JSON + embeddings to Cloudflare R2
- 30-day retention
- Versioned backups with timestamps

### 5.3 Recovery Procedures

**Restore from local backup:**
```bash
# Copy backup files to data/
cp backups/20260205/identities.json data/
cp backups/20260205/photo_index.json data/
cp backups/20260205/embeddings.npy data/

# Verify
python app/main.py
curl http://localhost:5001/health
```

**Restore production from local:**
```bash
# Full reseed (see section 3.4)
railway run -- rm /app/data/.initialized
git add data/
git commit -m "data: restore from backup"
git push origin main
```

---

## 6. Troubleshooting

### 6.1 App Won't Start

**Check Railway logs:**
```bash
railway logs
# Or view in Railway dashboard
```

**Common causes:**
| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError` | Missing dependency | Check requirements.txt |
| `FileNotFoundError: identities.json` | Volume not mounted | Check Railway volume config |
| `Address already in use` | Port conflict | Railway should set PORT automatically |
| Health check failing | App crashing on startup | Check logs for Python errors |

### 6.2 Photos Not Loading

**Check photo paths:**
```bash
# On Railway
railway run -- ls /app/raw_photos/ | head

# Verify photo_index.json paths match
railway run -- python -c "
import json
with open('/app/data/photo_index.json') as f:
    data = json.load(f)
for pid, pdata in list(data['photos'].items())[:3]:
    print(f\"{pid}: {pdata.get('path')}\")
"
```

### 6.3 Data Out of Sync

**Symptoms:** Web shows different data than local.

**Diagnose:**
```bash
# Compare identity counts
# Local:
python -c "import json; print(len(json.load(open('data/identities.json'))['identities']))"

# Production:
curl -s https://rhodesli.nolanandrewfox.com/health | jq .identities
```

**Fix:** Pull or push data per section 3.

### 6.4 Volume Full

**Check usage:**
```bash
railway run -- df -h /app/data
railway run -- du -sh /app/data/*
```

**Clean up:**
```bash
# Remove old backups
railway run -- rm -rf /app/data/backups/*

# Remove processed staging
railway run -- rm -rf /app/data/staging/*
```

### 6.5 How to Check Railway Logs

```bash
# CLI
railway logs
railway logs --follow  # Live tail

# Dashboard
# railway.app → Project → Service → Logs tab
```

### 6.6 How to SSH into Railway

```bash
# Interactive shell
railway shell

# Single command
railway run -- <command>

# Examples
railway run -- python -c "print('hello')"
railway run -- cat /app/data/identities.json | head
```

---

## 7. Common Tasks Quick Reference

| Task | Command/Steps |
|------|---------------|
| **Start local server** | `source venv/bin/activate && python app/main.py` |
| **Check app health** | `curl http://localhost:5001/health` or `curl https://rhodesli.nolanandrewfox.com/health` |
| **Add photos locally** | `cp photos/*.jpg raw_photos/ && python -m core.ingest_inbox --directory raw_photos/` |
| **Sync to production** | Commit data files, `git push`, Railway auto-deploys |
| **Pull from production** | `railway run -- cat /app/data/identities.json > data/identities.json` |
| **View production logs** | `railway logs` or Railway dashboard |
| **Restart service** | `railway up` or redeploy from dashboard |
| **Check staged uploads** | `railway run -- ls /app/data/staging/` |
| **Full reseed** | `railway run -- rm /app/data/.initialized && railway up` |
| **Manual backup** | `tar -czvf backups/$(date +%Y%m%d).tar.gz data/` |
| **Invite a contributor** | *Phase B — not yet implemented* |
| **Review submissions** | *Phase C — not yet implemented* |
| **Configure R2 backups** | *Phase F — not yet implemented* |

---

## 8. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Network interface to bind |
| `PORT` | `5001` | Server port (Railway sets this automatically) |
| `DEBUG` | `true` (local), `false` (prod) | Enable hot reload and verbose logging |
| `PROCESSING_ENABLED` | `true` (local), `false` (prod) | Enable ML processing on upload |
| `DATA_DIR` | `data` | Path to data directory |
| `PHOTOS_DIR` | `raw_photos` | Path to photos directory |

**Future (Phase B+):**
| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `JWT_SECRET` | Session signing secret |
| `ADMIN_EMAIL` | Admin email for notifications |

---

## Version History

| Date | Change |
|------|--------|
| 2026-02-05 | Initial creation (Phase A deployment) |
