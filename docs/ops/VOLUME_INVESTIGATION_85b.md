# Railway Volume Investigation — Session 85b

**Date:** 2026-03-03
**Resolved:** YES

## Problem
Compare endpoint returning 500 with `OSError: [Errno 28] No space left on device`.
Health check showed root filesystem (3TB) had plenty of space, masking the real issue.

## Root Cause
Railway volume mounted at `/app/storage` is only **433MB total**.
The `data/backups/` directory had accumulated **346.77MB across 515 files** — 82% of all volume space.
Only 13MB (6MB at worst) remained free.

The health check was reporting `shutil.disk_usage("/")` which shows the container root filesystem (3TB), NOT the volume mount. This masked the real problem for months.

## What Was Consuming Space

| Directory/Files | Size (MB) | Files | Notes |
|---|---|---|---|
| data/backups/ | 346.77 | 515 | OLD full snapshots, never pruned |
| data/auto_backups/ | 18.36 | 24 | Auto-created, partial pruning existed |
| data/uploads/ | 16.52 | 12 | Stale upload job directories |
| .bak files (scattered) | ~20 | ~30 | Per-file backups, kept 3 per type |
| data/ (live data) | ~12 | ~25 | Actual operational data |
| **Total** | **~414** | **622** | |

## Fix Applied (commits d32038d → e2dc570)

### 1. Health check now reports volume usage (d32038d)
```json
"disk": {
  "total_mb": 3001822,  // root FS
  "free_mb": 1445034,
  "volume": {
    "mount": "/app/storage",
    "total_mb": 433,
    "free_mb": 388,      // was 13!
    "used_pct": 8.2      // was 94.9!
  }
}
```

### 2. Admin diagnostic endpoint (d32038d)
`GET /api/admin/disk-usage` — shows volume contents with file sizes.
Accepts Bearer sync token or admin session auth.

### 3. Startup logging differentiates root vs volume (d32038d)
```
Root FS: 52.1% used, 1437677MB free
Volume (/app/storage): 8.2% used, 388MB free of 433MB total
```

### 4. Aggressive startup cleanup (e2dc570)
- `data/backups/`: keep only 2 most recent snapshots (was unlimited)
- `data/auto_backups/`: keep 3 most recent (was 24)
- `data/cleanup_backups/`: keep 3 most recent
- `.bak` files: keep 1 per type (was 3)
- Stale upload dirs: cleaned after 24h
- Stale lock files: cleaned after 1h

### 5. Graceful disk-full handling (0d67095)
`_save_comparison_result` catches OSError and continues with in-memory cache.
Comparisons still work even when volume is full — results just aren't persisted.

## Result
Volume usage dropped from **94.9% → 8.2%** (388MB free of 433MB).
~375MB reclaimed on first startup after fix.

## Monitoring
- `/health` endpoint now shows `disk.volume` with `free_mb` and `used_pct`
- Startup logs warn when volume free space < 50MB
- `/api/admin/disk-usage` gives full directory breakdown on demand

## Prevention
The startup cleanup runs on every deploy. As long as deploys happen regularly
(they do — every code push triggers a Railway redeploy), backups will be pruned
automatically. The volume should stay well under 50% used.

If the volume fills up again, check `/api/admin/disk-usage` to identify the consumer.
