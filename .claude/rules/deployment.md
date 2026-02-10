---
paths:
  - "Dockerfile"
  - "railway.toml"
  - ".dockerignore"
  - ".gitignore"
  - "requirements.txt"
  - "scripts/init_*.py"
  - "scripts/upload_to_r2.py"
  - "core/storage.py"
  - "Procfile"
---

# Deployment Rules

Before modifying deployment files, read docs/ops/OPS_DECISIONS.md.

Key rules:
1. data/ and photo directories must be in .gitignore but NEVER in .dockerignore (OD-002)
2. git push = code only. railway up = data seeding. Do not confuse them (OD-001)
3. Never add heavy ML libraries (torch, tensorflow, dlib, insightface) to requirements.txt (AD-007)
4. embeddings.npy must always be included in deployments — it is the R2 file index (OD-003)
5. If modifying the init script, test for the "zombie .initialized" edge case (OD-005)

## Data File Deployment Checklist

When creating a new file in `data/` that the app needs at runtime:

1. Add `!data/filename` to `.gitignore`
2. Add to `REQUIRED_DATA_FILES` in `scripts/init_railway_volume.py`
3. `git add data/filename`
4. All three MUST happen in the same commit

After deploy, verify with:
```bash
curl -s https://rhodesli.nolanandrewfox.com/[page-that-uses-it] | grep [expected-content]
```

Never verify deployment by checking local files only. Always fetch rendered HTML.

Run `python scripts/check_data_integrity.py` to verify deployment readiness locally.
